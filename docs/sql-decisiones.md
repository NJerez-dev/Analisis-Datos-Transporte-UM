# Decisiones SQL — patrones, optimización y `EXPLAIN`

Este documento recoge los patrones SQL usados en `sql/gold/` y `sql/analysis/`, con foco en por qué se eligió cada uno y qué muestra el plan de ejecución de DuckDB.

Para correr `EXPLAIN` localmente sobre cualquier query:

```bash
uv run python -c "
from pathlib import Path
import duckdb
sql = Path('sql/gold/kpi_entregas.sql').read_text(encoding='utf-8').format(silver_dir='data/processed')
con = duckdb.connect(':memory:')
print('\\n'.join(row[1] for row in con.execute(f'EXPLAIN {sql}').fetchall()))
"
```

## Patrones usados

### 1. CTEs (`WITH`) para subqueries escalares legibles

**Dónde**: `sql/gold/kpi_entregas.sql`, `sql/gold/kpi_devoluciones.sql`, `sql/analysis/ranking_patentes.sql`.

```sql
WITH metricas AS (
    SELECT patente, COUNT(*) AS total_entregas, ...
    FROM read_parquet(...)
    GROUP BY patente
)
SELECT DENSE_RANK() OVER (ORDER BY pct_on_time DESC) AS rank_general, ...
FROM metricas
ORDER BY rank_general;
```

**Razón**: el CTE separa claramente las **dos pasadas** que hace la query (agregación → ranking). Sin CTE el SELECT externo se convierte en una subquery anidada, ilegible.

**Lo que muestra `EXPLAIN`**: DuckDB no materializa el CTE — es puramente sintáctico. El plan colapsa los dos niveles en una sola pasada cuando puede.

### 2. Window functions: `RANK`, `DENSE_RANK`, `ROW_NUMBER`, `SUM() OVER ()`

**Dónde**: `kpi_devoluciones.sql` (`SUM() OVER ()` para `pct_del_total`), `ranking_patentes.sql` (`DENSE_RANK` y `ROW_NUMBER`).

```sql
SELECT
    cantidad,
    ROUND(cantidad::DOUBLE / SUM(cantidad) OVER () * 100, 2) AS pct_del_total
FROM agregados;
```

**Razón**: calcula el porcentaje del total en **una sola pasada**, sin un segundo SELECT con un total previamente computado. El plan muestra un nodo `WINDOW` que agrega la columna calculada sobre la salida del `HASH_GROUP_BY`.

**Cuándo elegir cuál**:
- `ROW_NUMBER()`: identificador único secuencial. Útil para paginación.
- `RANK()`: empates comparten valor, salta números (1, 2, 2, 4, 5...). Ideal cuando importa marcar el empate.
- `DENSE_RANK()`: empates comparten valor, no salta (1, 2, 2, 3, 4...). Ideal para ranking compacto que muestra la "categoría" del competidor.

### 3. `STRING_AGG(DISTINCT ... ORDER BY)`

**Dónde**: `sql/gold/kpi_por_patente.sql`.

```sql
STRING_AGG(DISTINCT commerce, ', ' ORDER BY commerce) AS commerce_clientes,
STRING_AGG(DISTINCT region,   ', ' ORDER BY region)   AS regiones_cubiertas
```

**Razón**: equivale al patrón pandas `lambda x: ', '.join(sorted(x.unique()))` en una agregación SQL nativa. Más declarativo y permite que el motor optimice.

### 4. `QUALIFY`: filtro sobre window functions sin subquery anidada

**Dónde**: `sql/analysis/top_motivos_por_patente.sql`.

```sql
SELECT patente, motivo_no_entrega, cantidad,
       RANK() OVER (PARTITION BY patente ORDER BY cantidad DESC) AS rk_motivo
FROM motivos_por_patente
QUALIFY rk_motivo <= 2
ORDER BY patente, rk_motivo;
```

**Razón**: alternativa SQL estándar moderna para "top N por grupo" sin tener que envolver todo en otra `SELECT`. Lo soporta DuckDB, Snowflake y BigQuery.

**Equivalente sin `QUALIFY`** (más feo):

```sql
SELECT * FROM (
    SELECT patente, motivo_no_entrega, cantidad,
           RANK() OVER (PARTITION BY patente ORDER BY cantidad DESC) AS rk_motivo
    FROM motivos_por_patente
) WHERE rk_motivo <= 2;
```

### 5. `generate_series` + `EXTRACT`: dimensión calendario sin loop Python

**Dónde**: `sql/gold/dim_tiempo.sql`.

```sql
WITH rango AS (SELECT MIN(fecha)::DATE AS fmin, MAX(fecha)::DATE AS fmax FROM ...),
fechas AS (SELECT unnest(generate_series(r.fmin, r.fmax, INTERVAL '1 day'))::DATE AS fecha
           FROM rango r)
SELECT EXTRACT(YEAR FROM fecha) AS anio, EXTRACT(MONTH FROM fecha) AS mes, ...
FROM fechas;
```

**Razón**: construir la dimensión tiempo es 100% SQL; en pandas requeriría `pd.date_range` + loop. La query es declarativa: "dame todas las fechas del rango y derívame las partes".

**Detalle no obvio**: `EXTRACT(DOW)` sigue convención PostgreSQL (`domingo=0`), mientras que `pandas.dayofweek` sigue Python (`lunes=0`). Para alinear con pandas: `(EXTRACT(DOW FROM fecha) + 6) % 7`. Está documentado en la query y en `decisiones-diseno.md` sección 4b.

### 6. `read_parquet()` con projection pushdown automático

**Dónde**: todas las queries.

```sql
SELECT estado, patente, id_ruta, volumen
FROM read_parquet('{silver_dir}/silver_viajes.parquet')
GROUP BY estado, patente;
```

**Lo que muestra `EXPLAIN`**:

```
READ_PARQUET
   Projections:
      estado, patente, id_ruta, volumen
   ~50 rows
```

**Razón**: aunque `silver_viajes.parquet` tiene 29 columnas, DuckDB solo lee las 4 que la query usa. Es la ventaja columnar de Parquet: I/O proporcional a las columnas accedidas, no al ancho total del archivo.

## Optimizaciones documentadas

### a) Filtrar antes de agrupar

Cuando una query filtra y agrupa, los filtros van **antes** del `GROUP BY`. DuckDB es lo bastante inteligente para reordenar, pero escribirlo así explícito reduce ambigüedad y a veces evita conversiones innecesarias.

**Ejemplo**: `top_motivos_por_patente.sql`:

```sql
WITH motivos_por_patente AS (
    SELECT patente, motivo_no_entrega, COUNT(*) AS cantidad
    FROM read_parquet(...)
    WHERE motivo_no_entrega IS NOT NULL    -- filtro early
      AND motivo_no_entrega <> ''
    GROUP BY patente, motivo_no_entrega    -- group by después
)
SELECT ... QUALIFY rk_motivo <= 2;
```

### b) `CROSS JOIN` con tabla 1×1 vs subquery escalar

`kpi_entregas.sql` usa `CROSS JOIN` entre dos CTEs cada uno con 1 fila para combinar agregados de viajes con el total de devoluciones:

```sql
SELECT a.*, d.total_devoluciones, ...
FROM agregados a CROSS JOIN total_dev d;
```

**Alternativa con subquery escalar** (también funciona):

```sql
SELECT a.*, (SELECT COUNT(*) FROM devoluciones) AS total_devoluciones
FROM agregados a;
```

DuckDB optimiza ambas a algo equivalente. El `CROSS JOIN` se elige porque es más legible cuando se cruzan **varios** valores escalares.

**Lo que muestra `EXPLAIN`**: aparece un nodo `CROSS_PRODUCT` que con 1×1 filas es trivial — costo despreciable.

### c) `HASH_GROUP_BY` vs `SORT + GROUP`

DuckDB elige `HASH_GROUP_BY` por defecto para agregaciones sin orden requerido. Es más rápido que `SORT + GROUP BY` para datos no ordenados. Solo se elige sort cuando la query final necesita orden y se puede aprovechar.

**Lo que muestra `EXPLAIN`**: nodos `HASH_GROUP_BY` en todas las queries con `GROUP BY`.

## Cosas que NO se hicieron (a propósito)

- **Indices manuales**: DuckDB en Parquet no usa índices al estilo PostgreSQL; usa estadísticas de columna y zone maps. Para 1.013 filas no hay nada que indexar.
- **Materialized views / caché de queries**: el dataset es chico, el pipeline corre rápido. Cuando crezca, evaluar `CREATE TABLE AS SELECT` y persistir intermedios.
- **Particionado**: actualmente todos los Parquet son archivos planos. Cuando el dataset cubra varios meses, particionar gold por `año/mes` (deferred al bloque 5 del roadmap).

## Cómo correr `EXPLAIN ANALYZE` (con tiempos reales)

```python
import duckdb
sql = "..."
con = duckdb.connect(":memory:")
result = con.execute(f"EXPLAIN ANALYZE {sql}").fetchall()
for row in result:
    print(row[1])
```

Para 1.013 filas todas las queries tardan <50 ms en máquina personal. La diferencia entre patrones es invisible en este volumen — el ejercicio es **didáctico**: aprender a leer planes para cuando el volumen importe.
