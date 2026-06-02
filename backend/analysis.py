"""Geração de análise textual em português a partir das previsões."""
from __future__ import annotations

from typing import Dict, List


def build_analysis(escopo: str, alvo: str, uf: str | None,
                   hist_min: int, hist_max: int,
                   ano_inicio: int, ano_fim: int,
                   metricas: List[dict]) -> str:
    """Recebe lista de dicts com chaves: metric, taxa_crescimento_anual_pct,
    confiabilidade, confiabilidade_score, modelo_escolhido, serie, observacoes."""
    lugar = alvo + (f" ({uf})" if uf and escopo == "municipio" else "")
    blocos: List[str] = []

    blocos.append(
        f"**Escopo analisado:** {escopo} — {lugar}. "
        f"Base histórica disponível de {hist_min} a {hist_max}, com horizonte de projeção "
        f"de {ano_inicio} a {ano_fim} ({ano_fim - ano_inicio + 1} anos)."
    )

    # tendências
    tend = []
    for m in metricas:
        nome = {"acidentes": "acidentes", "mortos": "óbitos", "feridos": "feridos"}.get(m["metric"], m["metric"])
        taxa = m["taxa_crescimento_anual_pct"]
        if abs(taxa) < 0.1:
            tend.append(f"{nome} praticamente estáveis (~{taxa:+.2f}% a.a.)")
        elif taxa > 0:
            tend.append(f"**alta** de {nome} a {taxa:+.2f}% ao ano")
        else:
            tend.append(f"**queda** de {nome} de {taxa:+.2f}% ao ano")
    blocos.append("**Tendências projetadas:** " + "; ".join(tend) + ".")

    # comportamento histórico
    descricoes = []
    for m in metricas:
        hist = [p for p in m["serie"] if p["tipo"] == "historico"]
        if len(hist) >= 2:
            ini, fim = hist[0]["valor"], hist[-1]["valor"]
            if ini > 0:
                var = (fim / ini - 1) * 100
                descricoes.append(f"{m['metric']} variaram {var:+.1f}% entre {hist[0]['ano']} e {hist[-1]['ano']}")
    if descricoes:
        blocos.append("**Comportamento histórico:** " + "; ".join(descricoes) + ".")

    # projeção
    proj_lines = []
    for m in metricas:
        fut = [p for p in m["serie"] if p["tipo"] == "previsao"]
        if not fut:
            continue
        last = fut[-1]
        proj_lines.append(
            f"{m['metric']} em {last['ano']}: ~{round(last['valor']):,} "
            f"(IC95%: {round(last['lower']):,}–{round(last['upper']):,}; modelo: {m['modelo_escolhido']})"
            .replace(",", ".")
        )
    if proj_lines:
        blocos.append("**Projeção final do horizonte:** " + "; ".join(proj_lines) + ".")

    # confiabilidade
    confs = [m["confiabilidade"] for m in metricas]
    pior = "baixa" if "baixa" in confs else ("media" if "media" in confs else "alta")
    if pior == "alta":
        msg = "A confiabilidade estatística geral é **alta** dentro do horizonte solicitado."
    elif pior == "media":
        msg = "A confiabilidade é **média**: as bandas de incerteza são consideráveis e tendências de longo prazo devem ser lidas como cenários."
    else:
        msg = ("A confiabilidade estatística é **baixa**. Projeções a esta distância do histórico "
               "carregam incerteza elevada — trate os números como ordens de grandeza, não previsões pontuais.")
    blocos.append("**Confiabilidade:** " + msg)

    # limitações
    limits = [
        "As séries cobrem apenas dados agregados anualmente; choques estruturais (mudanças regulatórias, novas rodovias, frota elétrica, automação) não são modelados.",
        "Quanto mais distante o ano-alvo, maior a banda de confiança — extrapolações além de 30–40 anos do último dado têm valor apenas exploratório.",
        "Os modelos são reescolhidos por MAPE em validação holdout, mas amostras pequenas favorecem modelos mais simples.",
    ]
    blocos.append("**Limitações:** " + " ".join(limits))

    return "\n\n".join(blocos)
