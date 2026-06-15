"""Geração de análise textual em PT-BR — refere explicitamente a amostra usada
e as fontes (RENAEST + DATATRAN/PRF), sem mencionar limitações herdadas do
modelo antigo (apenas-PRF/rodovias federais)."""
from __future__ import annotations

from typing import List, Optional


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def build_analysis(
    escopo: str, alvo: str, uf: Optional[str],
    hist_min: int, hist_max: int,
    ano_inicio: int, ano_fim: int,
    metricas: List[dict],
    total_registros: int,
    fontes: List[str],
    anos_excluidos: List[int],
) -> str:
    lugar = alvo + (f" ({uf})" if uf and escopo == "municipio" else "")
    blocos: List[str] = []

    fontes_txt = " + ".join(fontes) if fontes else "base consolidada"
    blocos.append(
        f"**Esta análise foi realizada com base em {_fmt(total_registros)} registros** "
        f"de acidentes no período de **{hist_min} a {hist_max}**, oriundos da base "
        f"consolidada **{fontes_txt}**, para o escopo **{escopo} — {lugar}**. "
        f"Horizonte de projeção: **{ano_inicio} a {ano_fim}** "
        f"({ano_fim - ano_inicio + 1} anos)."
    )

    if anos_excluidos:
        blocos.append(
            f"**Tratamento de dados:** o(s) ano(s) {anos_excluidos} foi(ram) "
            f"identificado(s) como **parcial(is)** (coleta ainda em andamento, "
            f"total muito abaixo da mediana recente) e portanto **excluído(s) do "
            f"treino dos modelos** para não introduzir viés de tendência decrescente artificial."
        )

    # Tendências
    tend = []
    for m in metricas:
        nome = {"acidentes": "acidentes", "mortos": "óbitos", "feridos": "feridos"}.get(
            m["metric"], m["metric"])
        taxa = m["taxa_crescimento_anual_pct"]
        if abs(taxa) < 0.1:
            tend.append(f"{nome} praticamente estáveis (~{taxa:+.2f}% a.a.)")
        elif taxa > 0:
            tend.append(f"alta de {nome} a {taxa:+.2f}% ao ano")
        else:
            tend.append(f"queda de {nome} de {taxa:+.2f}% ao ano")
    if tend:
        blocos.append("**Tendências projetadas:** " + "; ".join(tend) + ".")

    # Histórico (excluindo pontos parciais)
    descricoes = []
    for m in metricas:
        hist = [p for p in m["serie"] if p["tipo"] == "historico"]
        if len(hist) >= 2:
            ini, fim = hist[0]["valor"], hist[-1]["valor"]
            if ini > 0:
                var = (fim / ini - 1) * 100
                descricoes.append(
                    f"{m['metric']} variaram {var:+.1f}% entre {hist[0]['ano']} e {hist[-1]['ano']}"
                )
    if descricoes:
        blocos.append("**Comportamento histórico observado:** " + "; ".join(descricoes) + ".")

    # Projeção final
    proj_lines = []
    for m in metricas:
        fut = [p for p in m["serie"] if p["tipo"] == "previsao"]
        if not fut:
            continue
        last = fut[-1]
        proj_lines.append(
            f"{m['metric']} em {last['ano']}: ~{_fmt(last['valor'])} "
            f"(IC95%: {_fmt(last['lower'])}–{_fmt(last['upper'])}; modelo: {m['modelo_escolhido']})"
        )
    if proj_lines:
        blocos.append("**Projeção no final do horizonte:** " + "; ".join(proj_lines) + ".")
    else:
        blocos.append(
            "**Projeção:** não foi possível gerar projeção estatisticamente "
            "confiável para este recorte; a análise apresenta apenas a série observada."
        )

    # Confiabilidade
    confs = [m["confiabilidade"] for m in metricas]
    pior = "baixa" if "baixa" in confs else ("media" if "media" in confs else "alta")
    if pior == "alta":
        msg = "A confiabilidade estatística geral é **alta** dentro do horizonte solicitado."
    elif pior == "media":
        msg = ("A confiabilidade é **média**: bandas de incerteza são consideráveis e "
               "tendências de longo prazo devem ser lidas como cenários, não previsões pontuais.")
    else:
        msg = ("A confiabilidade estatística é **baixa**. A amostra disponível ou o "
               "horizonte solicitado limitam a precisão — interprete como ordem de grandeza.")
    blocos.append("**Confiabilidade:** " + msg)

    blocos.append(
        "**Rastreabilidade:** os registros exatos usados estão listados na seção "
        "*Dados Utilizados nesta Análise* e podem ser baixados em CSV/JSON pelo botão de exportação."
    )

    return "\n\n".join(blocos)
