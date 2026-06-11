"""Agregações SQL que alimentam os endpoints de analytics."""
from __future__ import annotations

import re
from collections import Counter

from app import db
from app.config import CANDIDATE_BY_ID, CANDIDATE_BY_USERNAME
from app.models import (
    CandidateComparison,
    CandidateMetrics,
    CompetitiveAnalysisData,
    CompetitiveMetrics,
    ComparisonData,
    ContextualSentimentData,
    OverviewData,
    PostData,
    PostsResponse,
    SentimentDistribution,
    SentimentTimelineData,
    ThemeByCandidate,
    ThemeCount,
    ThemeData,
    ThemesResponse,
    TimelineDataPoint,
    TrendData,
    WordCloudData,
    WordCloudWord,
)

MAIN_IDS = ["charlles", "sheila"]


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def _candidate_metrics_row(candidate_id: str) -> dict:
    row = db.query_one(
        """
        with p as (
            select coalesce(sum(like_count),0) as likes,
                   coalesce(sum(comment_count),0) as ig_comments,
                   count(*) as total_posts
            from posts where candidate_id = %(cid)s
        ),
        c as (
            select count(*) as total_comments,
                   count(*) filter (where sentiment='positive') as pos,
                   count(*) filter (where sentiment='negative') as neg,
                   count(*) filter (where sentiment='neutral')  as neu,
                   coalesce(avg(sentiment_score) filter (where analyzed_at is not null),0) as avg_score
            from comments where candidate_id = %(cid)s
        )
        select p.total_posts, p.likes, p.ig_comments,
               c.total_comments, c.pos, c.neg, c.neu, c.avg_score
        from p, c
        """,
        {"cid": candidate_id},
    )
    return row or {}


def build_candidate_metrics(candidate_id: str) -> CandidateMetrics:
    cand = CANDIDATE_BY_ID[candidate_id]
    r = _candidate_metrics_row(candidate_id)
    return CandidateMetrics(
        candidate_id=candidate_id,
        username=cand.username,
        display_name=cand.display_name,
        total_posts=int(r.get("total_posts", 0)),
        total_comments=int(r.get("total_comments", 0)),
        average_sentiment_score=round(float(r.get("avg_score", 0)), 4),
        sentiment_distribution=SentimentDistribution(
            positive=int(r.get("pos", 0)),
            negative=int(r.get("neg", 0)),
            neutral=int(r.get("neu", 0)),
        ),
        total_engagement=int(r.get("likes", 0)) + int(r.get("ig_comments", 0)),
    )


def get_overview() -> OverviewData:
    candidates = [build_candidate_metrics(cid) for cid in MAIN_IDS]
    last = db.query_one("select max(finished_at) as ls from scrape_runs where status='completed'")
    total_analyzed = db.query_one("select count(*) as n from comments where analyzed_at is not null")
    return OverviewData(
        candidates=candidates,
        last_scrape=_iso(last["ls"]) if last else None,
        total_comments_analyzed=int(total_analyzed["n"]) if total_analyzed else 0,
    )


def _top_themes(candidate_id: str | None = None, limit: int = 5) -> list[ThemeCount]:
    where = "where analyzed_at is not null"
    params: dict = {"lim": limit}
    if candidate_id:
        where += " and candidate_id = %(cid)s"
        params["cid"] = candidate_id
    rows = db.query_all(
        f"""
        select theme, count(*) as count
        from comments c, unnest(c.themes) as theme
        {where}
        group by theme order by count desc limit %(lim)s
        """,
        params,
    )
    return [ThemeCount(theme=r["theme"], count=int(r["count"])) for r in rows]


def get_themes(candidate_id: str | None = None) -> ThemesResponse:
    cid = _resolve_filter(candidate_id)
    where = "where c.analyzed_at is not null"
    params: dict = {}
    if cid:
        where += " and c.candidate_id = %(cid)s"
        params["cid"] = cid
    rows = db.query_all(
        f"""
        select theme, c.candidate_id, count(*) as count
        from comments c, unnest(c.themes) as theme
        {where}
        group by theme, c.candidate_id
        """,
        params,
    )
    total = sum(int(r["count"]) for r in rows) or 1
    agg: dict[str, dict] = {}
    for r in rows:
        t = r["theme"]
        agg.setdefault(t, {"count": 0, "by": {}})
        agg[t]["count"] += int(r["count"])
        agg[t]["by"][r["candidate_id"]] = agg[t]["by"].get(r["candidate_id"], 0) + int(r["count"])
    themes = []
    for theme, data in sorted(agg.items(), key=lambda kv: kv[1]["count"], reverse=True):
        by_cand = [
            ThemeByCandidate(candidate_id=k, username=CANDIDATE_BY_ID[k].username, count=v)
            for k, v in data["by"].items() if k in CANDIDATE_BY_ID
        ]
        themes.append(
            ThemeData(
                theme=theme,
                count=data["count"],
                percentage=round(100 * data["count"] / total, 2),
                by_candidate=by_cand,
            )
        )
    return ThemesResponse(themes=themes)


def get_sentiment_timeline(candidate_id=None, start_date=None, end_date=None) -> SentimentTimelineData:
    cid = _resolve_filter(candidate_id)
    where = ["p.posted_at is not null"]
    params: dict = {}
    if cid:
        where.append("p.candidate_id = %(cid)s")
        params["cid"] = cid
    if start_date:
        where.append("p.posted_at >= %(sd)s")
        params["sd"] = start_date
    if end_date:
        where.append("p.posted_at <= %(ed)s")
        params["ed"] = end_date
    rows = db.query_all(
        f"""
        select p.id, p.candidate_id, p.url, p.caption, p.posted_at,
               coalesce(avg(c.sentiment_score) filter (where c.analyzed_at is not null),0) as avg_score,
               count(c.id) filter (where c.analyzed_at is not null) as comment_count
        from posts p
        left join comments c on c.post_id = p.id
        where {' and '.join(where)}
        group by p.id, p.candidate_id, p.url, p.caption, p.posted_at
        order by p.posted_at asc
        """,
        params,
    )
    points = [
        TimelineDataPoint(
            candidate_id=r["candidate_id"],
            candidate_username=CANDIDATE_BY_ID[r["candidate_id"]].username,
            post_id=r["id"],
            post_url=r["url"] or "",
            post_caption=(r["caption"] or "")[:200],
            posted_at=_iso(r["posted_at"]) or "",
            average_sentiment_score=round(float(r["avg_score"]), 4),
            comment_count=int(r["comment_count"]),
        )
        for r in rows if r["candidate_id"] in CANDIDATE_BY_ID
    ]
    return SentimentTimelineData(data_points=points)


# stopwords PT-BR para a nuvem de palavras (Code First — zero LLM)
_STOPWORDS = set(
    "a o e de da do das dos que em um uma para por com não nao se ao na no nos nas "
    "as os é eh foi ser tem tá ta tava muito mais já ja só so mas como meu minha seu sua "
    "ele ela eles elas isso esse essa este esta aqui ali lá la pra pro pelo pela aos à às "
    "vc você voce vcs nós nos eu te lhe me ou nem sem até ate sobre entre quando onde quem "
    "qual quais porque pq tudo nada algo todos toda todas cada outro outra bem vai vou ter "
    "estão estao está esta sao são fica ficou faz fez tao tão deus parabéns parabens sim".split()
)
_TOKEN_RE = re.compile(r"[a-záàâãéêíóôõúüç]{3,}", re.IGNORECASE)


def get_wordcloud(candidate_id=None, top: int = 80) -> WordCloudData:
    cid = _resolve_filter(candidate_id)
    where = "where length(trim(text)) > 0"
    params: dict = {}
    if cid:
        where += " and candidate_id = %(cid)s"
        params["cid"] = cid
    rows = db.query_all(f"select text from comments {where}", params)
    counter: Counter[str] = Counter()
    for r in rows:
        for tok in _TOKEN_RE.findall((r["text"] or "").lower()):
            if tok not in _STOPWORDS and not tok.startswith("http"):
                counter[tok] += 1
    words = [WordCloudWord(word=w, count=c) for w, c in counter.most_common(top)]
    return WordCloudData(words=words, total_unique_words=len(counter))


_SORT_COLUMNS = {
    "posted_at": "p.posted_at",
    "engagement": "(p.like_count + p.comment_count)",
    "likes": "p.like_count",
    "comments": "p.comment_count",
    "sentiment": "avg_score",
}


def get_posts(candidate_id=None, sort_by="posted_at", order="desc", limit=20, offset=0) -> PostsResponse:
    cid = _resolve_filter(candidate_id)
    col = _SORT_COLUMNS.get(sort_by, "p.posted_at")
    direction = "asc" if str(order).lower() == "asc" else "desc"
    where = "where 1=1"
    params: dict = {"lim": limit, "off": offset}
    if cid:
        where += " and p.candidate_id = %(cid)s"
        params["cid"] = cid
    total_row = db.query_one(f"select count(*) as n from posts p {where}", params)
    rows = db.query_all(
        f"""
        select p.id, p.candidate_id, p.url, p.caption, p.posted_at,
               p.like_count, p.comment_count,
               coalesce(avg(c.sentiment_score) filter (where c.analyzed_at is not null),0) as avg_score,
               count(c.id) filter (where c.sentiment='positive') as pos,
               count(c.id) filter (where c.sentiment='negative') as neg,
               count(c.id) filter (where c.analyzed_at is not null) as analyzed
        from posts p
        left join comments c on c.post_id = p.id
        {where}
        group by p.id, p.candidate_id, p.url, p.caption, p.posted_at, p.like_count, p.comment_count
        order by {col} {direction} nulls last
        limit %(lim)s offset %(off)s
        """,
        params,
    )
    posts = []
    for r in rows:
        analyzed = int(r["analyzed"]) or 0
        posts.append(
            PostData(
                post_id=r["id"],
                candidate_username=CANDIDATE_BY_ID[r["candidate_id"]].username,
                url=r["url"] or "",
                caption=r["caption"] or "",
                posted_at=_iso(r["posted_at"]) or "",
                like_count=int(r["like_count"]),
                comment_count=int(r["comment_count"]),
                positive_ratio=round(int(r["pos"]) / analyzed, 4) if analyzed else 0.0,
                negative_ratio=round(int(r["neg"]) / analyzed, 4) if analyzed else 0.0,
                average_sentiment_score=round(float(r["avg_score"]), 4),
            )
        )
    return PostsResponse(
        posts=posts, total=int(total_row["n"]) if total_row else 0, limit=limit, offset=offset
    )


def _trend(candidate_id: str) -> TrendData:
    rows = db.query_all(
        """
        select coalesce(avg(c.sentiment_score) filter (where c.analyzed_at is not null),0) as score
        from posts p left join comments c on c.post_id = p.id
        where p.candidate_id = %(cid)s and p.posted_at is not null
        group by p.id order by max(p.posted_at) desc
        """,
        {"cid": candidate_id},
    )
    scores = [float(r["score"]) for r in rows]
    if len(scores) < 2:
        return TrendData(direction="stable", recent_avg=0.0, previous_avg=0.0, delta=0.0)
    half = max(1, len(scores) // 2)
    recent = sum(scores[:half]) / half
    previous = sum(scores[half:]) / max(1, len(scores) - half)
    delta = recent - previous
    direction = "improving" if delta > 0.05 else "declining" if delta < -0.05 else "stable"
    return TrendData(
        direction=direction,
        recent_avg=round(recent, 4),
        previous_avg=round(previous, 4),
        delta=round(delta, 4),
    )


def get_comparison() -> ComparisonData:
    candidates = []
    for cid in MAIN_IDS:
        base = build_candidate_metrics(cid)
        candidates.append(
            CandidateComparison(
                **base.model_dump(),
                top_themes=_top_themes(cid),
                trend=_trend(cid),
            )
        )
    return ComparisonData(candidates=candidates)


def _competitive_metrics(username: str) -> CompetitiveMetrics | None:
    cand = CANDIDATE_BY_USERNAME.get(username)
    if not cand:
        return None
    base = build_candidate_metrics(cand.id)
    posts = base.total_posts or 1
    likes_row = db.query_one(
        "select coalesce(sum(like_count),0) as l, coalesce(sum(comment_count),0) as cm from posts where candidate_id=%(c)s",
        {"c": cand.id},
    )
    return CompetitiveMetrics(
        username=cand.username,
        display_name=cand.display_name,
        total_posts=base.total_posts,
        total_comments=base.total_comments,
        average_sentiment_score=base.average_sentiment_score,
        total_engagement=base.total_engagement,
        avg_likes_per_post=round(int(likes_row["l"]) / posts, 1),
        avg_comments_per_post=round(int(likes_row["cm"]) / posts, 1),
        sentiment_distribution=base.sentiment_distribution,
        top_themes=_top_themes(cand.id),
    )


def get_competitive(our_username=None, competitor_username=None) -> CompetitiveAnalysisData:
    our_username = our_username or "delegadasheila"
    competitor_username = competitor_username or "delegadaione"
    our = _competitive_metrics(our_username)
    comp = _competitive_metrics(competitor_username)
    eng_adv = (our.total_engagement - comp.total_engagement) if our and comp else 0.0
    sent_adv = (
        round(our.average_sentiment_score - comp.average_sentiment_score, 4) if our and comp else 0.0
    )
    return CompetitiveAnalysisData(
        our_candidate=our,
        competitor=comp,
        engagement_advantage=float(eng_adv),
        sentiment_advantage=float(sent_adv),
    )


def get_contextual_sentiment(post_id: str) -> ContextualSentimentData:
    post = db.query_one(
        """
        select p.id, p.caption, cand.display_name
        from posts p join candidates cand on cand.id = p.candidate_id
        where p.id = %(id)s
        """,
        {"id": post_id},
    )
    counts = db.query_one(
        """
        select count(*) as total,
               count(*) filter (where analyzed_at is not null) as classified,
               count(*) filter (where stance='apoio')  as apoio,
               count(*) filter (where stance='contra')  as contra,
               count(*) filter (where stance='neutro')  as neutro
        from comments where post_id = %(id)s
        """,
        {"id": post_id},
    )
    classified = int(counts["classified"]) if counts else 0
    apoio = int(counts["apoio"]) if counts else 0
    contra = int(counts["contra"]) if counts else 0
    neutro = int(counts["neutro"]) if counts else 0
    base = classified or 1
    return ContextualSentimentData(
        post_id=post_id,
        caption_preview=((post["caption"] if post else "") or "")[:160],
        candidate_name=post["display_name"] if post else "",
        total_comments=int(counts["total"]) if counts else 0,
        total_classified=classified,
        apoio=apoio,
        contra=contra,
        neutro=neutro,
        apoio_percent=round(100 * apoio / base, 1),
        contra_percent=round(100 * contra / base, 1),
        neutro_percent=round(100 * neutro / base, 1),
    )


def _resolve_filter(candidate_id):
    """Aceita 'charlles'/'sheila'/'ione' (ou username) e retorna o id canônico, ou None."""
    if not candidate_id:
        return None
    if candidate_id in CANDIDATE_BY_ID:
        return candidate_id
    if candidate_id in CANDIDATE_BY_USERNAME:
        return CANDIDATE_BY_USERNAME[candidate_id].id
    return None
