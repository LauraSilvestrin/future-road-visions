"""FastAPI app: expõe /api/options, /api/forecast e /api/health."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from analysis import build_analysis
from data_loader import Datasets, load_all
from forecasting import fit_and_forecast

app = FastAPI(title="RoadCast API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA: Optional[Datasets] = None
LOAD_ERROR: Optional[str] = None


@app.on_event("startup")
def _startup() -> None:
    global DATA, LOAD_ERROR
    try:
        DATA = load_all()
    except Exception as e:  # noqa: BLE001
        LOAD_ERROR = str(e)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_loaded": DATA is not None,
        "error": LOAD_ERROR,
        "ano_min": DATA.ano_min if DATA else None,
        "ano_max": DATA.ano_max if DATA else None,
    }


@app.get("/api/options")
def options():
    if DATA is None:
        raise HTTPException(503, f"Dados não carregados: {LOAD_ERROR}")
    return {
        "ufs": DATA.ufs,
        "regioes": DATA.regioes,
        "municipios_por_uf": DATA.municipios_por_uf(),
        "ano_min": DATA.ano_min,
        "ano_max": DATA.ano_max,
    }


class ForecastReq(BaseModel):
    escopo: str = Field(pattern="^(municipio|uf|regiao)$")
    alvo: str
    uf: Optional[str] = None
    ano_inicio: int
    ano_fim: int


METRICS = ["acidentes", "mortos", "feridos"]


def _slice_history(req: ForecastReq) -> tuple[pd.DataFrame, str]:
    assert DATA is not None
    if req.escopo == "municipio":
        if not req.uf:
            raise HTTPException(400, "UF é obrigatória para escopo município.")
        df = DATA.municipio[
            (DATA.municipio["uf"] == req.uf.upper())
            & (DATA.municipio["municipio"].str.lower() == req.alvo.lower())
        ]
        if df.empty:
            raise HTTPException(404, f"Município '{req.alvo}/{req.uf}' não encontrado.")
        return df, "municipio"
    if req.escopo == "uf":
        df = DATA.uf[DATA.uf["uf"] == req.alvo.upper()]
        if df.empty:
            raise HTTPException(404, f"UF '{req.alvo}' não encontrada.")
        return df, "uf"
    df = DATA.regiao[DATA.regiao["regiao"].str.lower() == req.alvo.lower()]
    if df.empty:
        raise HTTPException(404, f"Região '{req.alvo}' não encontrada.")
    return df, "regiao"


@app.post("/api/forecast")
def forecast(req: ForecastReq):
    if DATA is None:
        raise HTTPException(503, f"Dados não carregados: {LOAD_ERROR}")
    if req.ano_fim < req.ano_inicio:
        raise HTTPException(400, "ano_fim deve ser >= ano_inicio.")
    hist, _ = _slice_history(req)

    metricas_out = []
    for metric in METRICS:
        if metric not in hist.columns:
            continue
        sub = hist[["ano", metric]].copy()
        f = fit_and_forecast(sub, metric, req.ano_inicio, req.ano_fim)
        metricas_out.append({
            "metric": metric,
            "serie": f.serie,
            "modelo_escolhido": f.modelo_escolhido,
            "comparacao_modelos": f.comparacao,
            "taxa_crescimento_anual_pct": f.taxa_crescimento_anual_pct,
            "confiabilidade": f.confiabilidade,
            "confiabilidade_score": f.confiabilidade_score,
            "observacoes": f.observacoes,
        })

    # Ranking e heatmap só fazem sentido para escopo UF/Região
    ranking: List[dict] | None = None
    heatmap: List[dict] | None = None

    if req.escopo == "uf":
        # ranking: municípios dessa UF previstos para o ano_fim em "acidentes"
        muns = DATA.municipio[DATA.municipio["uf"] == req.alvo.upper()]
        out = []
        for mun, sub in muns.groupby("municipio"):
            try:
                fc = fit_and_forecast(sub[["ano", "acidentes"]], "acidentes",
                                      req.ano_fim, req.ano_fim)
                last = fc.serie[-1]
                out.append({"nome": str(mun), "valor": last["valor"], "metric": "acidentes"})
            except Exception:  # noqa: BLE001
                continue
        out.sort(key=lambda r: r["valor"], reverse=True)
        ranking = out[:15]

    if req.escopo == "regiao":
        # ranking: UFs da região
        # mapeamento simples região -> UFs
        regioes_uf = {
            "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
            "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
            "Centro-Oeste": ["DF", "GO", "MT", "MS"],
            "Sudeste": ["ES", "MG", "RJ", "SP"],
            "Sul": ["PR", "RS", "SC"],
        }
        ufs = regioes_uf.get(req.alvo, [])
        out = []
        for u in ufs:
            sub = DATA.uf[DATA.uf["uf"] == u]
            if sub.empty:
                continue
            try:
                fc = fit_and_forecast(sub[["ano", "acidentes"]], "acidentes",
                                      req.ano_fim, req.ano_fim)
                out.append({"nome": u, "valor": fc.serie[-1]["valor"], "metric": "acidentes"})
            except Exception:  # noqa: BLE001
                continue
        out.sort(key=lambda r: r["valor"], reverse=True)
        ranking = out

    # heatmap: causa x ano (sempre, é nacional)
    if not DATA.causa.empty:
        top_cat = (DATA.causa.groupby("causa_acidente")["acidentes"].sum()
                   .nlargest(8).index.tolist())
        sub = DATA.causa[DATA.causa["causa_acidente"].isin(top_cat)]
        heatmap = [{"ano": int(r["ano"]), "categoria": str(r["causa_acidente"]),
                    "valor": float(r["acidentes"])} for _, r in sub.iterrows()]

    analise = build_analysis(
        escopo=req.escopo, alvo=req.alvo, uf=req.uf,
        hist_min=int(hist["ano"].min()), hist_max=int(hist["ano"].max()),
        ano_inicio=req.ano_inicio, ano_fim=req.ano_fim, metricas=metricas_out,
    )

    return {
        "escopo": req.escopo,
        "alvo": req.alvo,
        "uf": req.uf,
        "ano_inicio": req.ano_inicio,
        "ano_fim": req.ano_fim,
        "historico_min": int(hist["ano"].min()),
        "historico_max": int(hist["ano"].max()),
        "metricas": metricas_out,
        "analise_textual": analise,
        "ranking": ranking,
        "heatmap": heatmap,
        "gerado_em": datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
