"""FastAPI app — endpoints com rastreabilidade completa e exportação.

Endpoints:
- GET  /api/health
- GET  /api/options
- POST /api/forecast    → resultado + dados_utilizados (metadados + amostra)
- POST /api/export      → CSV/JSON dos registros usados na análise
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from analysis import build_analysis
from data_loader import Datasets, load_all
from forecasting import fit_and_forecast

app = FastAPI(title="RoadCast API", version="2.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DATA: Optional[Datasets] = None
LOAD_ERROR: Optional[str] = None
METRICS = ["acidentes", "mortos", "feridos"]

REGIOES_UF = {
    "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Centro-Oeste": ["DF", "GO", "MT", "MS"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"],
}


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
        "ano_max_completo": DATA.ano_max_completo if DATA else None,
        "anos_parciais": DATA.anos_parciais if DATA else [],
        "fontes": DATA.fontes if DATA else [],
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
        "ano_max_completo": DATA.ano_max_completo,
        "anos_parciais": DATA.anos_parciais,
        "fontes": DATA.fontes,
    }


class ForecastReq(BaseModel):
    escopo: str = Field(pattern="^(municipio|uf|regiao)$")
    alvo: str
    uf: Optional[str] = None
    ano_inicio: int
    ano_fim: int


def _slice_history(req: ForecastReq) -> pd.DataFrame:
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
        return df
    if req.escopo == "uf":
        df = DATA.uf[DATA.uf["uf"] == req.alvo.upper()]
        if df.empty:
            raise HTTPException(404, f"UF '{req.alvo}' não encontrada.")
        return df
    df = DATA.regiao[DATA.regiao["regiao"].str.lower() == req.alvo.lower()]
    if df.empty:
        raise HTTPException(404, f"Região '{req.alvo}' não encontrada.")
    return df


def _resumo_estatistico(df: pd.DataFrame, cols: List[str]) -> dict:
    out = {}
    for c in cols:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            if not s.empty:
                out[c] = {
                    "soma": int(s.sum()),
                    "media": round(float(s.mean()), 2),
                    "mediana": round(float(s.median()), 2),
                    "min": int(s.min()),
                    "max": int(s.max()),
                }
    return out


@app.post("/api/forecast")
def forecast(req: ForecastReq):
    if DATA is None:
        raise HTTPException(503, f"Dados não carregados: {LOAD_ERROR}")
    if req.ano_fim < req.ano_inicio:
        raise HTTPException(400, "ano_fim deve ser >= ano_inicio.")

    hist = _slice_history(req)
    cols_metricas = [c for c in METRICS if c in hist.columns]

    metricas_out = []
    anos_excluidos_global: set = set()
    anos_treino_global: set = set()
    for metric in cols_metricas:
        sub = hist[["ano", metric]].copy()
        f = fit_and_forecast(sub, metric, req.ano_inicio, req.ano_fim,
                             anos_parciais=DATA.anos_parciais)
        anos_excluidos_global.update(f.anos_excluidos)
        anos_treino_global.update(f.anos_treino)
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

    # ---- Ranking ----
    ranking = None
    if req.escopo == "uf":
        muns = DATA.municipio[
            (DATA.municipio["uf"] == req.alvo.upper())
            & (~DATA.municipio["ano"].isin(DATA.anos_parciais))
        ]
        agg = (muns.groupby("municipio")["acidentes"].sum()
               .sort_values(ascending=False).head(15))
        ranking = [{"nome": str(k), "valor": float(v), "metric": "acidentes"}
                   for k, v in agg.items()]
    elif req.escopo == "regiao":
        ufs = REGIOES_UF.get(req.alvo, [])
        sub = DATA.uf[DATA.uf["uf"].isin(ufs)
                      & (~DATA.uf["ano"].isin(DATA.anos_parciais))]
        agg = sub.groupby("uf")["acidentes"].sum().sort_values(ascending=False)
        ranking = [{"nome": str(k), "valor": float(v), "metric": "acidentes"}
                   for k, v in agg.items()]

    # ---- Heatmap causas (top 8, excluindo anos parciais) ----
    heatmap = None
    if not DATA.causa.empty:
        cau = DATA.causa[~DATA.causa["ano"].isin(DATA.anos_parciais)]
        top_cat = (cau.groupby("causa_acidente")["acidentes"].sum()
                   .nlargest(8).index.tolist())
        sub = cau[cau["causa_acidente"].isin(top_cat)]
        heatmap = [{"ano": int(r["ano"]), "categoria": str(r["causa_acidente"]),
                    "valor": float(r["acidentes"])} for _, r in sub.iterrows()]

    # ---- Rastreabilidade: dados utilizados ----
    total_registros = int(len(hist))
    amostra = hist.sort_values("ano").head(50).to_dict(orient="records")
    dados_utilizados = {
        "total_registros": total_registros,
        "periodo": {"inicio": int(hist["ano"].min()), "fim": int(hist["ano"].max())},
        "fontes": DATA.fontes,
        "filtros_aplicados": {
            "escopo": req.escopo, "alvo": req.alvo, "uf": req.uf,
        },
        "colunas_utilizadas": ["ano"] + cols_metricas,
        "anos_excluidos_do_treino": sorted(anos_excluidos_global),
        "motivo_exclusao": (
            "Anos com coleta parcial (totais nacionais muito abaixo da mediana "
            "dos 3 anos anteriores) — excluídos para não distorcer a tendência."
            if anos_excluidos_global else None
        ),
        "anos_treino": sorted(anos_treino_global),
        "resumo_estatistico": _resumo_estatistico(hist, cols_metricas),
        "amostra": amostra,
    }

    analise = build_analysis(
        escopo=req.escopo, alvo=req.alvo, uf=req.uf,
        hist_min=int(hist["ano"].min()), hist_max=int(hist["ano"].max()),
        ano_inicio=req.ano_inicio, ano_fim=req.ano_fim,
        metricas=metricas_out,
        total_registros=total_registros,
        fontes=DATA.fontes,
        anos_excluidos=sorted(anos_excluidos_global),
    )

    return {
        "escopo": req.escopo, "alvo": req.alvo, "uf": req.uf,
        "ano_inicio": req.ano_inicio, "ano_fim": req.ano_fim,
        "historico_min": int(hist["ano"].min()),
        "historico_max": int(hist["ano"].max()),
        "metricas": metricas_out,
        "analise_textual": analise,
        "ranking": ranking,
        "heatmap": heatmap,
        "dados_utilizados": dados_utilizados,
        "gerado_em": datetime.utcnow().isoformat() + "Z",
    }


# ---------------- Export ----------------

class ExportReq(BaseModel):
    escopo: str = Field(pattern="^(municipio|uf|regiao)$")
    alvo: str
    uf: Optional[str] = None
    formato: str = Field(default="csv", pattern="^(csv|json)$")
    amostra: Optional[int] = None  # None = tudo


@app.post("/api/export")
def export(req: ExportReq):
    if DATA is None:
        raise HTTPException(503, f"Dados não carregados: {LOAD_ERROR}")
    # reuso da lógica de slice
    fake = ForecastReq(escopo=req.escopo, alvo=req.alvo, uf=req.uf,
                       ano_inicio=DATA.ano_min, ano_fim=DATA.ano_max)
    df = _slice_history(fake).sort_values("ano").reset_index(drop=True)
    if req.amostra and req.amostra > 0:
        df = df.head(req.amostra)

    meta = {
        "_fonte": " + ".join(DATA.fontes),
        "_gerado_em": datetime.utcnow().isoformat() + "Z",
        "_filtros": {"escopo": req.escopo, "alvo": req.alvo, "uf": req.uf},
        "_total_registros": int(len(df)),
        "_anos_parciais_na_base": DATA.anos_parciais,
    }

    if req.formato == "json":
        payload = {"metadata": meta, "registros": df.to_dict(orient="records")}
        return StreamingResponse(
            io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="roadcast_{req.escopo}_{req.alvo}.json"'},
        )

    # CSV: cabeçalho com metadados em comentários
    buf = io.StringIO()
    for k, v in meta.items():
        buf.write(f"# {k}: {json.dumps(v, ensure_ascii=False)}\n")
    df.to_csv(buf, index=False, sep=";")
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="roadcast_{req.escopo}_{req.alvo}.csv"'},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
