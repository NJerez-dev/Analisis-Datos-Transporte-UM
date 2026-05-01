-- gold_kpi_por_patente — KPI agrupado por patente (camión), ordenado por on_time desc.
--
-- Patrón: GROUP BY + STRING_AGG con DISTINCT para concatenar clientes y regiones
-- únicas por vehículo. ORDER BY pct_on_time DESC al final para mostrar mejores
-- vehículos arriba (mismo orden que la versión pandas).
--
-- Equivalente a transporte.gold.compute_kpi_por_patente.

SELECT
    patente,
    COUNT(*)                                                  AS total_entregas,
    SUM(entrega_on_time)                                      AS on_time_count,
    ROUND(AVG(entrega_on_time)   * 100, 2)                    AS pct_on_time,
    ROUND(AVG(dias_retraso),         2)                       AS retraso_prom_dias,
    SUM(flag_no_entregado)                                    AS no_entregados,
    STRING_AGG(DISTINCT commerce, ', ' ORDER BY commerce)     AS commerce_clientes,
    STRING_AGG(DISTINCT region,   ', ' ORDER BY region)       AS regiones_cubiertas,
    COUNT(DISTINCT id_ruta)                                   AS rutas_asignadas
FROM read_parquet('{silver_dir}/silver_viajes.parquet')
GROUP BY patente
ORDER BY pct_on_time DESC, patente;
