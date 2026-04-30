"""Genera una muestra anonimizada del dataset crudo para versionarla en `data/sample/`.

Uso:
    uv run python scripts/build_sample.py

Lee `data/raw/transporte_um.xlsx`, toma muestra reproducible de 50 filas por hoja,
anonimiza campos sensibles (empresa, cliente, patentes, direcciones, IDs) con un
mapping consistente entre hojas, y escribe `data/sample/transporte_um_sample.xlsx`.

La muestra anonimizada SÍ se versiona en git (es la única excepción al `.gitignore` de Excel).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "transporte_um.xlsx"
SAMPLE = ROOT / "data" / "sample" / "transporte_um_sample.xlsx"

SEED = 42
N_VIAJES = 50
N_DEVOLUCIONES = 25


def hash_id(value: object, prefix: str, length: int = 8) -> str:
    """ID determinista corto, mismo input → mismo output entre hojas."""
    if pd.isna(value):
        return ""
    digest = hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:length].upper()
    return f"{prefix}_{digest}"


def anonimizar_viajes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Suborden"] = out["Suborden"].map(lambda v: hash_id(v, "SUB"))
    out["Do"] = out["Do"].map(lambda v: hash_id(v, "DO"))
    out["Patente"] = out["Patente"].map(lambda v: hash_id(v, "VEH", 6))
    out["Empresa"] = "EmpresaTransporteA"
    out["Idruta"] = out["Idruta"].map(lambda v: hash_id(v, "RUT"))
    out["Direccion"] = out["Direccion"].apply(
        lambda _: "Direccion anonimizada"
    )
    out["Commerce"] = out["Commerce"].apply(
        lambda v: "ClienteRetailA" if pd.notna(v) else v
    )
    for col in ("LPN", "LPN_Container", "ParentOrder"):
        prefix = col[:3].upper()
        out[col] = out[col].apply(
            lambda v, prefix=prefix: hash_id(v, prefix) if pd.notna(v) else v
        )
    return out


def anonimizar_devoluciones(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "N° Recepción" in out.columns:
        out["N° Recepción"] = out["N° Recepción"].map(lambda v: hash_id(v, "REC"))
    if "N° de Etiqueta" in out.columns:
        out["N° de Etiqueta"] = out["N° de Etiqueta"].map(lambda v: hash_id(v, "ETI"))
    if "N° de OC" in out.columns:
        out["N° de OC"] = out["N° de OC"].map(
            lambda v: hash_id(v, "OC") if v not in ("-", "") and pd.notna(v) else v
        )
    if "Patente" in out.columns:
        out["Patente"] = out["Patente"].map(lambda v: hash_id(v, "VEH", 6))
    if "Observaciones" in out.columns:
        out["Observaciones"] = out["Observaciones"].apply(
            lambda v: "Observacion anonimizada" if pd.notna(v) else v
        )
    return out


def main() -> None:
    if not RAW.exists():
        msg = f"Falta dataset crudo en {RAW}. Colocarlo manualmente, no se versiona."
        raise FileNotFoundError(msg)

    log.info("Leyendo %s", RAW)
    viajes = pd.read_excel(RAW, sheet_name="VIAJES DIARIOS")
    devoluciones = pd.read_excel(RAW, sheet_name="DEVOLUCIONES")
    log.info("Viajes: %s filas | Devoluciones: %s filas", len(viajes), len(devoluciones))

    viajes_sample = viajes.sample(n=min(N_VIAJES, len(viajes)), random_state=SEED).reset_index(
        drop=True
    )
    devoluciones_sample = devoluciones.sample(
        n=min(N_DEVOLUCIONES, len(devoluciones)), random_state=SEED
    ).reset_index(drop=True)

    viajes_sample = anonimizar_viajes(viajes_sample)
    devoluciones_sample = anonimizar_devoluciones(devoluciones_sample)

    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(SAMPLE, engine="openpyxl") as writer:
        viajes_sample.to_excel(writer, sheet_name="VIAJES DIARIOS", index=False)
        devoluciones_sample.to_excel(writer, sheet_name="DEVOLUCIONES", index=False)

    log.info("Muestra anonimizada escrita en %s", SAMPLE)
    log.info(
        "Filas: viajes=%s, devoluciones=%s", len(viajes_sample), len(devoluciones_sample)
    )


if __name__ == "__main__":
    main()
