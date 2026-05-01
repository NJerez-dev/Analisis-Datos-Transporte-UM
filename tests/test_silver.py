"""Tests para `transporte.silver`.

Encadena bronze → silver sobre la muestra anonimizada en `data/sample/` y
verifica tipos, columnas calculadas y reglas de negocio mínimas.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from transporte import bronze, silver

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "data" / "sample" / "transporte_um_sample.xlsx"


@pytest.fixture(scope="module")
def bronze_outputs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Corre bronze sobre la muestra y deja los parquets en un tmp dir."""
    out = tmp_path_factory.mktemp("bronze_out")
    bronze.ingest_all(input_path=SAMPLE, output_dir=out)
    return out


@pytest.fixture(scope="module")
def silver_viajes(bronze_outputs: Path, tmp_path_factory: pytest.TempPathFactory) -> pd.DataFrame:
    out = tmp_path_factory.mktemp("silver_out")
    path = silver.silverize_viajes(input_dir=bronze_outputs, output_dir=out)
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def silver_devoluciones(
    bronze_outputs: Path, tmp_path_factory: pytest.TempPathFactory
) -> pd.DataFrame:
    out = tmp_path_factory.mktemp("silver_out_dev")
    path = silver.silverize_devoluciones(input_dir=bronze_outputs, output_dir=out)
    return pd.read_parquet(path)


def test_silverize_all_writes_two_parquets(bronze_outputs: Path, tmp_path: Path) -> None:
    outputs = silver.silverize_all(input_dir=bronze_outputs, output_dir=tmp_path)
    assert set(outputs.keys()) == {"viajes", "devoluciones"}
    for path in outputs.values():
        assert path.exists()


def test_silver_viajes_columns_renamed_to_snake_case(silver_viajes: pd.DataFrame) -> None:
    expected = {
        "suborden",
        "documento",
        "estado",
        "patente",
        "id_ruta",
        "centro_transporte",
        "volumen",
        "fecha_pactada",
        "fecha_entrega_real",
        "dias_retraso",
        "entrega_on_time",
        "flag_no_entregado",
    }
    assert expected.issubset(set(silver_viajes.columns))
    assert "Suborden" not in silver_viajes.columns
    assert "Volumen" not in silver_viajes.columns
    assert "volumen_raw" not in silver_viajes.columns


def test_silver_viajes_no_bronze_metadata(silver_viajes: pd.DataFrame) -> None:
    bronze_meta = [
        c for c in silver_viajes.columns if c.startswith("_") and c != "_silver_timestamp"
    ]
    assert bronze_meta == []


def test_silver_viajes_dates_are_datetime(silver_viajes: pd.DataFrame) -> None:
    for col in silver.VIAJES_FECHAS:
        assert pd.api.types.is_datetime64_any_dtype(silver_viajes[col]), (
            f"{col} debe ser datetime, dtype={silver_viajes[col].dtype}"
        )


def test_silver_viajes_volumen_is_numeric(silver_viajes: pd.DataFrame) -> None:
    assert pd.api.types.is_numeric_dtype(silver_viajes["volumen"])


def test_silver_viajes_flags_are_binary(silver_viajes: pd.DataFrame) -> None:
    assert set(silver_viajes["entrega_on_time"].dropna().unique()).issubset({0, 1})
    assert set(silver_viajes["flag_no_entregado"].dropna().unique()).issubset({0, 1})


def test_silver_viajes_estado_is_title_case(silver_viajes: pd.DataFrame) -> None:
    assert (silver_viajes["estado"] == silver_viajes["estado"].str.title()).all()


def test_silver_viajes_flag_no_entregado_consistent_with_estado(
    silver_viajes: pd.DataFrame,
) -> None:
    terminados = silver_viajes[silver_viajes["estado"] == "Terminado"]
    no_terminados = silver_viajes[silver_viajes["estado"] != "Terminado"]
    assert (terminados["flag_no_entregado"] == 0).all()
    assert (no_terminados["flag_no_entregado"] == 1).all()


def test_silver_devoluciones_dates_are_datetime(silver_devoluciones: pd.DataFrame) -> None:
    assert pd.api.types.is_datetime64_any_dtype(silver_devoluciones["fecha_viaje"])
    assert pd.api.types.is_datetime64_any_dtype(silver_devoluciones["fecha_devolucion"])


def test_silver_devoluciones_has_dias_calculated(silver_devoluciones: pd.DataFrame) -> None:
    assert "dias_hasta_devolucion" in silver_devoluciones.columns


def test_silverize_missing_input_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        silver.silverize_viajes(input_dir=tmp_path, output_dir=tmp_path)
