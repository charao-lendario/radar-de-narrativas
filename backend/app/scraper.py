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


def scrape_profiles() -> int:
    """Coleta metadados de perfil (foto/bio/seguidores) dos 3 perfis e faz upsert."""
    profile_urls = [f"https://www.instagram.com/{c.username}/" for c in CANDIDATES]
    items = _run_actor(
        {"directUrls": profile_urls, "resultsType": "details", "resultsLimit": 1}, max_wait=300
    )
    saved = 0
    for it in items:
        cand = CANDIDATE_BY_USERNAME.get(it.get("username"))
        if not cand:
            continue
        pic_url = it.get("profilePicUrlHD") or it.get("profilePicUrl")
        pic_data, pic_ct = None, None
        if pic_url:
            try:
                with httpx.Client(timeout=30, follow_redirects=True) as cl:
                    resp = cl.get(pic_url)
                    if resp.status_code == 200 and resp.content:
                        pic_data = resp.content
                        pic_ct = resp.headers.get("content-type", "image/jpeg")
            except Exception:  # noqa: BLE001 — foto é opcional
                pass
        category = it.get("businessCategoryName")
        if category and "," in category:  # vem como "None,Politician"
            category = category.split(",")[-1].strip()
        db.execute(
            """
            insert into profiles (candidate_id, username, full_name, biography, followers_count,
                follows_count, posts_count, profile_pic_url, profile_pic_data, profile_pic_content_type,
                verified, is_private, external_url, category, updated_at)
            values (%(cid)s,%(u)s,%(fn)s,%(bio)s,%(fol)s,%(fw)s,%(pc)s,%(purl)s,%(pdata)s,%(pct)s,
                %(ver)s,%(priv)s,%(ext)s,%(cat)s, now())
            on conflict (candidate_id) do update set
                username=excluded.username, full_name=excluded.full_name, biography=excluded.biography,
                prev_followers_count=profiles.followers_count,
                followers_count=excluded.followers_count, follows_count=excluded.follows_count,
                posts_count=excluded.posts_count, profile_pic_url=excluded.profile_pic_url,
                profile_pic_data=coalesce(excluded.profile_pic_data, profiles.profile_pic_data),
                profile_pic_content_type=coalesce(excluded.profile_pic_content_type, profiles.profile_pic_content_type),
                verified=excluded.verified, is_private=excluded.is_private,
                external_url=excluded.external_url, category=excluded.category, updated_at=now()
            """,
            {
                "cid": cand.id,
                "u": it.get("username"),
                "fn": it.get("fullName"),
                "bio": it.get("biography") or "",
                "fol": int(it.get("followersCount") or 0),
                "fw": int(it.get("followsCount") or 0),
                "pc": int(it.get("postsCount") or 0),
                "purl": pic_url,
                "pdata": pic_data,
                "pct": pic_ct,
                "ver": bool(it.get("verified")),
                "priv": bool(it.get("private")),
                "ext": it.get("externalUrl"),
                "cat": category,
            },
        )
        saved += 1
    return saved


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


def scrape_comments(posts: list[dict], limit: int | None = None) -> int:
    if not posts:
        return 0
    url_to_post = {p["url"]: p for p in posts}
    items = _run_actor(
        {
            "directUrls": [p["url"] for p in posts],
            "resultsType": "comments",
            "resultsLimit": limit or settings.comments_per_post,
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


def _download_pic(url: str | None) -> tuple[bytes | None, str | None]:
    if not url:
        return None, None
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as cl:
            resp = cl.get(url)
            if resp.status_code == 200 and resp.content:
                return resp.content, resp.headers.get("content-type", "image/jpeg")
    except Exception:  # noqa: BLE001
        pass
    return None, None


def analyze_single_profile(username: str, display_name: str | None = None) -> dict:
    """Pipeline sob demanda para UM perfil enviado pelo usuário (comparação ad-hoc)."""
    from app.sentiment import analyze_pending

    cand_id = username  # username é único e estável como id
    display = display_name or username
    url = f"https://www.instagram.com/{username}/"

    # 1. registra candidato ad-hoc
    db.execute(
        """
        insert into candidates (id, username, display_name, cargo, is_competitor, is_adhoc)
        values (%(id)s,%(u)s,%(d)s,'Perfil comparado', true, true)
        on conflict (id) do update set username=excluded.username, is_competitor=true, is_adhoc=true
        """,
        {"id": cand_id, "u": username, "d": display},
    )

    # 2. detalhes do perfil (foto/bio/seguidores)
    details = _run_actor({"directUrls": [url], "resultsType": "details", "resultsLimit": 1}, max_wait=300)
    for it in details:
        if (it.get("username") or "").lower() != username:
            continue
        pic_url = it.get("profilePicUrlHD") or it.get("profilePicUrl")
        pic_data, pic_ct = _download_pic(pic_url)
        category = it.get("businessCategoryName")
        if category and "," in category:
            category = category.split(",")[-1].strip()
        full_name = it.get("fullName")
        if full_name:
            db.execute("update candidates set display_name=%(d)s where id=%(id)s", {"d": full_name, "id": cand_id})
        db.execute(
            """
            insert into profiles (candidate_id, username, full_name, biography, followers_count,
                follows_count, posts_count, profile_pic_url, profile_pic_data, profile_pic_content_type,
                verified, is_private, external_url, category, updated_at)
            values (%(cid)s,%(u)s,%(fn)s,%(bio)s,%(fol)s,%(fw)s,%(pc)s,%(purl)s,%(pdata)s,%(pct)s,
                %(ver)s,%(priv)s,%(ext)s,%(cat)s, now())
            on conflict (candidate_id) do update set
                username=excluded.username, full_name=excluded.full_name, biography=excluded.biography,
                prev_followers_count=profiles.followers_count,
                followers_count=excluded.followers_count, follows_count=excluded.follows_count,
                posts_count=excluded.posts_count, profile_pic_url=excluded.profile_pic_url,
                profile_pic_data=coalesce(excluded.profile_pic_data, profiles.profile_pic_data),
                profile_pic_content_type=coalesce(excluded.profile_pic_content_type, profiles.profile_pic_content_type),
                verified=excluded.verified, is_private=excluded.is_private,
                external_url=excluded.external_url, category=excluded.category, updated_at=now()
            """,
            {
                "cid": cand_id, "u": username, "fn": full_name, "bio": it.get("biography") or "",
                "fol": int(it.get("followersCount") or 0), "fw": int(it.get("followsCount") or 0),
                "pc": int(it.get("postsCount") or 0), "purl": pic_url, "pdata": pic_data, "pct": pic_ct,
                "ver": bool(it.get("verified")), "priv": bool(it.get("private")),
                "ext": it.get("externalUrl"), "cat": category,
            },
        )

    # 3. posts
    post_items = _run_actor(
        {"directUrls": [url], "resultsType": "posts", "resultsLimit": settings.adhoc_posts, "addParentData": False}
    )
    posts: list[dict] = []
    for it in post_items:
        if (it.get("ownerUsername") or "").lower() != username:
            continue
        post_id = str(it.get("id") or it.get("shortCode"))
        purl = it.get("url") or f"https://www.instagram.com/p/{it.get('shortCode')}/"
        db.execute(
            """
            insert into posts (id, candidate_id, url, caption, posted_at, like_count, comment_count, scraped_at)
            values (%(id)s,%(cand)s,%(url)s,%(caption)s,%(posted_at)s,%(likes)s,%(comments)s, now())
            on conflict (id) do update set caption=excluded.caption, like_count=excluded.like_count,
                comment_count=excluded.comment_count, scraped_at=now()
            """,
            {
                "id": post_id, "cand": cand_id, "url": purl, "caption": it.get("caption") or "",
                "posted_at": _parse_ts(it.get("timestamp")), "likes": int(it.get("likesCount") or 0),
                "comments": int(it.get("commentsCount") or 0),
            },
        )
        posts.append({"post_id": post_id, "url": purl, "candidate_id": cand_id})

    # 4. comentários + 5. sentimento
    n_comments = scrape_comments(posts, limit=settings.adhoc_comments_per_post)
    n_analyzed = analyze_pending()
    return {"username": username, "posts": len(posts), "comments": n_comments, "analyzed": n_analyzed}


def run_full_scrape() -> dict:
    from app.sentiment import analyze_pending

    run_row = db.query_one(
        "insert into scrape_runs (status, message) values ('running','scraping iniciado') returning id"
    )
    run_id = str(run_row["id"])
    try:
        scrape_profiles()
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
