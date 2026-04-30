.PHONY: help setup lint format test sample run-bronze run-silver run-gold run-all clean

help:  ## Lista los targets disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup:  ## Sincroniza el entorno con uv (instala Python si falta)
	uv sync

lint:  ## Corre ruff sobre src, scripts y tests
	uv run ruff check src scripts tests

format:  ## Formatea con ruff
	uv run ruff format src scripts tests

test:  ## Corre pytest
	uv run pytest

sample:  ## Regenera la muestra anonimizada desde data/raw/
	uv run python scripts/build_sample.py

run-bronze:  ## Ejecuta capa bronze (TBD: src/transporte/bronze.py)
	uv run python -m transporte.bronze

run-silver:  ## Ejecuta capa silver (TBD: src/transporte/silver.py)
	uv run python -m transporte.silver

run-gold:  ## Ejecuta capa gold (TBD: src/transporte/gold.py)
	uv run python -m transporte.gold

run-all: run-bronze run-silver run-gold  ## Pipeline completo bronze -> silver -> gold

clean:  ## Borra outputs y caches
	rm -rf data/processed/* .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
