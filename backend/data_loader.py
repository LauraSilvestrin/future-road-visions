"""Carregamento dos CSVs reais da pasta data/ (RENAEST + DATATRAN/PRF consolidados).

Estrutura efetivamente encontrada (separador `;`, codificação utf-8):
- municipio_ano.csv  -> ano, uf, municipio, acidentes, mortos, feridos, pessoas
- uf_ano.csv         -> ano, uf, acidentes, mortos, feridos, pessoas
- regiao_ano.csv     -> ano, regiao, acidentes, mortos, feridos
- causa_ano.csv      -> ano, causa_acidente, acidentes, mortos
- clima_ano.csv      -> ano, condicao_metereologica, acidentes, mortos

Observações:
- A coluna `veiculos` NÃO está presente na base atual (era do antigo schema PRF).
- O último ano da base pode estar PARCIAL (coleta incompleta). Isto é detectado
  comparando o total do último ano com a mediana dos 3 anos anteriores.
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))

# Limite: se o total do último ano for menor que esta fração da mediana
# dos 3 anos anteriores, ele é tratado como PARCIAL e excluído do treino.
PARTIAL_YEAR_THRESHOLD = 0.6


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo ausente: {path}")
    last_err: Exception | None = None
    for sep in (";", ","):
        for enc in ("utf-8", "latin-1"):
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc)
                if df.shape[1] > 1:
                    df.columns = [_normalize(c) for c in df.columns]
                    return df
            except Exception as e:  # noqa: BLE001
                last_err = e
    raise RuntimeError(f"Não foi possível ler {path}: {last_err}")


@dataclass
class Datasets:
    municipio: pd.DataFrame
    uf: pd.DataFrame
    regiao: pd.DataFrame
    causa: pd.DataFrame
    clima: pd.DataFrame
    ano_min: int
    ano_max: int
    ano_max_completo: int  # último ano CONSIDERADO COMPLETO (treino)
    anos_parciais: List[int] = field(default_factory=list)
    fontes: List[str] = field(default_factory=lambda: ["RENAEST", "DATATRAN/PRF"])

    @property
    def ufs(self) -> List[str]:
        return sorted(self.uf["uf"].dropna().astype(str).str.upper().unique().tolist())

    @property
    def regioes(self) -> List[str]:
        return sorted(self.regiao["regiao"].dropna().astype(str).unique().tolist())

    def municipios_por_uf(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for uf, sub in self.municipio.groupby("uf"):
            out[str(uf).upper()] = sorted(
                sub["municipio"].dropna().astype(str).unique().tolist()
            )
        return out


def _coerce_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            raw = df[c]
            if raw.dtype == "object":
                cleaned = (
                    raw.astype(str)
                    .str.strip()
                    .str.replace("\u00a0", "", regex=False)
                    .str.replace(r"(?<=\d)\.(?=\d{3}(\D|$))", "", regex=True)
                    .str.replace(",", ".", regex=False)
                )
                numeric = pd.to_numeric(cleaned, errors="coerce")
                blanks = cleaned.isin(["", "nan", "None", "NaN"])
                invalid = numeric.isna() & ~blanks
                if invalid.any():
                    exemplos = sorted(cleaned[invalid].astype(str).unique().tolist())[:5]
                    raise ValueError(
                        f"Coluna numérica inválida em '{c}': {int(invalid.sum())} valor(es) "
                        f"não conversível(is), exemplos={exemplos}"
                    )
                df[c] = numeric.fillna(0)
            else:
                df[c] = pd.to_numeric(raw, errors="raise").fillna(0)
    return df


def _detectar_anos_parciais(uf_df: pd.DataFrame) -> List[int]:
    """Retorna anos cujo total nacional de acidentes é < PARTIAL_YEAR_THRESHOLD
    da mediana dos 3 anos anteriores. Tipicamente o ano corrente em coleta."""
    tot = uf_df.groupby("ano")["acidentes"].sum().sort_index()
    parciais: List[int] = []
    anos = tot.index.tolist()
    for i, ano in enumerate(anos):
        if i < 3:
            continue
        ref = tot.iloc[max(0, i - 3): i].median()
        if ref > 0 and tot.iloc[i] < PARTIAL_YEAR_THRESHOLD * ref:
            parciais.append(int(ano))
    return parciais


def load_all() -> Datasets:
    mun = _read_csv(DATA_DIR / "municipio_ano.csv")
    uf = _read_csv(DATA_DIR / "uf_ano.csv")
    reg = _read_csv(DATA_DIR / "regiao_ano.csv")
    cau = _read_csv(DATA_DIR / "causa_ano.csv")
    cli = _read_csv(DATA_DIR / "clima_ano.csv")

    mun["uf"] = mun["uf"].astype(str).str.upper().str.strip()
    uf["uf"] = uf["uf"].astype(str).str.upper().str.strip()
    mun["municipio"] = mun["municipio"].astype(str).str.strip()
    reg["regiao"] = reg["regiao"].astype(str).str.strip()
    cau["causa_acidente"] = cau["causa_acidente"].astype(str).str.strip()
    cli["condicao_metereologica"] = cli["condicao_metereologica"].astype(str).str.strip()

    for df in (mun, uf, reg, cau, cli):
        df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
        df.dropna(subset=["ano"], inplace=True)
        df["ano"] = df["ano"].astype(int)

    # Apenas colunas REALMENTE presentes (sem 'veiculos', removida do schema novo)
    _coerce_numeric(mun, ["acidentes", "mortos", "feridos", "pessoas"])
    _coerce_numeric(uf, ["acidentes", "mortos", "feridos", "pessoas"])
    _coerce_numeric(reg, ["acidentes", "mortos", "feridos"])
    _coerce_numeric(cau, ["acidentes", "mortos"])
    _coerce_numeric(cli, ["acidentes", "mortos"])

    ano_min = int(min(mun["ano"].min(), uf["ano"].min(), reg["ano"].min()))
    ano_max = int(max(mun["ano"].max(), uf["ano"].max(), reg["ano"].max()))

    parciais = _detectar_anos_parciais(uf)
    ano_max_completo = ano_max
    while ano_max_completo in parciais and ano_max_completo > ano_min:
        ano_max_completo -= 1

    return Datasets(
        municipio=mun, uf=uf, regiao=reg, causa=cau, clima=cli,
        ano_min=ano_min, ano_max=ano_max,
        ano_max_completo=ano_max_completo,
        anos_parciais=parciais,
    )
