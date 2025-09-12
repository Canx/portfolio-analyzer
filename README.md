# 📊 portfolio-analyzer: Analizador de Carteras de Fondos de Inversión

Una aplicación web interactiva construida con Streamlit para crear, analizar, comparar y optimizar múltiples carteras de fondos de inversión.

## 🚀 Descripción

Este proyecto es una herramienta avanzada para inversores que desean tomar decisiones informadas sobre sus carteras. La aplicación permite gestionar un catálogo de fondos de inversión, construir múltiples carteras personalizadas, descargar datos históricos y realizar un análisis completo y comparativo.

La interfaz, organizada en varias páginas, permite una gestión fluida de las carteras (crear, copiar, renombrar, borrar), un análisis profundo de la cartera activa y una exploración detallada de todo el catálogo de fondos. Todas las carteras se guardan en el navegador para mantener tu trabajo entre sesiones.

-----

## ✨ Características Principales

La aplicación se estructura en torno a varias páginas y funcionalidades clave:

  * **Gestión Multi-Cartera:**

      * Crea un número ilimitado de carteras.
      * **Copia** una cartera existente para usarla como plantilla.
      * **Renombra** y **borra** carteras fácilmente.
      * Selecciona una **cartera activa** sobre la que realizar el análisis detallado.

  * **Página de Análisis de Cartera:**

      * **Dashboard Visual:** Comienza con una visión global de la composición de la cartera (gráfico de donut) y una tabla con las métricas clave de cada fondo y del total.
      * **Asignación de Pesos Precisa:** Ajusta la composición de la cartera con sliders y botones `+/-` para un control fino. La lista de fondos se ordena automáticamente por peso.
      * **Optimización Avanzada (con Riskfolio-Lib):** Optimiza la cartera activa con un solo clic usando modelos profesionales:
          * **Hierarchical Risk Parity (HRP):** Con múltiples medidas de riesgo seleccionables (Varianza, CVaR, CDaR, etc.).
          * **Mínima Varianza (MV).**
          * **Máximo Ratio de Sharpe (MSR).**
      * **Gráficos Interactivos (con Plotly):**
          * **Evolución Normalizada:** Compara el crecimiento de los fondos y la cartera.
          * **Volatilidad Rolling:** Analiza la evolución del riesgo en el tiempo.
          * **Riesgo vs. Retorno:** Identifica la eficiencia de la cartera frente a sus activos.
          * **Matriz de Correlaciones:** Muestra la diversificación interna de la cartera activa.

  * **Página de Explorador de Fondos:**

      * **Catálogo Centralizado:** Visualiza y gestiona todos los fondos de tu `fondos.json`.
      * **Enriquecimiento Automático de Datos:** Al añadir un nuevo fondo por ISIN, la app busca automáticamente su nombre oficial, TER, gestora, domicilio y SRRI.
      * **Filtros y Ordenación:** Filtra el catálogo por gestora, domicilio o TER máximo, y ordena la tabla por cualquiera de las métricas clave (Rentabilidad, Volatilidad, Sharpe, etc.).
      * **Análisis Rápido:** Incluye un gráfico de Riesgo vs. Retorno para todos los fondos del catálogo.
      * **Selección y Comparación:** Selecciona varios fondos mediante checkboxes y genera al instante un gráfico comparativo de su rendimiento.

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

La aplicación gestiona el fichero `fondos.json` por ti. La primera vez que la ejecutes, puedes añadir fondos directamente desde la interfaz usando su ISIN.

### 4\. Ejecución

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador. La primera vez que se ejecute, se creará una carpeta `fondos_data/` donde se guardarán los datos históricos de los fondos en formato CSV para acelerar las cargas futuras.

-----

## 📂 Estructura del Proyecto

La aplicación ha sido refactorizada para seguir una arquitectura modular y multi-página:

```
analizador-carteras/
├── app.py                      # Página principal de bienvenida
├── pages/
│   ├── 1_📈_Análisis_de_Cartera.py # Lógica y UI para la página de análisis
│   └── 2_🔎_Explorador_de_Fondos.py # Lógica y UI para el explorador del catálogo
│   └── 3_📊_Comparador_de_Carteras.py # Lógica y UI para comparar carteras
├── src/
│   ├── data_manager.py         # Gestiona la descarga de datos y el catálogo fondos.json
│   ├── metrics.py              # Funciones de cálculo de métricas financieras
│   ├── optimizer.py            # Lógica de optimización con Riskfolio-Lib
│   ├── portfolio.py            # Clase que modela una cartera agregada
│   ├── state.py                # Inicialización del estado de la sesión
│   ├── ui_components.py        # Funciones que construyen la interfaz
│   └── utils.py                # Funciones de utilidad compartidas (carga de config, etc.)
├── tests/
│   ├── test_metrics.py         # Tests unitarios para las funciones de métricas
│   └── test_portfolio.py       # Tests unitarios para la clase Portfolio
├── fondos.json                 # Fichero de configuración con el catálogo de fondos
├── fondos_data/                # Caché de datos de precios (CSVs)
├── requirements.txt            # Dependencias de Python
└── README.md                   # Este fichero
```

-----

## 💡 Posibles Mejoras Futuras

  * **Backtesting Histórico:** Añadir una nueva página para simular el rendimiento de una estrategia de cartera a lo largo de periodos históricos más largos.
  * **Comparación con Benchmarks:** Integrar la opción de superponer el rendimiento de un índice de referencia (ej. un ETF del MSCI World) en los gráficos.
  * **Análisis de Costes Avanzado:** Calcular el TER ponderado de la cartera y mostrar su impacto en el rendimiento a largo plazo.
  * **Ampliar Cobertura de Tests:** Añadir tests para el módulo de optimización y otras funciones críticas.
