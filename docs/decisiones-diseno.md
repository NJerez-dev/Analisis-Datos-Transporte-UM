# Decisiones de diseño

Documento que recoge las decisiones técnicas no triviales del refactor del proyecto, con sus alternativas consideradas y las consecuencias asumidas. El "qué" se ve en el código; este archivo cubre el "por qué".

## 1. Arquitectura medallón (bronze / silver / gold)

**Decisión**: dividir el pipeline en tres capas con responsabilidades estrictas.

| Capa | Hace | NO hace |
|---|---|---|
| **Bronze** | Lee la fuente y la persiste como Parquet, con metadata de ingesta. Todo string. | Inferencia de tipos. Joins. Validación de negocio. |
| **Silver** | Tipa, normaliza texto, calcula columnas derivadas. Datos confiables para analytics. | Agregaciones por dimensión. Modelo dimensional. |
| **Gold** | Agregaciones, KPIs, modelo dimensional (fact + dim). Listo para BI. | Reglas de negocio nuevas. Joins con fuentes externas. |

**Alternativa descartada**: un único notebook que hace todo end-to-end. Es lo que se hace en exploraciones rápidas, pero no escala: cualquier cambio tiene impacto difuso, no se pueden testar partes en aislamiento, y el debugging cuando algo se rompe es lineal.

**Consecuencia asumida**: el pipeline tiene 3 binarios (`python -m transporte.{bronze,silver,gold}`) en lugar de 1. A cambio: cada capa es testeable, debuggeable y reemplazable independientemente.

## 2. Parquet en lugar de SQLite (que era el formato del notebook original)

**Decisión**: persistir todas las salidas intermedias y finales en Parquet con `pyarrow`.

**Razones**:

- **Tipado nativo**: Parquet preserva `datetime64`, `Float64` nullable, `boolean` nullable. SQLite todo lo aplana a TEXT/INTEGER/REAL y hay que recargar tipos al leer.
- **Columnar y comprimido**: I/O 10-50x más rápido que CSV/SQLite cuando se leen pocas columnas de tablas grandes.
- **Estándar moderno**: lo que pide cualquier Data Lake (S3 + Athena, GCS + BigQuery, Databricks, Snowflake external tables). Migración futura sin reescribir.
- **Zero-copy con DuckDB / Polars / Spark**: si el dataset crece, el siguiente motor lo come directo sin transformación.

**Alternativa descartada (SQLite)**: era cómodo en Colab pero acopla el pipeline a un motor que no se usa en producción de DE. Hubiera obligado a re-aprender Parquet más adelante.

**Excepción**: la capa Gold también escribe **CSVs UTF-8 BOM** en `data/exports/` para Power BI, porque PBI consume CSV nativamente y trabajar con Parquet desde PBI es una capa extra de fricción.

## 3. `uv` en lugar de `pip + venv` o `poetry`

**Decisión**: gestor de entorno y dependencias 100% sobre `uv`.

**Razones**:

- **Velocidad**: 10-100x más rápido que `pip install`. Resolución del lockfile en segundos.
- **Lockfile determinista** (`uv.lock`): instala exactamente las mismas versiones en cualquier máquina. No hay "funciona en mi máquina".
- **Gestiona Python**: instala la versión declarada en `.python-version` automáticamente, sin pyenv ni asdf.
- **Estándar moderno**: pyproject.toml + lockfile siguen PEP 621 / PEP 735.

**Alternativa descartada (poetry)**: maduro, pero más lento y con su propio formato de lockfile. `uv` está construido sobre estándares PEP, lo que reduce dependencia de un proveedor.

## 4. Bronze estricto: solo string + metadata

**Decisión**: la capa Bronze persiste todos los valores como string, sin inferencia de tipos.

**Razones**:

- Si la fuente cambia (un Excel mal exportado, un campo nuevo, un valor inesperado), Bronze nunca falla por inferencia mal hecha. Toda la complejidad de "cómo interpretar este string" vive en Silver, donde se puede testar y validar.
- Permite reprocesar histórico sin perder datos: si Silver cambia su lógica de parsing, Bronze sigue siendo la fuente fiel.

**Excepción mínima**: en la hoja `DEVOLUCIONES`, las columnas con caracteres no-ASCII (`N° Recepción`, `Fecha devolución`) se renombran a snake_case ASCII. Razón: Parquet y SQL no aceptan headers con caracteres especiales, y este renombrado **no pierde información**.

## 4b. Engine dual en Gold (SQL como default, pandas como fallback)

**Decisión** (30 abr 2026): la capa Gold acepta `engine="sql"` (default) o `engine="pandas"`. SQL ejecuta las queries de `sql/gold/*.sql` con DuckDB; pandas ejecuta las funciones `compute_*` del módulo. Ambos producen los mismos Parquets/CSVs.

**Razones**:

- **SQL es el lenguaje del rol DE**. Tener `.sql` versionados pesa más en una entrevista que cualquier cantidad de pandas. Esta decisión convierte el SQL en la fuente de verdad operativa.
- **Pandas se mantiene como fallback útil**: para exploración interactiva en notebooks, para construir tests sintéticos sin necesitar disco, y como segunda implementación que detecta divergencias en SQL vía tests de regresión.
- **Tests cruzados** (`tests/test_gold_engines.py`) verifican que ambos producen el mismo output con tolerancia 1e-3. Si SQL diverge, el test falla con la columna y fila exactas del problema.

**Alternativa descartada (solo SQL)**: borrar `compute_*` pandas. Más limpio en el corto plazo, pero pierdes la red de seguridad que detecta bugs de SQL durante el desarrollo. Mantenerlos cuesta poco código y ahorra mucho debugging.

**Costo asumido**: dos lugares para mantener la lógica si la regla de negocio cambia. Mitigación: los tests de regresión disparan el día que alguien edite uno y olvide el otro.

**Aprendizaje del proceso**: la primera versión SQL de `dim_tiempo` usaba `EXTRACT(DOW FROM fecha)` (convención PostgreSQL: domingo=0..sábado=6) y eso divergía de pandas (`dayofweek` con convención Python: lunes=0..domingo=6). Sin tests de regresión, este bug habría salido en producción. La fórmula correcta en DuckDB es `(EXTRACT(DOW FROM fecha)::BIGINT + 6) % 7`.

## 5. Validación con Pandera al final de cada capa

**Decisión**: cada función productora (`ingest_*`, `transform_*`, `compute_*`) valida su output contra un `DataFrameSchema` antes de retornarlo.

**Razones**:

- **Contratos explícitos**: el schema documenta qué garantiza cada capa. Si silver cambia algo que rompe gold, el test detecta el problema antes que el dashboard.
- **Schema drift en la fuente**: si mañana el Excel viene con una columna nueva o un tipo distinto, pandera dispara un error con la celda exacta del problema. Es alerta temprana.
- **Permisivo por diseño** (`strict=False`): no rechaza si llegan columnas extra. Solo valida lo que está nombrado en el schema. Esto evita que el pipeline se rompa por cambios benignos en la fuente.

**Alternativa descartada (asserts dispersos)**: funciona pero los asserts no centralizan el contrato; quedan repartidos en docenas de líneas.

**Costo asumido**: pandera agrega ~100 ms al pipeline por validación. Aceptable para un pipeline batch.

## 6. Muestra anonimizada versionada en `data/sample/`

**Decisión**: incluir 50 viajes + 25 devoluciones anonimizados en el repo, generables vía `scripts/build_sample.py`.

**Razones**:

- **CI puede correr el pipeline completo** sin acceso al dataset original. Los tests de integración usan esta muestra.
- **Cualquiera que clone el repo puede ejecutar el pipeline** sin pedir el crudo. Ideal para demostración / portafolio.
- **Anonimización determinista** (hash SHA1 con prefijo): el mismo `Suborden` original siempre da el mismo `SUB_XXXXX` en la muestra. Eso preserva relaciones entre hojas y permite seguir un viaje en distintas tablas, sin exponer el ID real.

**Alternativa descartada (datos sintéticos)**: serían más seguros pero perderían la "forma" real del dataset (distribución de estados, motivos de no entrega, etc.). La anonimización determinista es un buen compromiso.

## 7. Single PR para todo el bloque 1 vs PRs por sub-bloque

**Decisión** (revisada el 30 abr 2026): trabajar todo el bloque 1 en una sola rama `refactor/bloque-1` y mergear con un único PR al final.

**Razones**:

- 4 PRs encadenados son fricción innecesaria para un proyecto personal.
- El historial de commits dentro del branch ya documenta el progreso por sub-bloque.
- Cuando alguien revise el repo verá un PR grande y bien documentado, no un goteo de 4-5 PRs.

**Alternativa descartada (stacked PRs)**: válida en equipos donde cada PR necesita revisión independiente. Aquí no aplica.

## 8. Cobertura objetivo 80%, real 88%

**Decisión**: configurar CI con `--cov-fail-under=80` para fallar el build si baja la cobertura.

**Razones**:

- 100% es performativo: forzaría tests sobre los `argparse` y los `__main__` que no aportan valor.
- 80% es un piso defensivo: cubre toda la lógica de negocio + la mayoría de los happy paths de I/O. Lo que queda fuera son CLI handlers y branches de error de logging.

**Costo asumido**: si en una refactorización futura alguien remueve tests sin reemplazarlos, el CI se rompe. Eso es una _feature_, no un _bug_.

## 9. Logging en lugar de print

**Decisión**: cada módulo declara su `log = logging.getLogger(__name__)` y usa `log.info / log.warning` en operaciones relevantes. El `main()` configura `logging.basicConfig` con formato `%(asctime)s | %(levelname)s | %(name)s | %(message)s`.

**Razones**:

- Por defecto solo logea INFO+. Los logs DEBUG están disponibles sin cambiar código (`--log-level DEBUG`).
- Los handlers son configurables: si en producción hay que enviar logs a CloudWatch o stdout JSON, solo cambia la configuración de `basicConfig`, no el código.

**Alternativa descartada (print)**: aceptable en notebooks. Inaceptable en producción porque no se puede silenciar selectivamente ni redirigir.

## 10. CI con GitHub Actions (`ubuntu-latest`)

**Decisión**: pipeline CI que corre en cada push a `main` y `refactor/**` y en cada PR contra `main`.

**Pasos del workflow**:

1. Checkout.
2. Instala `uv` con cache de dependencias.
3. Instala Python 3.12.
4. `uv sync --frozen` (usa el lockfile, no resuelve nuevas versiones).
5. `ruff check`.
6. `ruff format --check`.
7. `pytest --cov-fail-under=80`.
8. Sube `coverage.xml` como artifact.

**Ubuntu, no Windows**: aunque desarrollas en Windows, GitHub Actions corre el workflow en Ubuntu (más rápido, más barato, mismo Python). El proyecto tiene que funcionar en ambos. Si en algún momento aparece un bug Windows-only, agregamos un job de matriz.

## Limitaciones conocidas (no resueltas en este bloque)

- **Sin orquestador real**: los pasos se encadenan vía CLI manual o `make`. Para el bloque 4 del roadmap personal, migrar a Airflow / Prefect / Dagster.
- **Sin ingestión incremental**: cada corrida procesa el dataset completo. Funciona para el volumen actual (1.013 filas); a 1M+ habría que agregar marca de tiempo y particionado.
- **Sin tests de regresión sobre dashboard**: cambios en gold pueden romper el dashboard sin alerta. Mitigación a futuro: snapshot tests sobre los CSVs de export.
- **`make` no preinstalado en Windows**: el Makefile sirve como atajo en Linux/Mac/WSL/Git Bash con make instalado. En Windows desnudo, los comandos `uv run python -m transporte.X` documentados en el README son la fuente de verdad.
