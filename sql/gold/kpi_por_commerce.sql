-- gold_kpi_por_commerce — KPI agrupado por cliente (commerce).
--
-- Patrón: GROUP BY + agregados + ROUND para compatibilidad con la versión pandas.
--
-- Equivalente a transporte.gold.compute_kpi_por_commerce.

SELECT
    commerce,
    COUNT(*)                                       AS total_viajes,
    SUM(entrega_on_time)                           AS on_time_count,
    ROUND(AVG(entrega_on_time)   * 100, 2)         AS pct_on_time,
    ROUND(AVG(dias_retraso),         2)            AS lead_time_prom_dias,
    SUM(flag_no_entregado)                         AS no_entregados,
    ROUND(AVG(flag_no_entregado) * 100, 2)         AS pct_no_entregado,
    ROUND(SUM(volumen),              4)            AS volumen_total,
    COUNT(DISTINCT id_ruta)                        AS rutas_unicas,
    COUNT(DISTINCT patente)                        AS patentes_unicas
FROM read_parquet('{silver_dir}/silver_viajes.parquet')
GROUP BY commerce
ORDER BY commerce;
