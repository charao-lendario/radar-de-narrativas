"""Sugestões estratégicas geradas por Claude a partir dos dados agregados."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from anthropic import Anthropic

from app import analytics, db
from app.config import CANDIDATE_BY_ID, settings
from app.models import DataSnapshot, Suggestion, SuggestionsResponse

SYSTEM = (
    "Você é um estrategista de comunicação política digital no Brasil. "
    "Gera recomendações práticas e acionáveis baseadas em dados reais de engajamento e "
    "sentimento de comentários. Responda SEMPRE em JSON válido."
)

PROMPT_TMPL = """Candidato(a): {candidate}

DADOS REAIS (últimos posts no Instagram):
- Total de posts analisados: {total_posts}
- Total de comentários analisados: {total_comments}
- Sentimento médio (-1 a 1): {avg_score}
- Distribuição: {pos} positivos, {neg} negativos, {neu} neutros
- Principais temas dos comentários: {themes}
- Tendência recente do sentimento: {trend}

Gere de 4 a 6 sugestões estratégicas para melhorar a percepção e o engajamento.
Cada sugestão deve ter (em português correto, com acentuação):
- "title": título curto e direto
- "description": explicação da recomendação
- "supporting_data": qual dado acima embasa a sugestão
- "priority": "high" | "medium" | "low"
- "categoria": ex. "Conteúdo", "Engajamento", "Posicionamento", "Crise"
- "acoes_concretas": lista de 2 a 4 ações práticas
- "exemplo_post": exemplo curto de legenda de post
- "publico_alvo": quem essa ação atinge
- "impacto_esperado": resultado esperado

Responda com JSON:
{{"resumo_executivo": "...", "suggestions": [ {{...}} ]}}"""


def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY não configurado")
    return Anthropic(api_key=settings.anthropic_api_key)


def _snapshot() -> DataSnapshot:
    total = db.query_one("select count(*) as n from comments where analyzed_at is not null")
    last = db.query_one("select max(finished_at) as ls from scrape_runs where status='completed'")
    return DataSnapshot(
        total_comments_analyzed=int(total["n"]) if total else 0,
        last_scrape=last["ls"].isoformat() if last and last["ls"] else None,
    )


def generate_suggestions(candidate_id: str | None = None) -> SuggestionsResponse:
    cid = candidate_id if candidate_id in CANDIDATE_BY_ID else "sheila"
    metrics = analytics.build_candidate_metrics(cid)
    themes = analytics._top_themes(cid)
    trend = analytics._trend(cid)
    generated_at = datetime.now(timezone.utc).isoformat()

    if metrics.total_comments == 0:
        return SuggestionsResponse(
            suggestions=[],
            resumo_executivo="Ainda não há comentários analisados para gerar sugestões. Rode um scraping primeiro.",
            generated_at=generated_at,
            data_snapshot=_snapshot(),
        )

    prompt = PROMPT_TMPL.format(
        candidate=CANDIDATE_BY_ID[cid].display_name,
        total_posts=metrics.total_posts,
        total_comments=metrics.total_comments,
        avg_score=metrics.average_sentiment_score,
        pos=metrics.sentiment_distribution.positive,
        neg=metrics.sentiment_distribution.negative,
        neu=metrics.sentiment_distribution.neutral,
        themes=", ".join(f"{t.theme} ({t.count})" for t in themes) or "n/d",
        trend=f"{trend.direction} (delta {trend.delta})",
    )
    try:
        msg = _client().messages.create(
            model=settings.suggestions_model,
            max_tokens=3000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 — sem crédito/chave: degrada com aviso
        return SuggestionsResponse(
            suggestions=[],
            resumo_executivo=(
                "As sugestões geradas por IA estão temporariamente indisponíveis "
                f"(motivo: {str(exc)[:120]}). Os demais painéis continuam funcionando com os "
                "dados coletados. Adicione créditos à API Anthropic para reativar esta seção."
            ),
            generated_at=generated_at,
            data_snapshot=_snapshot(),
        )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].lstrip("json").strip()
    start, end = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[start : end + 1]) if start >= 0 else {"suggestions": []}

    suggestions = []
    for s in data.get("suggestions", []):
        if not isinstance(s, dict) or not s.get("title"):
            continue
        prio = s.get("priority")
        suggestions.append(
            Suggestion(
                title=s.get("title", ""),
                description=s.get("description", ""),
                supporting_data=s.get("supporting_data", ""),
                priority=prio if prio in ("high", "medium", "low") else "medium",
                categoria=s.get("categoria"),
                acoes_concretas=s.get("acoes_concretas"),
                exemplo_post=s.get("exemplo_post"),
                roteiro_video=s.get("roteiro_video"),
                publico_alvo=s.get("publico_alvo"),
                para_quem=s.get("para_quem"),
                impacto_esperado=s.get("impacto_esperado"),
            )
        )
    return SuggestionsResponse(
        suggestions=suggestions,
        resumo_executivo=data.get("resumo_executivo"),
        generated_at=generated_at,
        data_snapshot=_snapshot(),
    )
