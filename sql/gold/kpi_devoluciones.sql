-- gold_kpi_devoluciones — KPI de devoluciones agrupado por motivo (observaciones).
--
-- Patrón: GROUP BY + window function SUM() OVER () para calcular el porcentaje
-- del total sin tener que hacer una segunda pasada al DataFrame. Ordenado por
-- cantidad descendente.
--
-- Equivalente a transporte.gold.compute_kpi_devoluciones.

WITH agregados AS (
    SELECT
        observaciones,
        COUNT(nro_etiqueta)                                AS cantidad,
        ROUND(AVG(dias_hasta_devolucion::DOUBLE), 1)       AS dias_devolucion_prom
    FROM read_parquet('{silver_dir}/silver_devoluciones.parquet')
    GROUP BY observaciones
)
SELECT
    observaciones,
    cantidad,
    dias_devolucion_prom,
    ROUND(cantidad::DOUBLE / SUM(cantidad) OVER () * 100, 2)  AS pct_del_total
FROM agregados
ORDER BY cantidad DESC, observaciones;
