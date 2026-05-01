"""Tests para los schemas Pandera y la función helper `validate`.

Verifica que:
- Los schemas detectan datos válidos (golden path).
- Los schemas rechazan datos inválidos con `SchemaError` claro.
- La integración bronze → silver → gold pasa todas las validaciones sobre
  la muestra real anonimizada.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

from transporte import bronze, gold, schemas, silver

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "data" / "sample" / "transporte_um_sample.xlsx"


def test_validate_returns_same_dataframe_on_pass() -> None:
    df = pd.DataFrame({"x": [1, 2, 3]})
    schema = pa.DataFrameSchema({"x": pa.Column(int)})
    out = schemas.validate(df, schema, name="ok")
    assert out is not None
    assert len(out) == len(df)


def test_validate_raises_schema_error_on_fail() -> None:
    df = pd.DataFrame({"x": [1, 2, 3]})
    schema = pa.DataFrameSchema({"y": pa.Column(int)})  # 'y' no existe
    with pytest.raises(pa.errors.SchemaError):
        schemas.validate(df, schema, name="missing-y")


def test_kpi_entregas_rechaza_pct_fuera_de_rango() -> None:
    bad = pd.DataFrame(
        [
            {
                "total_viajes": 100,
                "viajes_terminados": 50,
                "viajes_on_time": 40,
                "pct_on_time_delivery": 150.0,
                "pct_no_entregado": 10.0,
                "lead_time_dias_prom": 1.0,
                "total_devoluciones": 5,
                "tasa_devolucion_pct": 5.0,
                "rutas_unicas": 3,
                "patentes_activas": 2,
                "volumen_total_m3": 1.0,
                "_gold_timestamp": "2026-04-30T00:00:00+00:00",
            }
        ]
    )
    with pytest.raises(pa.errors.SchemaError):
        schemas.validate(bad, schemas.GOLD_KPI_ENTREGAS_SCHEMA, name="kpi-bad")


def test_dim_tiempo_rechaza_mes_invalido() -> None:
    bad = pd.DataFrame(
        [
            {
                "fecha": "2026-13-01",
                "anio": 2026,
                "mes": 13,
                "dia": 1,
                "trimestre": 1,
                "es_fin_semana": 0,
            }
        ]
    )
    with pytest.raises(pa.errors.SchemaError):
        schemas.validate(bad, schemas.GOLD_DIM_TIEMPO_SCHEMA, name="dim-bad")


def test_silver_viajes_rechaza_flag_invalido() -> None:
    bad = pd.DataFrame(
        {
            "suborden": ["X"],
            "documento": ["Y"],
            "estado": ["Terminado"],
            "patente": ["P1"],
            "id_ruta": ["R1"],
            "centro_transporte": ["HUB"],
            "region": ["RM"],
            "commerce": ["A"],
            "volumen": [0.1],
            "fecha_pactada": pd.to_datetime(["2026-03-02"]),
            "fecha_entrega_real": pd.to_datetime(["2026-03-02"]),
            "fecha_estimada": pd.to_datetime(["2026-03-02"]),
            "fecha_inicio_ruta": pd.to_datetime(["2026-03-02"]),
            "dias_retraso": [0.0],
            "entrega_on_time": [5],  # inválido: debe ser 0/1
            "flag_no_entregado": [0],
            "activa": pd.Series([True], dtype="boolean"),
            "_silver_timestamp": ["2026-04-30T00:00:00+00:00"],
        }
    )
    with pytest.raises(pa.errors.SchemaError):
        schemas.validate(bad, schemas.SILVER_VIAJES_SCHEMA, name="silver-bad")


def test_pipeline_completo_pasa_todos_los_schemas(tmp_path: Path) -> None:
    """Bronze → silver → gold sobre la muestra real anonimizada.

    Si cualquier schema rechazara los datos reales, este test fallaria.
    La validacion ocurre dentro de cada `compute_*`/`transform_*`, asi que
    si llegamos al final sin excepcion, todos los schemas pasaron.
    """
    bronze_dir = tmp_path / "bronze"
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"

    bronze.ingest_all(input_path=SAMPLE, output_dir=bronze_dir)
    silver.silverize_all(input_dir=bronze_dir, output_dir=silver_dir)
    outputs = gold.goldify_all(input_dir=silver_dir, output_dir=gold_dir, exports_dir=None)

    assert len(outputs) == len(gold.GOLD_TABLES_ORDER)
    for path in outputs.values():
        assert path.exists()
