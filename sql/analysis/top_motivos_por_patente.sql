-- top_motivos_por_patente — top 2 motivos de no entrega por vehículo.
--
-- Pattern showcase:
-- - QUALIFY: filtra sobre el resultado de window functions sin necesidad de
--   anidar SELECT/WITH. Más limpio que `WHERE rk <= N` en una subquery.
-- - PARTITION BY ... ORDER BY ... define el "ranking dentro del grupo".
-- - RANK() (no DENSE_RANK) para que si dos motivos empatan en cantidad,
--   ambos aparezcan con el mismo rank y se salte el siguiente.
--
-- Útil para: "¿qué motivo es el principal por cada camión? ¿el top 1 es el
-- mismo en todos o cambia?".

WITH motivos_por_patente AS (
    SELECT
        patente,
        motivo_no_entrega,
        COUNT(*) AS cantidad
    FROM read_parquet('{silver_dir}/silver_viajes.parquet')
    WHERE motivo_no_entrega IS NOT NULL
      AND motivo_no_entrega <> ''
    GROUP BY patente, motivo_no_entrega
)
SELECT
    patente,
    motivo_no_entrega,
    cantidad,
    RANK() OVER (
        PARTITION BY patente
        ORDER BY cantidad DESC
    ) AS rk_motivo
FROM motivos_por_patente
QUALIFY rk_motivo <= 2
ORDER BY patente, rk_motivo, motivo_no_entrega;
