"""Análise de sentimento/postura/temas de comentários via Claude (Anthropic)."""
from __future__ import annotations

import json

from anthropic import Anthropic

from app import db
from app.config import settings

# Vocabulário de temas controlado (PT-BR, contexto político) — mantém a agregação consistente
THEMES = [
    "segurança pública", "saúde", "educação", "economia", "emprego",
    "corrupção", "infraestrutura", "transporte", "meio ambiente", "direitos",
    "religião", "família", "crítica pessoal", "apoio pessoal", "outros",
]

BATCH = 15

SYSTEM = (
    "Você é um analista político brasileiro. Classifica comentários de Instagram em posts "
    "de candidatos. Responda SEMPRE em JSON válido, sem texto fora do JSON."
)

PROMPT_TMPL = """Candidato analisado: {candidate}

Para cada comentário abaixo, classifique considerando o contexto político brasileiro:
- "sentiment": "positive" | "negative" | "neutral" (tom emocional do comentário)
- "score": número de -1.0 (muito negativo) a 1.0 (muito positivo)
- "stance": "apoio" | "contra" | "neutro" (posição do autor EM RELAÇÃO AO CANDIDATO)
- "themes": lista de 1 a 3 temas, ESCOLHIDOS APENAS desta lista: {themes}

Considere ironia, sarcasmo e gírias brasileiras. Comentário elogioso mas irônico = negative/contra.

Comentários (JSON):
{comments}

Responda com um array JSON na mesma ordem, cada item:
{{"i": <indice>, "sentiment": "...", "score": <num>, "stance": "...", "themes": ["..."]}}"""


def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY não configurado")
    return Anthropic(api_key=settings.anthropic_api_key)


def _classify_batch(client: Anthropic, candidate: str, comments: list[dict]) -> list[dict]:
    payload = [{"i": idx, "text": c["text"][:600]} for idx, c in enumerate(comments)]
    prompt = PROMPT_TMPL.format(
        candidate=candidate,
        themes=", ".join(THEMES),
        comments=json.dumps(payload, ensure_ascii=False),
    )
    msg = client.messages.create(
        model=settings.sentiment_model,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    # remove cercas de código se houver
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].lstrip("json").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("["), raw.rfind("]")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def analyze_pending(limit: int = 2000) -> int:
    """Classifica comentários sem análise. Retorna quantos foram analisados."""
    rows = db.query_all(
        """
        select c.id, c.text, cand.display_name as candidate
        from comments c
        join candidates cand on cand.id = c.candidate_id
        where c.analyzed_at is null and length(trim(c.text)) > 0
        order by c.commented_at desc nulls last
        limit %(lim)s
        """,
        {"lim": limit},
    )
    if not rows:
        return 0

    client = _client()
    valid_themes = set(THEMES)
    analyzed = 0

    for start in range(0, len(rows), BATCH):
        batch = rows[start : start + BATCH]
        candidate = batch[0]["candidate"]
        # agrupa por candidato dentro do batch para dar contexto correto
        try:
            results = _classify_batch(client, candidate, batch)
        except Exception:
            continue  # batch problemático não trava o resto
        by_index = {r.get("i"): r for r in results if isinstance(r, dict)}
        for idx, row in enumerate(batch):
            res = by_index.get(idx)
            if not res:
                continue
            sentiment = res.get("sentiment") if res.get("sentiment") in ("positive", "negative", "neutral") else "neutral"
            stance = res.get("stance") if res.get("stance") in ("apoio", "contra", "neutro") else "neutro"
            try:
                score = max(-1.0, min(1.0, float(res.get("score", 0))))
            except (TypeError, ValueError):
                score = 0.0
            themes = [t for t in (res.get("themes") or []) if t in valid_themes][:3] or ["outros"]
            db.execute(
                """
                update comments set sentiment=%(s)s, sentiment_score=%(sc)s,
                    stance=%(st)s, themes=%(th)s, analyzed_at=now()
                where id=%(id)s
                """,
                {"id": row["id"], "s": sentiment, "sc": score, "st": stance, "th": themes},
            )
            analyzed += 1
    return analyzed
