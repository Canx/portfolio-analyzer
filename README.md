# 📊 Analizador de Carteras de Fondos de Inversión

Una aplicación web interactiva construida con Streamlit para analizar, simular y optimizar carteras de fondos de inversión.


## 🚀 Descripción

Este proyecto es una herramienta para inversores que desean tomar decisiones informadas sobre sus carteras. La aplicación permite cargar una lista de fondos de inversión desde un fichero de configuración, descargar sus datos históricos, y realizar un análisis completo tanto de los fondos individuales como de una cartera ponderada por el usuario.

La interfaz es dinámica y permite ajustar los pesos de la cartera en tiempo real, visualizando al instante el impacto en las métricas de rentabilidad y riesgo. Además, la cartera personalizada puede guardarse en el navegador para futuras sesiones.

---

## ✨ Características Principales

* **Análisis Interactivo de Fondos:** Carga y analiza cualquier lista de fondos de inversión definida en un fichero `fondos.json`.
* **Métricas Clave:** Calcula automáticamente las métricas esenciales para cualquier periodo de tiempo seleccionado:
    * Rentabilidad Anualizada (TAE/CAGR)
    * Volatilidad Anualizada
    * Ratio de Sharpe
    * Caída Máxima (Max Drawdown)
* **Visualizaciones Dinámicas:** Ofrece múltiples gráficos interactivos para entender el comportamiento de los activos:
    * **Evolución Normalizada:** Compara el crecimiento de los fondos desde un punto de partida común.
    * **Volatilidad Rolling:** Muestra la evolución del riesgo de los activos en el tiempo.
    * **Riesgo vs. Retorno:** Un gráfico de dispersión para identificar qué fondos ofrecen un mejor retorno para su nivel de riesgo.
    * **Matriz de Correlaciones:** Visualiza cómo se mueven los activos entre sí, clave para la diversificación.
* **Simulación de Cartera:**
    * **Asignación de Pesos:** Sliders interactivos para definir la composición de "Mi Cartera".
    * **Ajuste Automático:** Los sliders se reajustan automáticamente para que la suma siempre sea 100%.
    * **Análisis Agregado:** La cartera simulada se muestra como un activo más en todas las tablas y gráficos para una comparación directa.
* **Persistencia de Datos:** Permite **guardar y cargar** la configuración de la cartera (fondos y pesos) en el almacenamiento local del navegador, manteniendo tu análisis entre sesiones.

---

## 🛠️ Instalación y Uso

Sigue estos pasos para poner en marcha la aplicación en tu entorno local.

### 1. Prerrequisitos
* Python 3.9+

### 2. Instalación

**a. Clona el repositorio:**
```bash
git clone [https://github.com/Canx/portfolio-analyzer.git](https://github.com/Canx/portfolio-analyzer.git)
cd portfolio-analyzer
````

**b. Crea un entorno virtual (recomendado):**

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

**c. Instala las dependencias:**

```bash
pip install -r requirements.txt
```

### 3\. Configuración

Antes de ejecutar la aplicación, debes crear el fichero `fondos.json` en la raíz del proyecto. Este fichero contiene la lista de fondos que quieres analizar.

**Ejemplo de `fondos.json`:**

```json
{
  "fondos": [
    {
      "nombre": "Avantage Fund B FI",
      "isin": "ES0112231016"
    },
    {
      "nombre": "Fidelity MSCI World Index",
      "isin": "IE00BYX5P602"
    },
    {
      "nombre": "Horos Value Internacional",
      "isin": "ES0146309002"
    }
  ]
}
```

### 4\. Ejecución

Una vez configurado, ejecuta la aplicación con el siguiente comando:

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador. La primera vez que se ejecute, se creará una carpeta `fondos_data/` donde se guardarán los datos históricos de los fondos en formato CSV para acelerar las cargas futuras.

-----

## 📂 Estructura del Proyecto

```
analizador-carteras/
├── app.py                  # Fichero principal de la aplicación Streamlit
├── portfolio_analyzer.py   # Módulo con la lógica de análisis y descarga de datos
├── fondos.json             # Fichero de configuración con la lista de fondos
├── fondos_data/            # Carpeta donde se cachean los datos CSV de los fondos
├── requirements.txt        # Lista de dependencias de Python
└── README.md               # Este fichero
```

-----

## 💡 Posibles Mejoras Futuras

  * **Optimización de Cartera:** Integrar la **Frontera Eficiente** (usando librerías como PyPortfolioOpt) para encontrar la cartera con el máximo Ratio de Sharpe o la mínima volatilidad.
  * **Comparación con Benchmarks:** Añadir la opción de superponer el rendimiento de un índice de referencia (ej. un ETF del MSCI World) en los gráficos.
  * **Análisis de Costes:** Incluir el TER (Total Expense Ratio) de cada fondo en `fondos.json` para calcular el coste ponderado de la cartera.
  * **Tests Unitarios:** Añadir pruebas para asegurar la fiabilidad de las funciones de cálculo.
