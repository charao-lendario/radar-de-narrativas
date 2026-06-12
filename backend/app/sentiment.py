"""Análise de sentimento/postura/temas de comentários.

PRINCÍPIO CENTRAL (contexto político):
  sentiment/score medem FAVORABILIDADE AO CANDIDATO — não a emoção bruta.
  - Crítica AO candidato (reclama dele, "não devia postar", ataca caráter) → negativo
  - Indignação/revolta COM O TEMA do post (vídeo forte) → engajamento a favor → positivo/neutro
  - Ataque a TERCEIROS (adversário, bandido) → não conta contra o candidato → neutro/positivo
  - Elogio/apoio → positivo

Campos: sentiment (favorabilidade), score (-1..1), stance (apoio/contra/neutro),
        target (candidato|tema|terceiro|nenhum), themes.

Dois motores: LLM (Claude) e heurística léxica (fallback). SENTIMENT_PROVIDER controla.
"""
from __future__ import annotations

import json
import re

from anthropic import Anthropic

from app import db
from app.config import settings

THEMES = [
    "segurança pública", "saúde", "educação", "economia", "emprego",
    "corrupção", "infraestrutura", "transporte", "meio ambiente", "direitos",
    "religião", "família", "crítica pessoal", "apoio pessoal", "outros",
]
TARGETS = ["candidato", "tema", "terceiro", "nenhum"]
BATCH = 15

# ----------------------------------------------------------------------------
# Motor LLM (Claude)
# ----------------------------------------------------------------------------
SYSTEM = (
    "Você é um analista político brasileiro especialista em opinião pública. "
    "Classifica comentários de Instagram em posts de candidatos com precisão sobre "
    "PARA QUEM a emoção é direcionada. Responde SEMPRE em JSON válido."
)

PROMPT_TMPL = """Candidato(a) do post: {candidate}

Classifique cada comentário. O ponto MAIS IMPORTANTE é distinguir o ALVO da emoção:

REGRA DE OURO — "sentiment" e "score" medem FAVORABILIDADE AO CANDIDATO, não a emoção bruta:
• Crítica/ataque AO CANDIDATO (reclama dele, diz que não devia ter postado, questiona
  caráter/competência, xinga o candidato) → sentiment "negative", stance "contra", target "candidato".
• INDIGNAÇÃO/REVOLTA COM O TEMA do post (o vídeo mostra algo forte/chocante e a pessoa está
  revoltada COM A SITUAÇÃO, não com o candidato) → isso é ENGAJAMENTO A FAVOR →
  sentiment "positive" ou "neutral", stance "apoio" ou "neutro", target "tema". NUNCA "negative".
• Ataque/raiva a TERCEIROS (adversário político, bandido, governo, outra pessoa) → não conta contra
  o candidato → sentiment "neutral"/"positive", target "terceiro".
• Elogio/apoio ao candidato → sentiment "positive", stance "apoio", target "candidato".
• Comentário neutro, dúvida, off-topic, emoji solto → sentiment "neutral", target "nenhum".

Campos por comentário:
- "sentiment": "positive" | "negative" | "neutral"  (favorabilidade AO CANDIDATO)
- "score": -1.0 (muito desfavorável ao candidato) a 1.0 (muito favorável)
- "stance": "apoio" | "contra" | "neutro"
- "target": "candidato" | "tema" | "terceiro" | "nenhum"
- "themes": 1 a 3, APENAS desta lista: {themes}

EXEMPLOS:
- "Que vergonha, não devia ter postado isso" → negative, contra, candidato
- "Que absurdo o que mostraram! Revoltante! Parabéns por denunciar" → positive, apoio, tema
- "Esses bandidos têm que ser presos, que ódio!" → neutral, neutro, terceiro
- "Parabéns delegada, sempre defendendo as crianças ❤️" → positive, apoio, candidato
- "kkk mais um político querendo aparecer" → negative, contra, candidato
- "Fico indignada com o que acontece no Brasil 😢" → neutral, neutro, tema

Considere ironia e sarcasmo (elogio irônico ao candidato = negative/contra).

Comentários (JSON): {comments}

Responda um array JSON, mesma ordem:
{{"i": <indice>, "sentiment": "...", "score": <num>, "stance": "...", "target": "...", "themes": ["..."]}}"""


def _llm_classify_batch(client: Anthropic, candidate: str, comments: list[dict]) -> list[dict]:
    payload = [{"i": i, "text": c["text"][:600]} for i, c in enumerate(comments)]
    prompt = PROMPT_TMPL.format(
        candidate=candidate, themes=", ".join(THEMES),
        comments=json.dumps(payload, ensure_ascii=False),
    )
    msg = client.messages.create(
        model=settings.sentiment_model, max_tokens=2500, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].lstrip("json").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        s, e = raw.find("["), raw.rfind("]")
        if s >= 0 and e > s:
            return json.loads(raw[s : e + 1])
        raise


# ----------------------------------------------------------------------------
# Motor heurístico (fallback) — conservador: só marca negativo se for claramente
# crítica ao candidato. Não detecta alvo com precisão, então evita falso-negativo.
# ----------------------------------------------------------------------------
_ANTI_CANDIDATE = {
    "vergonha", "mentiroso", "mentirosa", "corrupto", "corrupta", "ladrão", "ladra", "ladrao",
    "incompetente", "palhaço", "palhaça", "palhaco", "hipócrita", "hipocrita", "demagogo", "demagoga",
    "oportunista", "picareta", "vendido", "vendida", "fraude", "farsa", "covarde", "traidor", "traidora",
    "nojo", "nojento", "nojenta", "ridículo", "ridicula", "ridícula", "fraco", "fraca", "verme",
    "capacho", "fantoche", "aparecer", "aparecendo", "circo", "decepção", "decepcao", "fora",
}
_PRO_CANDIDATE = {
    "parabéns", "parabens", "apoio", "obrigado", "obrigada", "melhor", "ótima", "otima", "ótimo",
    "excelente", "guerreira", "guerreiro", "orgulho", "admiro", "competente", "honesta", "honesto",
    "votarei", "voto", "conte", "representa", "amo", "deus", "abençoe", "abençoa", "força", "forca",
    "respeito", "merece", "lindo", "linda", "maravilhosa", "maravilhoso", "gratidão", "gratidao",
}
_TOKEN_RE = re.compile(r"[a-záàâãéêíóôõúüç]+", re.IGNORECASE)


def _heuristic_classify(text: str) -> dict:
    low = text.lower()
    tokens = set(_TOKEN_RE.findall(low))
    pro = len(tokens & _PRO_CANDIDATE) + low.count("❤") + low.count("🙏") + low.count("👏")
    anti = len(tokens & _ANTI_CANDIDATE)
    if anti > pro and anti > 0:
        return {"sentiment": "negative", "score": -0.6, "stance": "contra", "target": "candidato", "themes": ["crítica pessoal"]}
    if pro > 0 and pro >= anti:
        return {"sentiment": "positive", "score": 0.6, "stance": "apoio", "target": "candidato", "themes": ["apoio pessoal"]}
    return {"sentiment": "neutral", "score": 0.0, "stance": "neutro", "target": "nenhum", "themes": ["outros"]}


# ----------------------------------------------------------------------------
# Orquestração
# ----------------------------------------------------------------------------
def _persist(comment_id: str, res: dict) -> None:
    valid_themes = set(THEMES)
    sentiment = res.get("sentiment") if res.get("sentiment") in ("positive", "negative", "neutral") else "neutral"
    stance = res.get("stance") if res.get("stance") in ("apoio", "contra", "neutro") else "neutro"
    target = res.get("target") if res.get("target") in TARGETS else "nenhum"
    try:
        score = max(-1.0, min(1.0, float(res.get("score", 0))))
    except (TypeError, ValueError):
        score = 0.0
    themes = [t for t in (res.get("themes") or []) if t in valid_themes][:3] or ["outros"]
    db.execute(
        """update comments set sentiment=%(s)s, sentiment_score=%(sc)s, stance=%(st)s,
           target=%(tg)s, themes=%(th)s, analyzed_at=now() where id=%(id)s""",
        {"id": comment_id, "s": sentiment, "sc": score, "st": stance, "tg": target, "th": themes},
    )


def analyze_pending(limit: int = 5000) -> int:
    rows = db.query_all(
        """
        select c.id, c.text, cand.display_name as candidate
        from comments c join candidates cand on cand.id = c.candidate_id
        where c.analyzed_at is null and length(trim(c.text)) > 0
        order by c.commented_at desc nulls last limit %(lim)s
        """,
        {"lim": limit},
    )
    if not rows:
        return 0

    provider = settings.sentiment_provider.lower()
    use_llm = provider in ("auto", "claude") and bool(settings.anthropic_api_key)
    client = Anthropic(api_key=settings.anthropic_api_key) if use_llm else None
    analyzed = 0

    for start in range(0, len(rows), BATCH):
        batch = rows[start : start + BATCH]
        results_by_index: dict[int, dict] = {}
        if use_llm:
            try:
                raw = _llm_classify_batch(client, batch[0]["candidate"], batch)
                results_by_index = {r.get("i"): r for r in raw if isinstance(r, dict)}
            except Exception as exc:  # noqa: BLE001
                if provider == "auto":
                    print(f"[sentiment] LLM indisponível ({str(exc)[:120]}); usando heurística")
                    use_llm = False
                else:
                    print(f"[sentiment] erro LLM: {str(exc)[:160]}")
                    continue
        for idx, row in enumerate(batch):
            res = results_by_index.get(idx) if use_llm else _heuristic_classify(row["text"])
            if res is None:
                res = _heuristic_classify(row["text"])
            _persist(row["id"], res)
            analyzed += 1
    return analyzed
