"""Radar de Narrativas — API FastAPI."""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from app import analytics, db, profiles as profiles_module, suggestions
from app.config import CANDIDATES, extract_username, settings
from app.models import (
    CompetitiveAnalysisData,
    ComparisonData,
    ContextualSentimentData,
    HealthStatus,
    CompareRequest,
    CompareResult,
    OverviewData,
    PostsResponse,
    ProfileData,
    ScrapingRunStatus,
    SentimentTimelineData,
    SuggestionsRequest,
    SuggestionsResponse,
    ThemesResponse,
    WordCloudData,
)

scheduler: Optional[BackgroundScheduler] = None
_scrape_lock = threading.Lock()
_adhoc_lock = threading.Lock()
_adhoc_running: set[str] = set()
DEFAULT_OUR_ID = "sheila"


def _run_adhoc(username: str) -> None:
    with _adhoc_lock:
        _adhoc_running.add(username)
    try:
        from app.scraper import analyze_single_profile
        analyze_single_profile(username)
    except Exception as exc:  # noqa: BLE001
        print(f"[compare] erro analisando @{username}: {exc}")
    finally:
        with _adhoc_lock:
            _adhoc_running.discard(username)


def run_migrations() -> None:
    sql = (Path(__file__).parent.parent / "migrations" / "001_init.sql").read_text(encoding="utf-8")
    with db.cursor() as cur:
        cur.execute(sql)
    # seed dos candidatos
    for c in CANDIDATES:
        db.execute(
            """
            insert into candidates (id, username, display_name, cargo, is_competitor)
            values (%(id)s,%(u)s,%(d)s,%(c)s,%(comp)s)
            on conflict (id) do update set
                username=excluded.username, display_name=excluded.display_name,
                cargo=excluded.cargo, is_competitor=excluded.is_competitor
            """,
            {"id": c.id, "u": c.username, "d": c.display_name, "c": c.cargo, "comp": c.is_competitor},
        )


def _background_scrape() -> None:
    if not _scrape_lock.acquire(blocking=False):
        return
    try:
        from app.scraper import run_full_scrape
        run_full_scrape()
    except Exception as exc:  # noqa: BLE001
        print(f"[scrape] erro: {exc}")
    finally:
        _scrape_lock.release()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    try:
        run_migrations()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] migration falhou: {exc}")
    if settings.scrape_cron_hour.strip():
        scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
        scheduler.add_job(
            _background_scrape,
            CronTrigger(hour=settings.scrape_cron_hour, minute=0),
            id="daily_scrape",
            replace_existing=True,
        )
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Radar de Narrativas API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health ---
@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    db_ok = db.ping()
    last = db.query_one("select max(finished_at) as ls from scrape_runs where status='completed'") if db_ok else None
    return HealthStatus(
        status="ok" if db_ok else "degraded",
        database="connected" if db_ok else "error",
        scheduler="running" if scheduler and scheduler.running else "stopped",
        last_scrape=last["ls"].isoformat() if last and last["ls"] else None,
    )


# --- Profiles ---
@app.get("/api/v1/profiles", response_model=list[ProfileData])
def profiles() -> list[ProfileData]:
    return profiles_module.get_profiles()


@app.get("/api/v1/profiles/{candidate_id}/avatar")
def profile_avatar(candidate_id: str) -> Response:
    result = profiles_module.get_avatar(candidate_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Avatar não disponível")
    data, content_type = result
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


# --- Analytics ---
@app.get("/api/v1/analytics/overview", response_model=OverviewData)
def overview() -> OverviewData:
    return analytics.get_overview()


@app.get("/api/v1/analytics/sentiment-timeline", response_model=SentimentTimelineData)
def sentiment_timeline(
    candidate_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> SentimentTimelineData:
    return analytics.get_sentiment_timeline(candidate_id, start_date, end_date)


@app.get("/api/v1/analytics/wordcloud", response_model=WordCloudData)
def wordcloud(candidate_id: Optional[str] = None) -> WordCloudData:
    return analytics.get_wordcloud(candidate_id)


@app.get("/api/v1/analytics/themes", response_model=ThemesResponse)
def themes(candidate_id: Optional[str] = None) -> ThemesResponse:
    return analytics.get_themes(candidate_id)


@app.get("/api/v1/analytics/posts", response_model=PostsResponse)
def posts(
    candidate_id: Optional[str] = None,
    sort_by: str = "posted_at",
    order: str = "desc",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PostsResponse:
    return analytics.get_posts(candidate_id, sort_by, order, limit, offset)


@app.get("/api/v1/analytics/comparison", response_model=ComparisonData)
def comparison() -> ComparisonData:
    return analytics.get_comparison()


@app.get("/api/v1/analytics/competitive", response_model=CompetitiveAnalysisData)
def competitive(
    our_username: Optional[str] = None,
    competitor_username: Optional[str] = None,
) -> CompetitiveAnalysisData:
    return analytics.get_competitive(our_username, competitor_username)


@app.post("/api/v1/analytics/suggestions", response_model=SuggestionsResponse)
def post_suggestions(body: SuggestionsRequest | None = None) -> SuggestionsResponse:
    candidate_id = body.candidate_id if body else None
    return suggestions.generate_suggestions(candidate_id)


# --- Comparação sob demanda (colar link de perfil) ---
@app.post("/api/v1/compare/analyze", response_model=CompareResult)
def compare_analyze(body: CompareRequest) -> CompareResult:
    username = extract_username(body.url)
    if not username:
        return CompareResult(status="not_found", message="Não consegui identificar um perfil válido nesse link.")
    with _adhoc_lock:
        running = username in _adhoc_running
    if not running:
        threading.Thread(target=_run_adhoc, args=(username,), daemon=True).start()
    return CompareResult(
        status="running",
        message=f"Analisando @{username}… isso leva ~1-2 min.",
        username=username,
        competitor_profile=profiles_module.get_one(username),
    )


@app.get("/api/v1/compare/{username}", response_model=CompareResult)
def compare_status(username: str, our: Optional[str] = None) -> CompareResult:
    username = username.lower()
    our = our or DEFAULT_OUR_ID
    with _adhoc_lock:
        running = username in _adhoc_running
    has_data = db.query_one("select 1 as x from posts where candidate_id=%(c)s limit 1", {"c": username})
    competitor_profile = profiles_module.get_one(username)
    if not has_data:
        return CompareResult(
            status="running" if running else "not_found",
            message="Analisando…" if running else "Perfil ainda não analisado.",
            username=username,
            competitor_profile=competitor_profile,
        )
    return CompareResult(
        status="running" if running else "ready",
        username=username,
        our_profile=profiles_module.get_one(our),
        competitor_profile=competitor_profile,
        analysis=analytics.get_competitive(our_username=our, competitor_username=username),
    )


# --- Análise contextual ---
@app.post("/api/v1/analysis/sentiment/contextual/{post_id}", response_model=ContextualSentimentData)
def contextual(post_id: str) -> ContextualSentimentData:
    return analytics.get_contextual_sentiment(post_id)


# --- Scraping ---
@app.post("/api/v1/scraping/run", response_model=ScrapingRunStatus)
def scraping_run() -> ScrapingRunStatus:
    if _scrape_lock.locked():
        return ScrapingRunStatus(run_id="", status="running", message="Já existe um scraping em andamento")
    threading.Thread(target=_background_scrape, daemon=True).start()
    return ScrapingRunStatus(run_id="pending", status="running", message="Scraping iniciado em background")


@app.get("/")
def root():
    return {"service": "radar-de-narrativas-api", "status": "ok"}
