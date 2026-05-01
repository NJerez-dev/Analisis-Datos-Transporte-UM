-- gold_kpi_entregas — KPI global de entregas, una sola fila.
--
-- Patrón: subqueries escalares + cross join con devoluciones para calcular
-- la tasa de devolución sin tener que joinear fila por fila.
--
-- Equivalente a transporte.gold.compute_kpi_entregas (regression-tested).

WITH viajes AS (
    SELECT *
    FROM read_parquet('{silver_dir}/silver_viajes.parquet')
),
devoluciones AS (
    SELECT *
    FROM read_parquet('{silver_dir}/silver_devoluciones.parquet')
),
agregados AS (
    SELECT
        COUNT(*)                                                   AS total_viajes,
        SUM(CASE WHEN estado = 'Terminado' THEN 1 ELSE 0 END)      AS viajes_terminados,
        SUM(entrega_on_time)                                       AS viajes_on_time,
        ROUND(AVG(entrega_on_time)   * 100, 2)                     AS pct_on_time_delivery,
        ROUND(AVG(flag_no_entregado) * 100, 2)                     AS pct_no_entregado,
        ROUND(AVG(dias_retraso),       2)                          AS lead_time_dias_prom,
        COUNT(DISTINCT id_ruta)                                    AS rutas_unicas,
        COUNT(DISTINCT patente)                                    AS patentes_activas,
        ROUND(SUM(volumen),            4)                          AS volumen_total_m3
    FROM viajes
),
total_dev AS (
    SELECT COUNT(*) AS total_devoluciones FROM devoluciones
)
SELECT
    a.total_viajes,
    a.viajes_terminados,
    a.viajes_on_time,
    a.pct_on_time_delivery,
    a.pct_no_entregado,
    a.lead_time_dias_prom,
    d.total_devoluciones,
    ROUND(d.total_devoluciones::DOUBLE / NULLIF(a.total_viajes, 0) * 100, 2)  AS tasa_devolucion_pct,
    a.rutas_unicas,
    a.patentes_activas,
    a.volumen_total_m3
FROM agregados a
CROSS JOIN total_dev d;
