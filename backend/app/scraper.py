"""Scraping de Instagram via Apify REST API (actor apify/instagram-scraper).

Usa HTTP direto (httpx) em vez do SDK para evitar conflitos de dependência.
Fluxo:
  1. posts por perfil  (resultsType="posts")
  2. comentários dos posts coletados (resultsType="comments", mapeados por postUrl)
Persiste tudo em radar.posts / radar.comments.
"""
from __future__ import annotations

import time
from datetime import datetime

import httpx

from app import db
from app.config import CANDIDATES, CANDIDATE_BY_USERNAME, settings

ACTOR = "apify~instagram-scraper"
BASE = "https://api.apify.com/v2"
TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _run_actor(run_input: dict, max_wait: int = 600) -> list[dict]:
    """Inicia o actor, aguarda terminar e retorna os itens do dataset."""
    if not settings.apify_token:
        raise RuntimeError("APIFY_TOKEN não configurado")
    token = settings.apify_token
    with httpx.Client(timeout=60) as client:
        r = client.post(f"{BASE}/acts/{ACTOR}/runs", params={"token": token}, json=run_input)
        r.raise_for_status()
        run = r.json()["data"]
        run_id = run["id"]
        dataset_id = run["defaultDatasetId"]

        deadline = time.time() + max_wait
        status = run["status"]
        while status not in TERMINAL and time.time() < deadline:
            time.sleep(5)
            s = client.get(f"{BASE}/actor-runs/{run_id}", params={"token": token})
            s.raise_for_status()
            status = s.json()["data"]["status"]

        if status != "SUCCEEDED":
            raise RuntimeError(f"Apify run {run_id} terminou como {status}")

        items: list[dict] = []
        offset = 0
        while True:
            d = client.get(
                f"{BASE}/datasets/{dataset_id}/items",
                params={"token": token, "clean": "true", "offset": offset, "limit": 1000},
            )
            d.raise_for_status()
            batch = d.json()
            if not batch:
                break
            items.extend(batch)
            if len(batch) < 1000:
                break
            offset += len(batch)
        return items


def scrape_posts() -> list[dict]:
    profile_urls = [f"https://www.instagram.com/{c.username}/" for c in CANDIDATES]
    items = _run_actor(
        {
            "directUrls": profile_urls,
            "resultsType": "posts",
            "resultsLimit": settings.posts_per_profile,
            "addParentData": False,
        }
    )
    saved: list[dict] = []
    for it in items:
        cand = CANDIDATE_BY_USERNAME.get(it.get("ownerUsername"))
        if not cand:
            continue
        post_id = str(it.get("id") or it.get("shortCode"))
        url = it.get("url") or f"https://www.instagram.com/p/{it.get('shortCode')}/"
        db.execute(
            """
            insert into posts (id, candidate_id, url, caption, posted_at, like_count, comment_count, scraped_at)
            values (%(id)s,%(cand)s,%(url)s,%(caption)s,%(posted_at)s,%(likes)s,%(comments)s, now())
            on conflict (id) do update set
                caption=excluded.caption, like_count=excluded.like_count,
                comment_count=excluded.comment_count, scraped_at=now()
            """,
            {
                "id": post_id,
                "cand": cand.id,
                "url": url,
                "caption": it.get("caption") or "",
                "posted_at": _parse_ts(it.get("timestamp")),
                "likes": int(it.get("likesCount") or 0),
                "comments": int(it.get("commentsCount") or 0),
            },
        )
        saved.append({"post_id": post_id, "url": url, "candidate_id": cand.id})
    return saved


def scrape_comments(posts: list[dict]) -> int:
    if not posts:
        return 0
    url_to_post = {p["url"]: p for p in posts}
    items = _run_actor(
        {
            "directUrls": [p["url"] for p in posts],
            "resultsType": "comments",
            "resultsLimit": settings.comments_per_post,
        }
    )
    saved = 0
    for it in items:
        post = url_to_post.get(it.get("postUrl"))
        if not post:
            continue
        text = (it.get("text") or "").strip()
        if not text:
            continue
        db.execute(
            """
            insert into comments (id, post_id, candidate_id, text, owner_username, commented_at, like_count)
            values (%(id)s,%(post)s,%(cand)s,%(text)s,%(owner)s,%(ts)s,%(likes)s)
            on conflict (id) do update set text=excluded.text, like_count=excluded.like_count
            """,
            {
                "id": str(it.get("id")),
                "post": post["post_id"],
                "cand": post["candidate_id"],
                "text": text,
                "owner": it.get("ownerUsername"),
                "ts": _parse_ts(it.get("timestamp")),
                "likes": int(it.get("likesCount") or 0),
            },
        )
        saved += 1
    return saved


def run_full_scrape() -> dict:
    from app.sentiment import analyze_pending

    run_row = db.query_one(
        "insert into scrape_runs (status, message) values ('running','scraping iniciado') returning id"
    )
    run_id = str(run_row["id"])
    try:
        posts = scrape_posts()
        n_comments = scrape_comments(posts)
        n_analyzed = analyze_pending()
        db.execute(
            """
            update scrape_runs set status='completed', finished_at=now(), message='ok',
                posts_scraped=%(p)s, comments_scraped=%(c)s, comments_analyzed=%(a)s
            where id=%(id)s
            """,
            {"id": run_id, "p": len(posts), "c": n_comments, "a": n_analyzed},
        )
        return {"run_id": run_id, "posts": len(posts), "comments": n_comments, "analyzed": n_analyzed}
    except Exception as exc:  # noqa: BLE001
        db.execute(
            "update scrape_runs set status='failed', finished_at=now(), message=%(m)s where id=%(id)s",
            {"id": run_id, "m": str(exc)[:500]},
        )
        raise
