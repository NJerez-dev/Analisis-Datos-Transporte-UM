# 🚚 Análisis de Transporte de Última Milla

Este proyecto analiza la operación logística de última milla, evaluando el desempeño en entregas, nivel de servicio (OTD) y principales causas de ineficiencia en el proceso de distribución.

---

## 🔍 Principales Hallazgos

- Se analizaron **1,013 viajes**, de los cuales:
  - **530 fueron completados**
  - **292 permanecen pendientes**
- A pesar de un **OTD del 100% en viajes finalizados**, existe un alto nivel de incidencias operacionales.
- **47.7% de los viajes no fueron entregados**, lo que representa un riesgo crítico para la operación.
- La **tasa de devolución alcanza un 27.2%**, indicando fallas en la ejecución de entregas.
- El principal problema detectado es **"Producto no cargado" (133 casos)**, evidenciando fallas en procesos de preparación en bodega.

---

## ⚙️ Metodología

- Modelamiento de datos mediante **arquitectura Medallón (Bronze, Silver, Gold)**
- Procesamiento y análisis de datos logísticos
- Visualización de KPIs mediante dashboard

---

## 📊 Análisis del Desempeño

### 📦 Estado de los Viajes
La operación presenta una distribución desigual entre viajes completados, pendientes y planificados, con una proporción importante aún sin ejecutar.

### 🚨 Motivos de No Entrega
Principales causas identificadas:
- **Producto no cargado:** 133 casos
- **Sin moradores:** 115 casos
- **Tiempo excedido:** 41 casos

> ⚠️ **Insight clave:**  
> La mayor parte de las fallas no dependen del transporte, sino de procesos previos (bodega y preparación de pedidos).

---

### 🔁 Devoluciones
- Total: **275 devoluciones**
- Principal causa: **Error en tienda (84%)**

> Esto sugiere problemas en:
> - preparación de pedidos
> - control de calidad previo al despacho

---

### 🚛 Rendimiento por Vehículo (Patente)

Se identifican diferencias relevantes en desempeño:
- Algunas rutas concentran gran cantidad de **no entregas**
- Otras mantienen operación más eficiente

> 💡 Oportunidad: redistribución de carga y optimización de rutas

---

### 🏪 Análisis por Cliente (Commerce)

- **Falabella concentra prácticamente toda la operación (1,011 viajes)**
- Presenta una tasa de **47.7% de no entrega**

> ⚠️ Alta dependencia operativa de un solo cliente  
> → riesgo estructural en la operación

---

### 🌍 Cobertura Geográfica

- **Región Metropolitana:** 986 viajes  
- **Región de Valparaíso:** 27 viajes  

> Operación altamente centralizada, con baja diversificación territorial

---

## 🧠 Conclusiones

El análisis evidencia que, aunque los indicadores de cumplimiento de tiempo son altos, existen **fallas críticas en etapas previas a la distribución**, especialmente en:

- Procesos de carga en bodega  
- Preparación de pedidos  
- Coordinación logística  

Estas ineficiencias generan:
- Alto porcentaje de no entregas  
- Incremento en devoluciones  
- Impacto directo en costos operacionales  

---

## 🚀 Recomendaciones

- Mejorar controles en procesos de **picking y carga**
- Implementar validaciones previas al despacho
- Optimizar asignación de rutas y vehículos
- Reducir dependencia de un solo cliente
- Monitorear KPIs operacionales en tiempo real

---

## 📌 Tecnologías Utilizadas

- Modelamiento de datos
- SQL / procesamiento de datos
- Power BI (visualización)

<img width="2446" height="103" alt="Screenshot_1" src="https://github.com/user-attachments/assets/9f554d5e-33ef-4541-a8e2-33f90c7f496d" />
<img width="1230" height="1100" alt="Dashboard DUM" src="https://github.com/user-attachments/assets/c2ac7fa6-8294-429b-b7b0-3fa4dfe63570" />
