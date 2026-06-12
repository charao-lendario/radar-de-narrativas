"""Configuração via variáveis de ambiente."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Candidate:
    id: str
    username: str
    display_name: str
    cargo: str
    is_competitor: bool = False


# Mapa fixo dos perfis monitorados (espelha src/lib/constants.ts do frontend)
CANDIDATES: list[Candidate] = [
    Candidate("charlles", "charlles.evangelista", "Charlles Evangelista", "Deputado Federal"),
    Candidate("sheila", "delegadasheila", "Delegada Sheila", "Deputada Estadual"),
    Candidate("ione", "delegadaione", "Delegada Ione", "Deputada", is_competitor=True),
]

CANDIDATE_BY_ID = {c.id: c for c in CANDIDATES}
CANDIDATE_BY_USERNAME = {c.username: c for c in CANDIDATES}


@dataclass(frozen=True)
class Settings:
    # DATABASE_URL é injetado via env no deploy (ver .env / stack.yml na VPS).
    # Default aponta pro Postgres do Supabase self-hosted (rede easypanel), sem credenciais.
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://supabase_admin@iaxlab_supabase_db:5432/postgres",
        )
    )
    db_schema: str = field(default_factory=lambda: os.getenv("DB_SCHEMA", "radar"))
    apify_token: str = field(default_factory=lambda: os.getenv("APIFY_TOKEN", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    sentiment_model: str = field(
        default_factory=lambda: os.getenv("SENTIMENT_MODEL", "claude-haiku-4-5-20251001")
    )
    suggestions_model: str = field(
        default_factory=lambda: os.getenv("SUGGESTIONS_MODEL", "claude-haiku-4-5-20251001")
    )
    # auto = tenta LLM e cai pra heurística; claude = só LLM; heuristic = só léxico
    sentiment_provider: str = field(default_factory=lambda: os.getenv("SENTIMENT_PROVIDER", "auto"))
    # limites de scraping (controle de custo Apify)
    posts_per_profile: int = field(default_factory=lambda: int(os.getenv("POSTS_PER_PROFILE", "12")))
    comments_per_post: int = field(default_factory=lambda: int(os.getenv("COMMENTS_PER_POST", "50")))
    # limites do scraping ad-hoc (comparação sob demanda — mais enxuto p/ ser rápido)
    adhoc_posts: int = field(default_factory=lambda: int(os.getenv("ADHOC_POSTS", "8")))
    adhoc_comments_per_post: int = field(default_factory=lambda: int(os.getenv("ADHOC_COMMENTS", "30")))
    # cron diário de scraping (hora BRT). Vazio = desligado.
    scrape_cron_hour: str = field(default_factory=lambda: os.getenv("SCRAPE_CRON_HOUR", "6"))
    cors_origins: str = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*"))


settings = Settings()


def extract_username(url_or_handle: str) -> str | None:
    """Extrai o username de uma URL do Instagram, @handle ou username puro."""
    import re

    s = (url_or_handle or "").strip()
    if not s:
        return None
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", s)
    if m:
        candidate = m.group(1)
    else:
        candidate = s.lstrip("@").strip("/")
    candidate = candidate.split("?")[0].split("/")[0].lower()
    # rejeita rotas do IG que não são perfis
    if not candidate or candidate in {"p", "reel", "reels", "explore", "stories", "tv"}:
        return None
    if not re.fullmatch(r"[a-z0-9._]{1,30}", candidate):
        return None
    return candidate
