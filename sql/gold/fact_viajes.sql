-- gold_fact_viajes — tabla de hechos del modelo estrella, una fila por viaje.
--
-- Patrón: SELECT con proyección explícita + columna calculada fecha_key
-- para joinear con gold_dim_tiempo en el dashboard.
--
-- Equivalente a transporte.gold.compute_fact_viajes.

SELECT
    suborden,
    documento,
    estado,
    patente,
    commerce,
    id_ruta,
    posicion_ruta,
    centro_transporte,
    localidad,
    region,
    volumen,
    fecha_pactada,
    fecha_entrega_real,
    fecha_estimada,
    dias_retraso,
    entrega_on_time,
    flag_no_entregado,
    motivo_no_entrega,
    activa,
    strftime(fecha_pactada, '%Y-%m-%d') AS fecha_key
FROM read_parquet('{silver_dir}/silver_viajes.parquet');
