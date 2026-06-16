"""Engine de previsão revisada para os dados RENAEST + DATATRAN/PRF.

Mudanças em relação à versão anterior (auditoria 2026):
- Anos parciais (coleta incompleta) são EXCLUÍDOS do treino — antes puxavam
  a tendência para zero artificialmente.
- Removida a feature quadrática (ano-base)² em RF/XGBoost: extrapolava para
  valores negativos / zero em horizontes longos. Mantida apenas tendência
  linear + log, e damping para anos distantes.
- Predições são limitadas (clip) ao intervalo [0.4·min_hist, 2.5·max_hist]
  para evitar tendências artificiais a zero ou explosões irreais.
- Quando há <5 anos de histórico ÚTIL, retornamos apenas análise histórica
  (média + variação observada), sem projeção — confiabilidade marcada baixa.
- Banda de incerteza usa resíduos + sqrt(distância) e nunca menor que 10%
  do valor previsto.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

MIN_ANOS_TREINO = 5
DAMPING = 0.85  # damping para evitar explosão da tendência em horizontes longos


@dataclass
class ModelResult:
    modelo: str
    mae: float
    rmse: float
    mape: float
    fitted: object


@dataclass
class Forecast:
    serie: List[dict]
    modelo_escolhido: str
    comparacao: List[Dict[str, float | str]]
    taxa_crescimento_anual_pct: float
    confiabilidade: str
    confiabilidade_score: float
    observacoes: List[str]
    anos_excluidos: List[int]  # anos parciais removidos do treino
    anos_treino: List[int]
    auditoria: Optional[Dict[str, Any]] = None


# ---------------- modelos ----------------

def _train_prophet(years: np.ndarray, values: np.ndarray):
    try:
        from prophet import Prophet
    except Exception:
        return None
    df = pd.DataFrame({
        "ds": pd.to_datetime(years.astype(int).astype(str) + "-01-01"),
        "y": values,
    })
    m = Prophet(
        yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False,
        changepoint_prior_scale=0.02, interval_width=0.8,
    )
    m.fit(df)

    def predict(target_years: List[int]) -> np.ndarray:
        fut = pd.DataFrame({"ds": pd.to_datetime([f"{y}-01-01" for y in target_years])})
        out = m.predict(fut)
        return out["yhat"].clip(lower=0).to_numpy()

    return predict


def _train_arima(years: np.ndarray, values: np.ndarray):
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except Exception:
        return None
    best, best_aic = None, float("inf")
    for order in [(1, 1, 1), (2, 1, 1), (1, 1, 0), (0, 1, 1)]:
        try:
            m = ARIMA(values, order=order).fit()
            if m.aic < best_aic:
                best_aic, best = m.aic, m
        except Exception:
            continue
    if best is None:
        return None
    last_year = int(years.max())

    def predict(target_years: List[int]) -> np.ndarray:
        in_hist = {int(y): i for i, y in enumerate(years)}
        future = sorted(y for y in target_years if y > last_year)
        steps = (max(future) - last_year) if future else 0
        fc = best.forecast(steps=steps) if steps > 0 else np.array([])
        fc_map = {last_year + i + 1: float(fc[i]) for i in range(len(fc))}
        fitted = best.fittedvalues
        out = np.empty(len(target_years))
        for i, y in enumerate(target_years):
            if y in in_hist:
                idx = in_hist[y]
                out[i] = float(fitted[idx]) if idx < len(fitted) else float(values[idx])
            elif y in fc_map:
                out[i] = fc_map[y]
            else:
                out[i] = float(values[-1])
        return np.clip(out, 0, None)

    return predict


def _make_features(years: np.ndarray, base_year: int) -> np.ndarray:
    """Features simples — APENAS tendência linear e log. Sem termo quadrático
    para não induzir extrapolação para zero/negativo em horizontes longos."""
    yrs = years.astype(float) - base_year
    return np.column_stack([yrs, np.log1p(np.maximum(yrs + 1, 1))])


def _train_rf(years: np.ndarray, values: np.ndarray):
    from sklearn.ensemble import RandomForestRegressor
    base = int(years.min())
    X = _make_features(years, base)
    m = RandomForestRegressor(n_estimators=200, max_depth=4, random_state=42)
    m.fit(X, values)

    def predict(target_years: List[int]) -> np.ndarray:
        Xn = _make_features(np.array(target_years), base)
        return np.clip(m.predict(Xn), 0, None)

    return predict


def _train_xgb(years: np.ndarray, values: np.ndarray):
    try:
        from xgboost import XGBRegressor
    except Exception:
        return None
    base = int(years.min())
    X = _make_features(years, base)
    m = XGBRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        objective="reg:squarederror", verbosity=0, random_state=42,
    )
    m.fit(X, values)

    def predict(target_years: List[int]) -> np.ndarray:
        Xn = _make_features(np.array(target_years), base)
        return np.clip(m.predict(Xn), 0, None)

    return predict


def _train_linear(years: np.ndarray, values: np.ndarray):
    from sklearn.linear_model import LinearRegression
    lr = LinearRegression().fit(years.reshape(-1, 1), values)

    def predict(target_years: List[int]) -> np.ndarray:
        return np.clip(lr.predict(np.array(target_years).reshape(-1, 1)), 0, None)

    return predict


# ---------------- métricas ----------------

def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, float, float]:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(math.sqrt(np.mean((y_true - y_pred) ** 2)))
    denom = np.where(y_true == 0, 1, np.abs(y_true))
    mape = float(np.mean(np.abs(y_true - y_pred) / denom) * 100)
    return mae, rmse, mape


TRAINERS = {
    "Prophet": _train_prophet,
    "ARIMA": _train_arima,
    "RandomForest": _train_rf,
    "XGBoost": _train_xgb,
    "Linear": _train_linear,
}


def _records_by_year(df: pd.DataFrame, value_col: str) -> List[Dict[str, float | int]]:
    return [
        {"ano": int(row["ano"]), "valor": float(row[value_col])}
        for _, row in df.sort_values("ano").iterrows()
    ]


def _zero_reason(raw_value: float, processed_value: float, historical_sum: float) -> Optional[str]:
    if processed_value > 0:
        return None
    if historical_sum <= 0:
        return "zerado porque a série histórica treinável não possui óbitos registrados"
    if raw_value <= 0:
        return "modelo retornou valor bruto menor ou igual a zero e o pós-processamento aplicou limite inferior"
    return "valor positivo tornou-se zero após pós-processamento"


def _damping_baseline(values: np.ndarray, value_col: str) -> float:
    recent = float(values[-min(3, len(values)):].mean())
    if value_col != "mortos" or float(values.sum()) <= 0:
        return recent

    positives = values[values > 0]
    longer_recent = float(values[-min(5, len(values)):].mean())
    return max(recent, longer_recent, float(values.mean()) * 0.5, float(positives.mean()) * 0.25)


# ---------------- orquestrador ----------------

def fit_and_forecast(
    history: pd.DataFrame,
    value_col: str,
    start_year: int,
    end_year: int,
    anos_parciais: Optional[List[int]] = None,
) -> Forecast:
    obs: List[str] = []
    anos_parciais = anos_parciais or []
    df = history.dropna(subset=["ano", value_col]).copy()
    df = df.groupby("ano", as_index=False)[value_col].sum().sort_values("ano")
    historico_real = _records_by_year(df, value_col)

    anos_excluidos: List[int] = []
    if anos_parciais:
        mask = df["ano"].isin(anos_parciais)
        anos_excluidos = sorted(df.loc[mask, "ano"].astype(int).unique().tolist())
        df_treino = df.loc[~mask].copy()
        if anos_excluidos:
            obs.append(
                f"Ano(s) parcial(is) {anos_excluidos} excluído(s) do treino "
                f"(coleta incompleta — distorceria a tendência)."
            )
    else:
        df_treino = df.copy()

    years = df_treino["ano"].to_numpy(dtype=int)
    values = df_treino[value_col].to_numpy(dtype=float)
    n = len(values)

    # ---------- Histórico insuficiente: só análise histórica, sem projeção ----------
    if n < MIN_ANOS_TREINO:
        obs.append(
            f"Histórico útil insuficiente ({n} anos) — projeções não são "
            f"estatisticamente confiáveis. Exibindo apenas a série observada."
        )
        serie = []
        # série completa (incluindo anos parciais marcados como tal)
        for _, row in df.iterrows():
            ano = int(row["ano"])
            v = float(row[value_col])
            tipo = "parcial" if ano in anos_excluidos else "historico"
            serie.append({
                "ano": ano, "valor": v,
                "lower": v * 0.9, "upper": v * 1.1, "tipo": tipo,
            })
        auditoria = {
            "metrica": value_col,
            "historico_real_por_ano": historico_real,
            "dados_treino": _records_by_year(df_treino, value_col),
            "previsao_bruta_ano_a_ano": [],
            "previsao_pos_processamento": [],
            "motivo_valor_zerado": [],
            "observacoes": ["histórico insuficiente para treino preditivo"],
        }
        return Forecast(
            serie=serie, modelo_escolhido="Histórico (sem projeção)",
            comparacao=[], taxa_crescimento_anual_pct=0.0,
            confiabilidade="baixa", confiabilidade_score=0.15,
            observacoes=obs, anos_excluidos=anos_excluidos,
            anos_treino=sorted(int(y) for y in years),
            auditoria=auditoria,
        )

    # Holdout — últimos 1-3 anos
    val_size = min(3, max(1, n // 4))
    train_y, train_v = years[:-val_size], values[:-val_size]
    val_y, val_v = years[-val_size:], values[-val_size:]

    results: List[ModelResult] = []
    for name, trainer in TRAINERS.items():
        try:
            if len(train_y) < 3:
                continue
            fitted = trainer(train_y, train_v)
            if fitted is None:
                continue
            pred = np.asarray(fitted(list(val_y.astype(int))), dtype=float)
            mae, rmse, mape = _metrics(val_v, pred)
            full_fit = trainer(years, values)
            if full_fit is None:
                continue
            results.append(ModelResult(name, mae, rmse, mape, full_fit))
        except Exception as e:  # noqa: BLE001
            obs.append(f"Falha em {name}: {e.__class__.__name__}")

    if not results:
        lin = _train_linear(years, values)
        results = [ModelResult("Linear (fallback)", 0, 0, 0, lin)]
        obs.append("Modelos avançados falharam; usando regressão linear como fallback.")

    best = min(results, key=lambda r: (r.mape if r.mape > 0 else r.rmse))

    # ---------- Predições ----------
    hist_min_v = float(values.min())
    hist_max_v = float(values.max())
    last_hist_year = int(years.max())
    # Limites realistas para evitar zero artificial / explosão.
    # Para óbitos, preservar valores esperados fracionários: uma cidade com
    # histórico 1,0,1,1... pode ter expectativa anual <1, mas não deve virar
    # zero por arredondamento ou por damping sobre anos recentes zerados.
    positive_values = values[values > 0]
    if value_col == "mortos" and positive_values.size > 0:
        floor = float(max(0.01, min(float(positive_values.min()) * 0.10, float(values.mean()) * 0.50)))
    else:
        floor = max(0.0, hist_min_v * 0.4)
    ceiling = hist_max_v * 2.5

    target_years = list(range(min(int(years.min()), start_year), end_year + 1))
    raw = np.asarray(best.fitted(target_years), dtype=float)

    # Damping para projeções distantes: blenda predição com média recente
    media_recente = _damping_baseline(values, value_col)
    fit_vals = []
    raw_forecast_records: List[Dict[str, float | int]] = []
    processed_forecast_records: List[Dict[str, float | int | Optional[str]]] = []
    for y, v in zip(target_years, raw):
        dist = max(0, y - last_hist_year)
        if dist == 0:
            adj = v
        else:
            # damping suave: cada ano à frente puxa um pouco em direção à média recente
            w = (1.0 - DAMPING ** dist)  # 0 → cresce com distância
            adj = v * (1 - w) + media_recente * w
        adj = float(np.clip(adj, floor, ceiling))
        if y > last_hist_year:
            raw_v = float(v)
            raw_forecast_records.append({"ano": int(y), "valor_bruto": raw_v})
            processed_forecast_records.append({
                "ano": int(y),
                "valor_pos_processamento": adj,
                "motivo_valor_zerado": _zero_reason(raw_v, adj, float(values.sum())),
            })
        fit_vals.append(adj)

    # Resíduo histórico → banda
    hist_pred = np.asarray(best.fitted(list(years.astype(int))), dtype=float)
    residuals = values - hist_pred
    sigma = float(np.std(residuals)) if len(residuals) > 1 else max(float(values.std()), 1.0)

    # Inclui anos parciais como "parcial" na visualização
    parc_map = {int(r["ano"]): float(r[value_col]) for _, r in df.iterrows()
                if int(r["ano"]) in anos_excluidos}
    hist_set = set(int(y) for y in years)

    serie: List[dict] = []
    for y, v in zip(target_years, fit_vals):
        if y in parc_map:  # mostra o ano parcial REAL, marcado
            real = parc_map[y]
            serie.append({"ano": int(y), "valor": real,
                          "lower": real * 0.9, "upper": real * 1.1, "tipo": "parcial"})
            continue
        is_hist = y in hist_set
        dist = max(0, y - last_hist_year)
        band = sigma * (1.0 + math.sqrt(dist) * 0.5)
        # banda mínima: 10% do valor
        band = max(band, v * 0.10)
        serie.append({
            "ano": int(y),
            "valor": float(v),
            "lower": float(max(floor, v - 1.96 * band)),
            "upper": float(min(ceiling, v + 1.96 * band)),
            "tipo": "historico" if is_hist else "previsao",
        })

    # CAGR projeção
    future = [p for p in serie if p["tipo"] == "previsao"]
    growth_pct = 0.0
    if len(future) >= 2 and future[0]["valor"] > 0:
        span = future[-1]["ano"] - future[0]["ano"]
        if span > 0:
            growth_pct = ((future[-1]["valor"] / future[0]["valor"]) ** (1 / span) - 1) * 100

    horizon = max(0, end_year - last_hist_year)
    mape_score = max(0.0, 1.0 - min(best.mape, 100) / 100)
    horizon_penalty = max(0.0, 1.0 - horizon / 40)  # >40 anos → quase zero
    history_score = min(1.0, n / 12)
    score = max(0.05, min(1.0,
        0.45 * mape_score + 0.40 * horizon_penalty + 0.15 * history_score))
    if score >= 0.7:
        label = "alta"
    elif score >= 0.4:
        label = "media"
    else:
        label = "baixa"
        obs.append("Horizonte longo: bandas de confiança amplas; trate como cenário.")

    comparacao = [{"modelo": r.modelo, "mae": round(r.mae, 2),
                   "rmse": round(r.rmse, 2), "mape": round(r.mape, 2)}
                  for r in results]

    return Forecast(
        serie=serie,
        modelo_escolhido=best.modelo,
        comparacao=comparacao,
        taxa_crescimento_anual_pct=round(growth_pct, 3),
        confiabilidade=label,
        confiabilidade_score=round(score, 3),
        observacoes=obs,
        anos_excluidos=anos_excluidos,
        anos_treino=sorted(int(y) for y in years),
    )
