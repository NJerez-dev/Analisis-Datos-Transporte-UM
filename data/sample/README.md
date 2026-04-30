# Muestra anonimizada

Archivo: `transporte_um_sample.xlsx`

Generado por `scripts/build_sample.py` desde el dataset crudo `data/raw/transporte_um.xlsx` (no versionado).

## Tamaño
- Hoja `VIAJES DIARIOS`: 50 filas (de 1.013 originales).
- Hoja `DEVOLUCIONES`: 25 filas (de 275 originales).

Muestra reproducible con `random_state=42`.

## Anonimización aplicada

| Columna | Transformación |
|---|---|
| `Suborden`, `Do`, `Idruta`, `LPN`, `LPN_Container`, `ParentOrder` | Hash SHA1 corto (8 chars) con prefijo (`SUB_`, `DO_`, `RUT_`, etc.). Mismo input → mismo hash entre hojas. |
| `Patente` | Hash 6 chars con prefijo `VEH_`. |
| `Empresa` | Reemplazada por `EmpresaTransporteA` literal. |
| `Commerce` | Reemplazada por `ClienteRetailA` literal. |
| `Direccion` | Reemplazada por `"Direccion anonimizada"`. |
| `N° Recepción`, `N° de Etiqueta`, `N° de OC` (devoluciones) | Hash con prefijo `REC_`, `ETI_`, `OC_`. |
| `Observaciones` (devoluciones) | Reemplazada por `"Observacion anonimizada"`. |

Todo lo demás (fechas, estados, motivos, regiones, localidades, volúmenes) se preserva.

## Para qué sirve esta muestra

- **Tests de integración**: `pytest` corre el pipeline completo sobre estos datos y verifica conteos.
- **CI**: GitHub Actions usa esta muestra (no hace falta el crudo, que no se versiona).
- **Demostración**: cualquiera puede clonar el repo y correr el pipeline sin el dataset original.

Para análisis real se necesita `data/raw/transporte_um.xlsx`, que **no se distribuye** vía git.
