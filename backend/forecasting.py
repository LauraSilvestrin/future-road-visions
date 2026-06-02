"""Engine de previsão: treina 4 modelos, escolhe o melhor por validação holdout,
e projeta para qualquer horizonte futuro com intervalo de confiança.

Modelos:
- Prophet
- ARIMA (statsmodels)
- Random Forest Regressor (sklearn) com features lag + tendência
- XGBoost Regressor

Estratégia:
1. Usa o histórico anual (ano -> valor).
2. Reserva os últimos N anos (até 4) como validação; calcula MAE/RMSE/MAPE.
3. Escolhe modelo com menor MAPE (ou RMSE se MAPE indef.).
4. Re-treina no histórico completo e projeta horizonte solicitado.
5. Intervalo de confiança expande com a distância (heurística baseada no
   resíduo histórico, multiplicado por sqrt(distância) — quanto mais longe,
   menor a confiabilidade).
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


@dataclass
class ModelResult:
    modelo: str
    mae: float
    rmse: float
    mape: float
    fitted: object  # callable (anos: List[int]) -> np.ndarray


@dataclass
class Forecast:
    serie: List[dict]            # [{ano, valor, lower, upper, tipo}]
    modelo_escolhido: str
    comparacao: List[Dict[str, float | str]]
    taxa_crescimento_anual_pct: float
    confiabilidade: str
    confiabilidade_score: float
    observacoes: List[str]


# ---------------- modelos individuais ----------------

def _train_prophet(years: np.ndarray, values: np.ndarray):
    try:
        from prophet import Prophet
    except Exception:
        return None
    df = pd.DataFrame({
        "ds": pd.to_datetime(years.astype(int).astype(str) + "-01-01"),
        "y": values,
    })
    m = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False,
                changepoint_prior_scale=0.05, interval_width=0.8)
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
    best = None
    best_aic = float("inf")
    for order in [(1, 1, 1), (2, 1, 1), (1, 1, 0), (0, 1, 1), (2, 1, 2)]:
        try:
            m = ARIMA(values, order=order).fit()
            if m.aic < best_aic:
                best_aic = m.aic
                best = m
                best_order = order
        except Exception:
            continue
    if best is None:
        return None
    last_year = int(years.max())

    def predict(target_years: List[int]) -> np.ndarray:
        out = np.empty(len(target_years))
        in_hist_idx = {int(y): i for i, y in enumerate(years)}
        future_years = sorted(y for y in target_years if y > last_year)
        steps = (max(future_years) - last_year) if future_years else 0
        fc = best.forecast(steps=steps) if steps > 0 else np.array([])
        fc_map = {last_year + i + 1: float(fc[i]) for i in range(len(fc))}
        fitted_vals = best.fittedvalues
        for i, y in enumerate(target_years):
            if y in in_hist_idx:
                out[i] = float(fitted_vals[in_hist_idx[y]]) if in_hist_idx[y] < len(fitted_vals) else float(values[in_hist_idx[y]])
            elif y in fc_map:
                out[i] = fc_map[y]
            else:
                out[i] = float(values[-1])
        return np.clip(out, 0, None)

    return predict


def _make_features(years: np.ndarray, base_year: int, base_value: float) -> np.ndarray:
    """Features: ano normalizado, tendência, log do ano-deslocamento."""
    yrs = years.astype(float)
    return np.column_stack([
        yrs - base_year,
        (yrs - base_year) ** 2,
        np.log1p(np.maximum(yrs - base_year + 1, 1)),
    ])


def _train_rf(years: np.ndarray, values: np.ndarray):
    from sklearn.ensemble import RandomForestRegressor
    base = int(years.min())
    X = _make_features(years, base, float(values[0]))
    m = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    m.fit(X, values)

    def predict(target_years: List[int]) -> np.ndarray:
        Xn = _make_features(np.array(target_years), base, float(values[0]))
        return np.clip(m.predict(Xn), 0, None)
    return predict


def _train_xgb(years: np.ndarray, values: np.ndarray):
    try:
        from xgboost import XGBRegressor
    except Exception:
        return None
    base = int(years.min())
    X = _make_features(years, base, float(values[0]))
    m = XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
                     objective="reg:squarederror", verbosity=0)
    m.fit(X, values)

    def predict(target_years: List[int]) -> np.ndarray:
        Xn = _make_features(np.array(target_years), base, float(values[0]))
        return np.clip(m.predict(Xn), 0, None)
    return predict


# ---------------- métricas ----------------

def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, float, float]:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(math.sqrt(np.mean((y_true - y_pred) ** 2)))
    denom = np.where(y_true == 0, 1, np.abs(y_true))
    mape = float(np.mean(np.abs(y_true - y_pred) / denom) * 100)
    return mae, rmse, mape


# ---------------- orquestrador ----------------

TRAINERS = {
    "Prophet": _train_prophet,
    "ARIMA": _train_arima,
    "RandomForest": _train_rf,
    "XGBoost": _train_xgb,
}


def fit_and_forecast(history: pd.DataFrame, value_col: str,
                     start_year: int, end_year: int) -> Forecast:
    """
    history: DataFrame com colunas ['ano', value_col], já agregado anualmente
             (uma linha por ano). Mínimo recomendado: 5 anos.
    """
    obs = []
    df = history.dropna(subset=["ano", value_col]).copy()
    df = df.groupby("ano", as_index=False)[value_col].sum().sort_values("ano")
    years = df["ano"].to_numpy(dtype=int)
    values = df[value_col].to_numpy(dtype=float)
    n = len(values)

    if n < 3:
        # fallback: média/repetição
        mean = float(values.mean()) if n else 0.0
        std = float(values.std()) if n > 1 else max(mean * 0.5, 1.0)
        target_years = list(range(int(min(years.min() if n else start_year, start_year)),
                                  end_year + 1))
        serie = []
        for y in target_years:
            tipo = "historico" if y in years else "previsao"
            v = float(values[list(years).index(y)]) if tipo == "historico" else mean
            band = std * (1 + max(0, y - (years.max() if n else start_year)) / 10)
            serie.append({"ano": y, "valor": v, "lower": max(0, v - band), "upper": v + band, "tipo": tipo})
        return Forecast(
            serie=serie, modelo_escolhido="Média",
            comparacao=[{"modelo": "Média", "mae": 0, "rmse": 0, "mape": 0}],
            taxa_crescimento_anual_pct=0.0,
            confiabilidade="baixa", confiabilidade_score=0.2,
            observacoes=["Histórico insuficiente (<3 anos): previsão fortemente limitada."],
        )

    # Holdout
    val_size = min(4, max(1, n // 4))
    train_y, train_v = years[:-val_size], values[:-val_size]
    val_y, val_v = years[-val_size:], values[-val_size:]

    results: List[ModelResult] = []
    for name, trainer in TRAINERS.items():
        try:
            fitted = trainer(train_y, train_v) if len(train_y) >= 3 else None
            if fitted is None:
                continue
            pred = np.asarray(fitted(list(val_y.astype(int))), dtype=float)
            mae, rmse, mape = _metrics(val_v, pred)
            full_fit = trainer(years, values)  # re-treina no histórico inteiro
            if full_fit is None:
                continue
            results.append(ModelResult(name, mae, rmse, mape, full_fit))
        except Exception as e:  # noqa: BLE001
            obs.append(f"Falha em {name}: {e.__class__.__name__}")

    if not results:
        # último fallback: regressão linear
        from sklearn.linear_model import LinearRegression
        lr = LinearRegression().fit(years.reshape(-1, 1), values)
        def lin_pred(ys: List[int]) -> np.ndarray:
            return np.clip(lr.predict(np.array(ys).reshape(-1, 1)), 0, None)
        results = [ModelResult("LinearRegression", 0, 0, 0, lin_pred)]
        obs.append("Modelos avançados falharam; usando regressão linear como fallback.")

    best = min(results, key=lambda r: (r.mape if r.mape > 0 else r.rmse))

    # projeta intervalo solicitado + histórico para visualização
    target_years = list(range(min(int(years.min()), start_year), end_year + 1))
    fit_vals = best.fitted(target_years)

    # resíduo histórico para estimar bandas
    hist_pred = best.fitted(list(years.astype(int)))
    residuals = values - hist_pred
    sigma = float(np.std(residuals)) if len(residuals) > 1 else max(float(values.std()), 1.0)
    last_hist_year = int(years.max())

    serie = []
    hist_set = set(int(y) for y in years)
    for y, v in zip(target_years, fit_vals):
        is_hist = y in hist_set
        dist = max(0, y - last_hist_year)
        # banda cresce com sqrt(distância) — extrapolações distantes ficam mais incertas
        band = sigma * (1.0 + math.sqrt(dist) * 0.6)
        serie.append({
            "ano": int(y),
            "valor": float(max(0.0, v)),
            "lower": float(max(0.0, v - 1.96 * band)),
            "upper": float(max(0.0, v + 1.96 * band)),
            "tipo": "historico" if is_hist else "previsao",
        })

    # taxa de crescimento anual média (CAGR sobre a projeção)
    future = [p for p in serie if p["tipo"] == "previsao"]
    growth_pct = 0.0
    if len(future) >= 2 and future[0]["valor"] > 0:
        years_span = future[-1]["ano"] - future[0]["ano"]
        if years_span > 0:
            growth_pct = ((future[-1]["valor"] / future[0]["valor"]) ** (1 / years_span) - 1) * 100

    # confiabilidade: combina MAPE do melhor modelo com horizonte
    horizon = max(0, end_year - last_hist_year)
    mape_score = max(0.0, 1.0 - min(best.mape, 100) / 100)
    horizon_penalty = max(0.0, 1.0 - horizon / 80)  # >80 anos => quase zero
    history_score = min(1.0, n / 15)
    score = max(0.05, min(1.0, 0.5 * mape_score + 0.35 * horizon_penalty + 0.15 * history_score))
    if score >= 0.7:
        label = "alta"
    elif score >= 0.4:
        label = "media"
    else:
        label = "baixa"
        obs.append("Horizonte de projeção muito longo: intervalos de confiança amplos e baixa confiabilidade estatística.")

    comparacao = [{"modelo": r.modelo, "mae": round(r.mae, 2),
                   "rmse": round(r.rmse, 2), "mape": round(r.mape, 2)} for r in results]

    return Forecast(
        serie=serie,
        modelo_escolhido=best.modelo,
        comparacao=comparacao,
        taxa_crescimento_anual_pct=round(growth_pct, 3),
        confiabilidade=label,
        confiabilidade_score=round(score, 3),
        observacoes=obs,
    )
