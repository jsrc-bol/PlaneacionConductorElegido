# Simulador de Planeación Operativa — Conductor Elegido

Herramienta de planeación para estimar demanda de servicios de conductor elegido y optimizar la asignación de turnos durante el período del Mundial FIFA 2026.

## Descripción

El sistema consta de dos módulos principales:

1. **Pronóstico y Calibración** — Estima la demanda futura de servicios usando datos históricos, aplicando percentiles sobre semanas homólogas. Permite calibrar el modelo en tiempo real y aplicar factores de impacto por partidos del Mundial.

2. **Estimación de Técnicos** — Toma la proyección calibrada y resuelve un problema de optimización lineal entera (ILP) para determinar cuántos conductores citar por turno, minimizando costos y penalizaciones por servicio incumplido.

## Arquitectura de Archivos

```
front-planeacion/
├── app.py                      # Entry point — navegación entre páginas
├── pages/
│   ├── pronostico.py           # Página 1: Pronóstico, calibración y factores
│   └── tecnicos.py             # Página 2: Optimización ILP de turnos
├── DIM.csv                     # Datos históricos de servicios (input del modelo)
├── partidos_colombia.json      # Persistencia de tabla de partidos Colombia (auto-generado)
├── partidos_otros.json         # Persistencia de tabla de otros partidos (auto-generado)
├── requirements.txt            # Dependencias Python
├── CHANGELOG.md                # Registro de cambios
├── .gitignore                  # Exclusiones de Git
└── README.md                   # Este archivo
```

## Página 1: Pronóstico y Calibración (`pages/pronostico.py`)

### Funcionalidades

- **Serie temporal completa**: Visualiza demanda real (Ene 2025 – Jun 2026) y proyección estimada (Jun – Jul 2026) con 3 líneas: real, estimación base, estimación + partidos.
- **Parámetros de calibración**:
  - Percentil (10–99): controla qué tan conservador es el modelo.
  - Semanas homólogas (2–8): cuántas semanas del mismo día de semana se usan como referencia.
  - Departamento: filtro por región.
- **Tablas editables de partidos**: Negocio puede modificar fecha, hora, horario de impacto y factor de cada partido. Puede agregar o eliminar partidos.
- **Persistencia**: Botón "Guardar" que almacena las tablas en archivos JSON para no perder configuraciones entre sesiones.
- **Métricas de backtesting**: MAE, MAPE y Cobertura evaluados sobre el período observado.
- **Impacto de partidos**: Gráfico de barras agrupadas mostrando estimación base vs estimación con factores por día.
- **Comparativa por horas**: Dos gráficos lado a lado para comparar un día real (observado) contra un día estimado (proyectado).
- **Guardar Modelo**: Congela la proyección y la pasa a la página de técnicos.

### Modelo de Estimación

El modelo usa un enfoque de **percentiles sobre semanas homólogas**:

1. Para cada fecha a estimar, busca las últimas N semanas del mismo día de semana en el histórico.
2. Calcula el percentil configurado hora por hora sobre esas semanas.
3. Aplica factores multiplicativos por partidos del Mundial en las ventanas horarias definidas.

## Página 2: Estimación de Técnicos (`pages/tecnicos.py`)

### Funcionalidades

- **Tipos de turno configurables**: Multiselect con duraciones de 3 a 9 horas. Negocio elige qué combinaciones probar.
- **Costo por tipo de turno**: Cada duración tiene su costo relativo en la función objetivo.
- **Productividad**: Viajes/hora que atiende cada conductor.
- **Penalización por incumplimiento**: Controla qué tan agresivo es el modelo al abrir turnos.
- **Resultados**:
  - KPIs dinámicos (conductores totales, bloques por duración).
  - Matriz de distribución con 3 vistas: técnicos, servicios, o combinada.
  - Descarga en CSV.

### Motor de Optimización (ILP)

Resuelve el siguiente problema de programación lineal entera:

```
Minimizar: Σ(costo_d × turnos_d) + penalización × Σ(demanda_incumplida)

Sujeto a:
  productividad × conductores_activos(t) + slack(t) ≥ demanda(t)  ∀t
  turnos_d ∈ Z+ (enteros no negativos)
```

Donde:
- `d` = cada tipo de turno habilitado (por duración)
- `t` = cada slot horario nocturno (18:00 – 06:00)
- Solo se crean turnos en horario nocturno

## Requisitos

- Python 3.12+
- Dependencias en `requirements.txt`

## Instalación y Ejecución

```bash
# Crear entorno virtual
python -m venv .venv

# Activar (Windows)
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
streamlit run app.py
```

La app se abre en `http://localhost:8501`.

## Flujo de Uso

1. Abrir la app → Página "Pronóstico y Calibración"
2. Ajustar percentil y semanas homólogas hasta que las métricas de backtesting sean aceptables
3. Configurar partidos del Mundial (fechas, horarios, factores)
4. Guardar tablas de partidos (persistencia)
5. Hacer clic en "Guardar Modelo y Continuar"
6. Ir a la página "Estimación de Técnicos"
7. Configurar tipos de turno, costos y productividad
8. Correr la optimización
9. Revisar la malla resultante y descargar CSV

## Datos de Entrada

El archivo `DIM.csv` debe tener la siguiente estructura:

| Columna | Descripción |
|---------|-------------|
| `# AUTORIZACION` | Número de autorización del servicio |
| `FECHA PROGRAMACIÓN DE SERVICIO` | Fecha en formato `YYYY-MM-DD` |
| `HORA PROGRAMACIÓN SERVICIO` | Hora en formato `HH:MM:SS` |
| `DEPARTAMENTO` | Departamento (región) del servicio |

## Autores

Equipo de Planeación Operativa — Conductor Elegido
