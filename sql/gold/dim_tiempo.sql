-- gold_dim_tiempo — dimensión calendario entre min y max de fecha_pactada.
--
-- Patrón: GENERATE_SERIES + extracción de partes de fecha. DuckDB tiene
-- generate_series con tipo DATE, lo que evita escribir bucles Python para
-- crear la dimensión.
--
-- Equivalente a transporte.gold.compute_dim_tiempo.

WITH rango AS (
    SELECT
        MIN(fecha_pactada)::DATE AS fecha_min,
        MAX(fecha_pactada)::DATE AS fecha_max
    FROM read_parquet('{silver_dir}/silver_viajes.parquet')
    WHERE fecha_pactada IS NOT NULL
),
fechas AS (
    SELECT
        unnest(generate_series(r.fecha_min, r.fecha_max, INTERVAL '1 day'))::DATE AS fecha
    FROM rango r
)
-- Nota sobre dia_semana: alineado a la convención Python (pandas.dayofweek):
-- lunes=0, martes=1, ..., domingo=6. DuckDB EXTRACT(DOW) usa la convención
-- PostgreSQL (domingo=0, ..., sábado=6); por eso aplicamos `(DOW + 6) % 7`.
SELECT
    strftime(fecha, '%Y-%m-%d')                              AS fecha,
    EXTRACT(YEAR    FROM fecha)::BIGINT                      AS anio,
    EXTRACT(MONTH   FROM fecha)::BIGINT                      AS mes,
    strftime(fecha, '%B')                                    AS nombre_mes,
    EXTRACT(DAY     FROM fecha)::BIGINT                      AS dia,
    ((EXTRACT(DOW FROM fecha)::BIGINT + 6) % 7)              AS dia_semana,
    strftime(fecha, '%A')                                    AS nombre_dia,
    EXTRACT(WEEK    FROM fecha)::BIGINT                      AS semana_anio,
    EXTRACT(QUARTER FROM fecha)::BIGINT                      AS trimestre,
    (CASE WHEN ((EXTRACT(DOW FROM fecha)::BIGINT + 6) % 7) >= 5 THEN 1 ELSE 0 END)::BIGINT AS es_fin_semana,
    strftime(fecha, '%Y-%m')                                 AS anio_mes
FROM fechas
ORDER BY fecha;
