"""Análise de sentimento/postura/temas de comentários.

Dois motores:
  - LLM (Claude/Anthropic): mais preciso, requer créditos.
  - Heurística léxica PT-BR: custo zero, determinística, fallback automático.

SENTIMENT_PROVIDER controla: "auto" (default, tenta LLM e cai pra heurística),
"claude" (só LLM) ou "heuristic" (só léxico).
"""
from __future__ import annotations

import json
import re

from anthropic import Anthropic

from app import db
from app.config import settings

# Vocabulário de temas controlado (PT-BR, contexto político)
THEMES = [
    "segurança pública", "saúde", "educação", "economia", "emprego",
    "corrupção", "infraestrutura", "transporte", "meio ambiente", "direitos",
    "religião", "família", "crítica pessoal", "apoio pessoal", "outros",
]

BATCH = 15

# ----------------------------------------------------------------------------
# Motor heurístico (léxico PT-BR) — Code First, zero token
# ----------------------------------------------------------------------------
_POS = {
    "parabéns", "parabens", "obrigado", "obrigada", "apoio", "apoio", "melhor", "ótimo", "otimo",
    "excelente", "sucesso", "abençoe", "abençoa", "força", "forca", "orgulho", "justiça", "justica",
    "bom", "boa", "amo", "amamos", "lindo", "linda", "maravilhoso", "maravilhosa", "top", "gratidão",
    "gratidao", "represent", "guerreira", "guerreiro", "votarei", "voto", "contamos", "verdade",
    "honesto", "honesta", "competente", "trabalho", "trabalhador", "respeito", "admiro", "admiração",
    "merece", "campeã", "campeao", "fenômeno", "show", "incrível", "incrivel", "perfeito", "deus",
    "vamos", "valeu", "ajuda", "ajudou", "feliz", "esperança", "esperanca", "obg", "lider", "líder",
}
_NEG = {
    "vergonha", "mentira", "mentiroso", "ladrão", "ladrao", "ladra", "corrupto", "corrupta", "péssimo",
    "pessimo", "ruim", "horrível", "horrivel", "golpe", "fraude", "palhaço", "palhaco", "vendido",
    "vendida", "descaro", "lixo", "nojo", "nojento", "falso", "falsa", "hipócrita", "hipocrita",
    "decepção", "decepcao", "decepcionado", "traidor", "traidora", "enganação", "enganacao", "picareta",
    "absurdo", "ridículo", "ridiculo", "fraco", "fraca", "incompetente", "covarde", "farsa", "demagogia",
    "oportunista", "interesseiro", "cadê", "cade", "nunca", "pior", "fora", "renuncia", "preso", "cadeia",
    "rouba", "roubou", "roubo", "safado", "safada", "verme", "capacho", "fantoche", "fingindo",
}
_THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "segurança pública": ("seguranç", "seguranc", "polícia", "policia", "bandido", "crime", "violência",
                           "violencia", "arma", "delegad", "assalto", "tráfico", "trafico", "pm"),
    "saúde": ("saúde", "saude", "hospital", "médic", "medic", "sus", "vacina", "posto", "remédio",
              "remedio", "ubs", "doente"),
    "educação": ("educaç", "educac", "escola", "professor", "ensino", "creche", "universidade",
                 "aluno", "merenda"),
    "economia": ("economia", "imposto", "preço", "preco", "salário", "salario", "inflação", "inflacao",
                 "dinheiro público", "verba", "gasto"),
    "emprego": ("emprego", "desemprego", "vaga", "trabalh", "renda", "carteira assinada"),
    "corrupção": ("corrupç", "corrupc", "corrupto", "rouba", "roubo", "propina", "desvio", "lavagem",
                  "fraude", "superfaturad"),
    "infraestrutura": ("asfalto", "buraco", "obra", "saneamento", "esgoto", "rua", "calçada", "calcada",
                       "iluminação", "iluminacao", "praça", "praca"),
    "transporte": ("ônibus", "onibus", "transporte", "metrô", "metro", "passagem", "tarifa", "trânsito",
                   "transito"),
    "meio ambiente": ("meio ambiente", "poluição", "poluicao", "lixo", "árvore", "arvore", "rio",
                      "desmatamento", "enchente"),
    "direitos": ("direitos", "lgbt", "mulher", "racismo", "minoria", "igualdade", "feminis", "aborto"),
    "religião": ("deus", "jesus", "igreja", "cristã", "crista", "cristão", "cristao", "fé", "abençoe",
                 "abençoa", "evangéli", "evangeli", "católic", "catolic", "pastor"),
    "família": ("família", "familia", "filho", "filha", "criança", "crianca", "pais", "mãe", "mae",
                "pai", "lar"),
}
_TOKEN_RE = re.compile(r"[a-záàâãéêíóôõúüç]+", re.IGNORECASE)


def _heuristic_classify(text: str) -> dict:
    low = text.lower()
    tokens = _TOKEN_RE.findall(low)
    tokenset = set(tokens)
    pos = len(tokenset & _POS)
    neg = len(tokenset & _NEG)
    # emojis/sinais simples
    pos += low.count("❤") + low.count("👏") + low.count("🙏") + low.count("💪") + low.count("👍")
    neg += low.count("👎") + low.count("🤬") + low.count("🤮")
    total = pos + neg
    if total == 0:
        sentiment, score, stance = "neutral", 0.0, "neutro"
    else:
        score = round((pos - neg) / total, 3)
        if score > 0.15:
            sentiment, stance = "positive", "apoio"
        elif score < -0.15:
            sentiment, stance = "negative", "contra"
        else:
            sentiment, stance = "neutral", "neutro"
    themes = [t for t, kws in _THEME_KEYWORDS.items() if any(k in low for k in kws)][:3]
    if not themes:
        themes = ["apoio pessoal" if stance == "apoio" else "crítica pessoal" if stance == "contra" else "outros"]
    return {"sentiment": sentiment, "score": score, "stance": stance, "themes": themes}


# ----------------------------------------------------------------------------
# Motor LLM (Claude/Anthropic)
# ----------------------------------------------------------------------------
SYSTEM = (
    "Você é um analista político brasileiro. Classifica comentários de Instagram em posts "
    "de candidatos. Responda SEMPRE em JSON válido, sem texto fora do JSON."
)
PROMPT_TMPL = """Candidato analisado: {candidate}

Para cada comentário, classifique no contexto político brasileiro:
- "sentiment": "positive" | "negative" | "neutral"
- "score": -1.0 (muito negativo) a 1.0 (muito positivo)
- "stance": "apoio" | "contra" | "neutro" (posição EM RELAÇÃO AO CANDIDATO)
- "themes": 1 a 3 temas, APENAS desta lista: {themes}

Considere ironia e gírias. Elogio irônico = negative/contra.

Comentários (JSON): {comments}

Responda array JSON na mesma ordem:
{{"i": <indice>, "sentiment": "...", "score": <num>, "stance": "...", "themes": ["..."]}}"""


def _llm_classify_batch(client: Anthropic, candidate: str, comments: list[dict]) -> list[dict]:
    payload = [{"i": i, "text": c["text"][:600]} for i, c in enumerate(comments)]
    prompt = PROMPT_TMPL.format(
        candidate=candidate, themes=", ".join(THEMES),
        comments=json.dumps(payload, ensure_ascii=False),
    )
    msg = client.messages.create(
        model=settings.sentiment_model, max_tokens=2000, system=SYSTEM,
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
# Orquestração
# ----------------------------------------------------------------------------
def _persist(comment_id: str, res: dict) -> None:
    valid_themes = set(THEMES)
    sentiment = res.get("sentiment") if res.get("sentiment") in ("positive", "negative", "neutral") else "neutral"
    stance = res.get("stance") if res.get("stance") in ("apoio", "contra", "neutro") else "neutro"
    try:
        score = max(-1.0, min(1.0, float(res.get("score", 0))))
    except (TypeError, ValueError):
        score = 0.0
    themes = [t for t in (res.get("themes") or []) if t in valid_themes][:3] or ["outros"]
    db.execute(
        """update comments set sentiment=%(s)s, sentiment_score=%(sc)s, stance=%(st)s,
           themes=%(th)s, analyzed_at=now() where id=%(id)s""",
        {"id": comment_id, "s": sentiment, "sc": score, "st": stance, "th": themes},
    )


def analyze_pending(limit: int = 5000) -> int:
    """Classifica comentários sem análise. Usa LLM se disponível, senão heurística."""
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
                # falha do LLM (sem crédito/auth/etc) → cai pra heurística no resto do run
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
