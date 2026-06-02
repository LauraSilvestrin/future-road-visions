"""Carregamento dos CSVs agregados da pasta data/.

Estrutura esperada (separador `,` ou `;`, codificação utf-8 ou latin-1):
- municipio_ano.csv  -> ano, uf, municipio, acidentes, mortos, feridos, pessoas, veiculos
- uf_ano.csv         -> ano, uf, acidentes, mortos, feridos
- regiao_ano.csv     -> ano, regiao, acidentes, mortos, feridos
- causa_ano.csv      -> ano, causa_acidente, acidentes, mortos
- clima_ano.csv      -> ano, condicao_metereologica, acidentes, mortos
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo ausente: {path}")
    last_err: Exception | None = None
    for sep in (",", ";"):
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

    @property
    def ufs(self) -> List[str]:
        return sorted(self.uf["uf"].dropna().astype(str).str.upper().unique().tolist())

    @property
    def regioes(self) -> List[str]:
        return sorted(self.regiao["regiao"].dropna().astype(str).unique().tolist())

    def municipios_por_uf(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for uf, sub in self.municipio.groupby("uf"):
            out[str(uf).upper()] = sorted(sub["municipio"].dropna().astype(str).unique().tolist())
        return out


def _coerce_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


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

    _coerce_numeric(mun, ["acidentes", "mortos", "feridos", "pessoas", "veiculos"])
    _coerce_numeric(uf, ["acidentes", "mortos", "feridos"])
    _coerce_numeric(reg, ["acidentes", "mortos", "feridos"])
    _coerce_numeric(cau, ["acidentes", "mortos"])
    _coerce_numeric(cli, ["acidentes", "mortos"])

    ano_min = int(min(mun["ano"].min(), uf["ano"].min(), reg["ano"].min()))
    ano_max = int(max(mun["ano"].max(), uf["ano"].max(), reg["ano"].max()))
    return Datasets(mun, uf, reg, cau, cli, ano_min, ano_max)
