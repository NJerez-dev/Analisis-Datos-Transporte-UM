"""Tests para `transporte.bronze`.

Usa la muestra anonimizada en `data/sample/transporte_um_sample.xlsx`
(versionada). No depende del crudo, así que estos tests corren en CI sin
acceso a datos sensibles.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from transporte import bronze

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "data" / "sample" / "transporte_um_sample.xlsx"


@pytest.fixture(scope="module")
def viajes_raw() -> pd.DataFrame:
    return bronze.read_sheet_as_strings(SAMPLE, bronze.SHEET_VIAJES)


@pytest.fixture(scope="module")
def devoluciones_raw() -> pd.DataFrame:
    return bronze.read_sheet_as_strings(SAMPLE, bronze.SHEET_DEVOLUCIONES)


def test_sample_exists() -> None:
    assert SAMPLE.exists(), f"Falta la muestra anonimizada en {SAMPLE}"


def test_read_sheet_returns_strings(viajes_raw: pd.DataFrame) -> None:
    assert len(viajes_raw) > 0
    non_string = [
        col
        for col in viajes_raw.columns
        if viajes_raw[col].dropna().map(lambda v: not isinstance(v, str)).any()
    ]
    assert non_string == [], f"Bronze debe preservar todo como string. Violan: {non_string}"


def test_read_sheet_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        bronze.read_sheet_as_strings(tmp_path / "no-existe.xlsx", bronze.SHEET_VIAJES)


def test_add_metadata_appends_three_columns(viajes_raw: pd.DataFrame) -> None:
    metadata = bronze.IngestionMetadata.now(fuente="VIAJES", archivo="test.xlsx")
    out = bronze.add_metadata(viajes_raw, metadata)
    assert {"_ingesta_timestamp", "_fuente", "_archivo"}.issubset(out.columns)
    assert (out["_fuente"] == "VIAJES").all()
    assert (out["_archivo"] == "test.xlsx").all()


def test_add_metadata_does_not_mutate_input(viajes_raw: pd.DataFrame) -> None:
    cols_before = set(viajes_raw.columns)
    metadata = bronze.IngestionMetadata.now(fuente="X", archivo="Y")
    bronze.add_metadata(viajes_raw, metadata)
    assert set(viajes_raw.columns) == cols_before


def test_normalize_column_names_renames_spec_columns(devoluciones_raw: pd.DataFrame) -> None:
    out = bronze.normalize_column_names(devoluciones_raw, bronze.DEVOLUCIONES_RENAMES)
    assert "nro_recepcion" in out.columns
    assert "estado_devolucion" in out.columns
    assert "fecha_devolucion" in out.columns
    raw_chars_in_output = [
        col for col in out.columns if any(ch in col for ch in ("°", "ó", "Ó", "ñ"))
    ]
    assert raw_chars_in_output == []


def test_ingest_all_writes_two_parquets(tmp_path: Path) -> None:
    outputs = bronze.ingest_all(input_path=SAMPLE, output_dir=tmp_path)

    assert set(outputs.keys()) == {"viajes", "devoluciones"}
    for path in outputs.values():
        assert path.exists(), f"No se escribio el parquet: {path}"

    viajes = pd.read_parquet(outputs["viajes"])
    devoluciones = pd.read_parquet(outputs["devoluciones"])
    assert len(viajes) > 0
    assert len(devoluciones) > 0
    assert {"_ingesta_timestamp", "_fuente", "_archivo"}.issubset(viajes.columns)
    assert {"_ingesta_timestamp", "_fuente", "_archivo"}.issubset(devoluciones.columns)
    assert "nro_recepcion" in devoluciones.columns
