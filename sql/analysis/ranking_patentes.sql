-- ranking_patentes — ranking de vehículos por desempeño operativo.
--
-- Pattern showcase:
-- - DENSE_RANK() OVER (...) para ranking compacto (sin saltos cuando hay empates).
-- - ROW_NUMBER() OVER (...) para identificador único secuencial.
-- - Tie-breaker explícito en ORDER BY del window: cuando dos patentes empatan
--   en pct_on_time, gana la que tenga menos no_entregados, y luego la que cubra
--   más rutas (más versátil).
-- - GROUP BY + métricas agregadas + window function en el mismo SELECT (DuckDB
--   lo permite sin necesidad de CTE).
--
-- Útil para: "¿quién es el mejor camión? ¿cómo se ve la diferencia entre top 3
-- y resto?".

WITH metricas AS (
    SELECT
        patente,
        COUNT(*)                                 AS total_entregas,
        SUM(entrega_on_time)                     AS on_time_count,
        ROUND(AVG(entrega_on_time)   * 100, 2)   AS pct_on_time,
        SUM(flag_no_entregado)                   AS no_entregados,
        ROUND(AVG(dias_retraso),         2)      AS retraso_prom_dias,
        COUNT(DISTINCT id_ruta)                  AS rutas_distintas,
        COUNT(DISTINCT region)                   AS regiones_cubiertas
    FROM read_parquet('{silver_dir}/silver_viajes.parquet')
    GROUP BY patente
)
SELECT
    DENSE_RANK() OVER (
        ORDER BY pct_on_time DESC,
                 no_entregados ASC,
                 rutas_distintas DESC
    )                                            AS rank_general,
    ROW_NUMBER() OVER (
        ORDER BY pct_on_time DESC,
                 no_entregados ASC,
                 rutas_distintas DESC,
                 patente ASC
    )                                            AS row_num,
    patente,
    total_entregas,
    on_time_count,
    pct_on_time,
    no_entregados,
    retraso_prom_dias,
    rutas_distintas,
    regiones_cubiertas
FROM metricas
ORDER BY rank_general, patente;
