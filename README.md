# 📊 portfolio-analizer: Analizador de Carteras de Fondos de Inversión

Una aplicación web interactiva construida con Streamlit para analizar, simular y optimizar carteras de fondos de inversión.

## 🚀 Descripción

Este proyecto es una herramienta para inversores que desean tomar decisiones informadas sobre sus carteras. La aplicación permite construir una cartera personalizada a partir de un catálogo de fondos, descargar sus datos históricos y realizar un análisis completo de la cartera ponderada y de los fondos individuales que la componen.

La interfaz es dinámica y permite ajustar los pesos de la cartera en tiempo real, visualizando al instante el impacto en las métricas de rentabilidad y riesgo. Además, la configuración de la cartera se guarda automáticamente en el navegador para futuras sesiones.

-----

## ✨ Características Principales

  * **Gestión de Cartera como Eje Central:** El análisis se centra exclusivamente en "Mi Cartera". Los fondos que añades y ponderas son los que se visualizan en todos los gráficos y métricas.
  * **Optimización de Cartera (HRP):** Incluye una optimización con un clic basada en **Hierarchical Risk Parity (HRP)** para proponer una asignación de pesos que diversifica el riesgo de forma robusta.
  * **Métricas Clave:** Calcula automáticamente las métricas esenciales para cualquier periodo de tiempo seleccionado:
      * Rentabilidad Anualizada
      * Volatilidad Anualizada
      * Ratio de Sharpe
      * Caída Máxima (Max Drawdown)
  * **Visualizaciones Dinámicas:** Ofrece múltiples gráficos para entender el comportamiento de la cartera y sus activos:
      * **Evolución Normalizada:** Compara el crecimiento de los fondos y la cartera global.
      * **Volatilidad Rolling:** Muestra la evolución del riesgo en el tiempo.
      * **Riesgo vs. Retorno:** Un gráfico de dispersión para ver la eficiencia de la cartera frente a sus componentes.
      * **Matriz de Correlaciones:** Visualiza cómo se mueven los activos de la cartera entre sí, clave para la diversificación.
  * **Simulación Interactiva:**
      * **Asignación de Pesos:** Sliders para definir la composición de la cartera.
      * **Ajuste Automático:** Los sliders se reajustan para que la suma siempre sea 100%.
      * **Análisis Agregado:** La cartera simulada se muestra como un activo más para una comparación directa.
  * **Persistencia de Datos:** **Guarda y carga automáticamente** la configuración de la cartera (fondos y pesos) en el almacenamiento local del navegador, manteniendo tu análisis entre sesiones.

-----

## 🛠️ Instalación y Uso

Sigue estos pasos para poner en marcha la aplicación en tu entorno local.

### 1\. Prerrequisitos

  * Python 3.9+

### 2\. Instalación

**a. Clona el repositorio:**

```bash
git clone https://github.com/Canx/portfolio-analyzer.git
cd portfolio-analyzer
```

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

Antes de ejecutar la aplicación, debes crear el fichero `fondos.json` en la raíz del proyecto. Este fichero contiene el catálogo de fondos disponibles para añadir a tu cartera.

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

También puedes añadir nuevos fondos al catálogo directamente desde la interfaz de la aplicación.

### 4\. Ejecución

Una vez configurado, ejecuta la aplicación con el siguiente comando:

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador. La primera vez que se ejecute, se creará una carpeta `fondos_data/` donde se guardarán los datos históricos de los fondos en formato CSV para acelerar las cargas futuras.

-----

## 📂 Estructura del Proyecto

La aplicación ha sido refactorizada para seguir una arquitectura modular que separa la lógica de la interfaz.

```
analizador-carteras/
├── app.py                  # Orquestador principal de la aplicación Streamlit.
├── fondos.json             # Fichero de configuración con el catálogo de fondos.
├── requirements.txt        # Lista de dependencias de Python.
├── fondos_data/            # Carpeta donde se cachean los datos CSV de los fondos.
└── src/
    ├── data_manager.py     # Módulo para descargar y gestionar los datos de los fondos.
    ├── metrics.py          # Módulo con las funciones de cálculo de métricas financieras.
    ├── optimizer.py        # Módulo con los algoritmos de optimización de carteras (HRP).
    ├── portfolio.py        # Clase que modela y calcula la cartera agregada.
    └── ui_components.py    # Módulo que construye la interfaz de usuario con Streamlit.
```

-----

## 💡 Posibles Mejoras Futuras

  * **Optimización Avanzada:** Añadir otros modelos de optimización como la **Frontera Eficiente** (Mean-Variance Optimization) para comparar con HRP.
  * **Comparación con Benchmarks:** Añadir la opción de superponer el rendimiento de un índice de referencia (ej. un ETF del MSCI World) en los gráficos.
  * **Análisis de Costes:** Incluir el TER (Total Expense Ratio) de cada fondo en `fondos.json` para calcular el coste ponderado de la cartera.
  * **Tests Unitarios:** Añadir pruebas para asegurar la fiabilidad de las funciones de cálculo en el directorio `src`.