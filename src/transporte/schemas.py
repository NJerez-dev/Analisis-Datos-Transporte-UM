"""Schemas Pandera — contratos de datos por capa.

Cada DataFrame que producen `bronze`, `silver` y `gold` se valida contra el
schema correspondiente al final de su función productora. La validación es
**permisiva** por diseño:

- Verifica presencia y tipo de columnas obligatorias.
- No verifica valores de negocio específicos (ej. lista cerrada de estados).
- `strict=False`: si llegan columnas extra del Excel, no se rompen los
  schemas; solo las nombradas son validadas.

Si una validación falla, el error de pandera apunta a la fila y columna
exacta del problema, lo que sirve como sistema de alerta temprana para
schema drift en la fuente.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

# Helpers para hacer schemas legibles sin pasar 100 chars por línea.
_RANGE_PCT = (Check.greater_than_or_equal_to(0), Check.less_than_or_equal_to(100))
_RANGE_MES = (Check.greater_than_or_equal_to(1), Check.less_than_or_equal_to(12))
_RANGE_DIA = (Check.greater_than_or_equal_to(1), Check.less_than_or_equal_to(31))
_RANGE_TRIMESTRE = (Check.greater_than_or_equal_to(1), Check.less_than_or_equal_to(4))
_NON_NEG = Check.greater_than_or_equal_to(0)
_BINARY = Check.isin([0, 1])

# ---------------------------------------------------------------------------
# Bronze — todo string + metadata de ingesta
# ---------------------------------------------------------------------------

_BRONZE_METADATA_COLUMNS: dict[str, Column] = {
    "_ingesta_timestamp": Column(str, nullable=False),
    "_fuente": Column(str, nullable=False),
    "_archivo": Column(str, nullable=False),
}

BRONZE_VIAJES_SCHEMA = DataFrameSchema(
    columns={
        "Suborden": Column(str, nullable=True),
        "Do": Column(str, nullable=True),
        "Estado": Column(str, nullable=True),
        "Patente": Column(str, nullable=True),
        "Empresa": Column(str, nullable=True),
        "Idruta": Column(str, nullable=True),
        "Fechapactada": Column(str, nullable=True),
        "Commerce": Column(str, nullable=True),
        **_BRONZE_METADATA_COLUMNS,
    },
    coerce=False,
    strict=False,
)

BRONZE_DEVOLUCIONES_SCHEMA = DataFrameSchema(
    columns={
        "nro_recepcion": Column(str, nullable=True),
        "nro_etiqueta": Column(str, nullable=True),
        "patente": Column(str, nullable=True),
        "fecha_viaje": Column(str, nullable=True),
        "fecha_devolucion": Column(str, nullable=True),
        "estado_devolucion": Column(str, nullable=True),
        **_BRONZE_METADATA_COLUMNS,
    },
    coerce=False,
    strict=False,
)


# ---------------------------------------------------------------------------
# Silver — tipos correctos, snake_case, KPIs operativos básicos
# ---------------------------------------------------------------------------

_SILVER_TIMESTAMP = Column(str, nullable=False)


SILVER_VIAJES_SCHEMA = DataFrameSchema(
    columns={
        "suborden": Column(str, nullable=True),
        "documento": Column(str, nullable=True),
        "estado": Column(str, nullable=True),
        "patente": Column(str, nullable=True),
        "id_ruta": Column(str, nullable=True),
        "centro_transporte": Column(str, nullable=True),
        "region": Column(str, nullable=True),
        "commerce": Column(str, nullable=True),
        "volumen": Column(float, nullable=True, checks=_NON_NEG),
        "fecha_pactada": Column("datetime64[ns]", nullable=True),
        "fecha_entrega_real": Column("datetime64[ns]", nullable=True),
        "fecha_estimada": Column("datetime64[ns]", nullable=True),
        "fecha_inicio_ruta": Column("datetime64[ns]", nullable=True),
        "dias_retraso": Column(float, nullable=True),
        "entrega_on_time": Column(int, checks=_BINARY),
        "flag_no_entregado": Column(int, checks=_BINARY),
        "activa": Column("boolean", nullable=True),
        "_silver_timestamp": _SILVER_TIMESTAMP,
    },
    coerce=False,
    strict=False,
)

SILVER_DEVOLUCIONES_SCHEMA = DataFrameSchema(
    columns={
        "nro_recepcion": Column(str, nullable=True),
        "nro_etiqueta": Column(str, nullable=True),
        "patente": Column(str, nullable=True),
        "fecha_viaje": Column("datetime64[ns]", nullable=True),
        "fecha_devolucion": Column("datetime64[ns]", nullable=True),
        "estado_devolucion": Column(str, nullable=True),
        "observaciones": Column(str, nullable=True),
        "dias_hasta_devolucion": Column(float, nullable=True),
        "_silver_timestamp": _SILVER_TIMESTAMP,
    },
    coerce=False,
    strict=False,
)


# ---------------------------------------------------------------------------
# Gold — KPIs y modelo dimensional
# ---------------------------------------------------------------------------

_GOLD_TIMESTAMP = Column(str, nullable=False)


GOLD_KPI_ENTREGAS_SCHEMA = DataFrameSchema(
    columns={
        "total_viajes": Column(int, checks=_NON_NEG),
        "viajes_terminados": Column(int, checks=_NON_NEG),
        "viajes_on_time": Column(int, checks=_NON_NEG),
        "pct_on_time_delivery": Column(float, checks=list(_RANGE_PCT)),
        "pct_no_entregado": Column(float, checks=list(_RANGE_PCT)),
        "lead_time_dias_prom": Column(float, nullable=True),
        "total_devoluciones": Column(int, checks=_NON_NEG),
        "tasa_devolucion_pct": Column(float, checks=_NON_NEG),
        "rutas_unicas": Column(int, checks=_NON_NEG),
        "patentes_activas": Column(int, checks=_NON_NEG),
        "volumen_total_m3": Column(float, checks=_NON_NEG),
        "_gold_timestamp": _GOLD_TIMESTAMP,
    },
    coerce=False,
    strict=False,
)


GOLD_KPI_POR_COMMERCE_SCHEMA = DataFrameSchema(
    columns={
        "commerce": Column(str, nullable=True),
        "total_viajes": Column(int, checks=_NON_NEG),
        "pct_on_time": Column(float, checks=list(_RANGE_PCT)),
        "pct_no_entregado": Column(float, checks=list(_RANGE_PCT)),
        "_gold_timestamp": _GOLD_TIMESTAMP,
    },
    coerce=False,
    strict=False,
)


GOLD_KPI_POR_PATENTE_SCHEMA = DataFrameSchema(
    columns={
        "patente": Column(str, nullable=True),
        "total_entregas": Column(int, checks=_NON_NEG),
        "pct_on_time": Column(float, checks=list(_RANGE_PCT)),
        "_gold_timestamp": _GOLD_TIMESTAMP,
    },
    coerce=False,
    strict=False,
)


GOLD_KPI_DEVOLUCIONES_SCHEMA = DataFrameSchema(
    columns={
        "observaciones": Column(str, nullable=True),
        "cantidad": Column(int, checks=_NON_NEG),
        "pct_del_total": Column(float, checks=list(_RANGE_PCT)),
        "_gold_timestamp": _GOLD_TIMESTAMP,
    },
    coerce=False,
    strict=False,
)


GOLD_DIM_TIEMPO_SCHEMA = DataFrameSchema(
    columns={
        "fecha": Column(str, nullable=False),
        "anio": Column(int, checks=Check.greater_than(2000)),
        "mes": Column(int, checks=list(_RANGE_MES)),
        "dia": Column(int, checks=list(_RANGE_DIA)),
        "trimestre": Column(int, checks=list(_RANGE_TRIMESTRE)),
        "es_fin_semana": Column(int, checks=_BINARY),
    },
    coerce=False,
    strict=False,
)


GOLD_FACT_VIAJES_SCHEMA = DataFrameSchema(
    columns={
        "suborden": Column(str, nullable=True),
        "estado": Column(str, nullable=True),
        "patente": Column(str, nullable=True),
        "commerce": Column(str, nullable=True),
        "fecha_pactada": Column("datetime64[ns]", nullable=True),
        "entrega_on_time": Column(int, checks=_BINARY),
        "flag_no_entregado": Column(int, checks=_BINARY),
        "fecha_key": Column(str, nullable=True),
        "_gold_timestamp": _GOLD_TIMESTAMP,
    },
    coerce=False,
    strict=False,
)


def validate(df: pd.DataFrame, schema: DataFrameSchema, *, name: str = "") -> pd.DataFrame:
    """Valida `df` contra `schema`. Devuelve el mismo DataFrame para encadenar.

    Lanza `pandera.errors.SchemaError` con detalle de la violación si falla.
    """
    try:
        return schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:  # pragma: no cover - solo se ejecuta en fallo
        msg = f"Schema validation failed for {name or 'dataframe'}: {exc.failure_cases}"
        raise pa.errors.SchemaError(schema, df, msg) from exc
