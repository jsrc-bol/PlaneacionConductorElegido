import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json
from pathlib import Path

# Archivos de persistencia
ARCHIVO_PARTIDOS_COLOMBIA = Path("partidos_colombia.json")
ARCHIVO_PARTIDOS_OTROS = Path("partidos_otros.json")

st.title("📊 Pronóstico y Calibración del Modelo")
st.markdown(
    "Calibra el modelo de demanda ajustando percentil y semanas homólogas. "
    "Visualiza Real (Ene–May 2026) vs Estimación (Jun–Jul 2026). "
    "Cuando estés conforme, guarda el modelo para pasar a la estimación de técnicos."
)

# =====================================================================
# GUÍA
# =====================================================================
with st.expander("ℹ️ Guía: Parámetros y cómo funciona", expanded=False):
    st.markdown("""
### 🎚️ Parámetros de calibración

| Parámetro | Qué controla | Efecto al subirlo |
|-----------|-------------|-------------------|
| **Percentil** | Qué tan conservador es el modelo. P50 = mediana, P90 = caso pesimista. | Sube la estimación → más conductores citados → menor riesgo de quedar cortos, mayor riesgo de inactividad. |
| **Semanas homólogas** | Cuántas semanas anteriores del mismo día se usan como referencia. | Más semanas = modelo más estable pero menos reactivo. Menos semanas = más reactivo pero más volátil. |

### ⚽ Tablas de Partidos

Las tablas de abajo son **editables**. Puedes:
- **Modificar** fecha, hora de pitazo, horario de impacto y factor de cualquier partido
- **Agregar filas** en "Otros Partidos del Mundial" para incluir más eventos
- **Eliminar filas** desmarcando la fila y borrándola

**Factor (Impacto):** Multiplicador sobre la demanda base en el horario impactado.
- 1.0 = sin efecto
- 1.5 = +50% de demanda
- 2.0 = el doble
- 2.8 = casi el triple

**Horario Impactado:** Ventana de horas donde se aplica el factor (formato "HH:00 – HH:00").
El modelo afecta todas las horas dentro de esa ventana en el día del partido.
""")

# =====================================================================
# CARGA DE DATOS
# =====================================================================
ARCHIVO_HISTORICO = "DIM.csv"

FECHA_OBS_INI = pd.Timestamp("2025-01-01")
FECHA_OBS_FIN = pd.Timestamp("2026-06-28")
FECHA_EST_INI = pd.Timestamp("2026-06-29")
FECHA_EST_FIN = pd.Timestamp("2026-07-20")


@st.cache_data
def cargar_historico() -> pd.DataFrame:
    """Carga y limpia el CSV histórico de servicios (DIM.csv)."""
    df = pd.read_csv(ARCHIVO_HISTORICO, index_col=0, low_memory=False)

    df["fecha"] = pd.to_datetime(df["FECHA PROGRAMACIÓN DE SERVICIO"], errors="coerce")
    df["hora"] = pd.to_numeric(
        df["HORA PROGRAMACIÓN SERVICIO"]
        .astype(str)
        .str.strip()
        .str.extract(r"(\d{1,2}):\d{2}")[0],
        errors="coerce",
    )
    df = df[df["fecha"].notna() & df["hora"].between(0, 23)].copy()
    df["hora"] = df["hora"].astype(int)

    # Filtrar al período observado
    df = df[(df["fecha"] >= FECHA_OBS_INI) & (df["fecha"] <= FECHA_OBS_FIN)].copy()

    return df[["DEPARTAMENTO", "fecha", "hora", "# AUTORIZACION"]].copy()


try:
    df_hist = cargar_historico()
except FileNotFoundError:
    st.error(f"⚠️ No se encontró '{ARCHIVO_HISTORICO}'. Colócalo en la carpeta del proyecto.")
    st.stop()
except Exception as exc:
    st.error(f"❌ Error cargando datos: {exc}")
    st.stop()

# =====================================================================
# SIDEBAR — PARÁMETROS DE CALIBRACIÓN
# =====================================================================
st.sidebar.header("🎚️ Parámetros del Modelo")

percentil = st.sidebar.slider(
    "Percentil para la estimación", min_value=10, max_value=99, value=70, step=5,
    help="Percentil sobre semanas homólogas anteriores.",
)
semanas_historicas = st.sidebar.slider(
    "Semanas homólogas", min_value=2, max_value=8, value=4, step=1,
    help="Cantidad de semanas del mismo día de semana como referencia.",
)
departamento_sel = st.sidebar.selectbox(
    "Departamento",
    options=sorted(df_hist["DEPARTAMENTO"].unique().tolist()),
)

st.sidebar.markdown("---")
st.sidebar.markdown("**🚌 Ruta Bolívar**")
pct_bolivar = st.sidebar.slider(
    "% de Operación Ruta Bolívar",
    min_value=0, max_value=100, value=100, step=5,
    help=(
        "Porcentaje de la demanda estimada que atenderá Ruta Bolívar. "
        "Ej: 50% → todas las estimaciones se reducen a la mitad."
    ),
)

# =====================================================================
# TABLAS EDITABLES DE PARTIDOS
# =====================================================================
st.markdown("---")
st.subheader("🇨🇴 Partidos de Selección Colombia")
st.caption("Edita fecha, horarios e impacto. Los partidos tentativos pueden cambiar.")

# Defaults para Colombia — carga desde archivo si existe
if "partidos_colombia" not in st.session_state:
    if ARCHIVO_PARTIDOS_COLOMBIA.exists():
        st.session_state["partidos_colombia"] = pd.DataFrame(
            json.loads(ARCHIVO_PARTIDOS_COLOMBIA.read_text(encoding="utf-8"))
        )
    else:
        st.session_state["partidos_colombia"] = pd.DataFrame([
            {"Fecha": "2026-06-17", "Partido": "Colombia vs Uzbekistán", "Pitazo": 21, "Hora Inicio Impacto": 22, "Hora Fin Impacto": 2, "Factor": 2.8, "Estado": "Confirmado"},
            {"Fecha": "2026-06-23", "Partido": "Colombia vs Congo", "Pitazo": 21, "Hora Inicio Impacto": 22, "Hora Fin Impacto": 2, "Factor": 2.8, "Estado": "Confirmado"},
            {"Fecha": "2026-06-27", "Partido": "Colombia vs Portugal", "Pitazo": 18, "Hora Inicio Impacto": 20, "Hora Fin Impacto": 3, "Factor": 2.8, "Estado": "Confirmado"},
            {"Fecha": "2026-07-03", "Partido": "Colombia Octavos de Final", "Pitazo": 20, "Hora Inicio Impacto": 22, "Hora Fin Impacto": 2, "Factor": 2.8, "Estado": "Tentativo"},
            {"Fecha": "2026-07-10", "Partido": "Colombia Cuartos de Final", "Pitazo": 20, "Hora Inicio Impacto": 22, "Hora Fin Impacto": 2, "Factor": 2.8, "Estado": "Tentativo"},
            {"Fecha": "2026-07-14", "Partido": "Colombia Semifinal", "Pitazo": 20, "Hora Inicio Impacto": 22, "Hora Fin Impacto": 2, "Factor": 2.8, "Estado": "Tentativo"},
            {"Fecha": "2026-07-19", "Partido": "Colombia FINAL", "Pitazo": 17, "Hora Inicio Impacto": 19, "Hora Fin Impacto": 2, "Factor": 2.8, "Estado": "Tentativo"},
        ])

df_col_edit = st.data_editor(
    st.session_state["partidos_colombia"],
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Fecha": st.column_config.TextColumn("Fecha", help="Formato: YYYY-MM-DD"),
        "Partido": st.column_config.TextColumn("Partido"),
        "Pitazo": st.column_config.NumberColumn("Pitazo (Hora)", min_value=0, max_value=23, step=1),
        "Hora Inicio Impacto": st.column_config.NumberColumn("Hora Inicio Impacto", min_value=0, max_value=23, step=1),
        "Hora Fin Impacto": st.column_config.NumberColumn("Hora Fin Impacto", min_value=0, max_value=23, step=1),
        "Factor": st.column_config.NumberColumn("Factor (Impacto)", min_value=1.0, max_value=5.0, step=0.1, format="%.1f"),
        "Estado": st.column_config.SelectboxColumn("Estado", options=["Confirmado", "Tentativo"]),
    },
    key="editor_colombia",
)
st.session_state["partidos_colombia"] = df_col_edit

if st.button("💾 Guardar Partidos Colombia", key="btn_save_col"):
    ARCHIVO_PARTIDOS_COLOMBIA.write_text(
        df_col_edit.to_json(orient="records", force_ascii=False), encoding="utf-8"
    )
    st.success("✅ Partidos de Colombia guardados.")

st.markdown("---")
st.subheader("🌍 Otros Partidos del Mundial")
st.caption("Edita o agrega partidos que impactan la demanda. Puedes agregar filas con '+'.")

# Defaults para otros partidos — carga desde archivo si existe
if "partidos_otros" not in st.session_state:
    if ARCHIVO_PARTIDOS_OTROS.exists():
        st.session_state["partidos_otros"] = pd.DataFrame(
            json.loads(ARCHIVO_PARTIDOS_OTROS.read_text(encoding="utf-8"))
        )
    else:
        st.session_state["partidos_otros"] = pd.DataFrame([
            {"Fecha": "2026-06-11", "Partido": "México vs Sudáfrica (inauguración)", "Pitazo": 14, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 1.2},
            {"Fecha": "2026-06-12", "Partido": "Argentina vs Argelia · Brasil", "Pitazo": 20, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 1.5},
            {"Fecha": "2026-06-13", "Partido": "EE.UU. vs Australia · partidos noche", "Pitazo": 14, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 1.5},
            {"Fecha": "2026-06-19", "Partido": "Argentina · Brasil 2da fecha", "Pitazo": 20, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 1.5},
            {"Fecha": "2026-06-20", "Partido": "Múltiples grupos fase 2", "Pitazo": 19, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 2.0},
            {"Fecha": "2026-06-25", "Partido": "Ecuador vs Alemania · Argentina", "Pitazo": 19, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 1.5},
            {"Fecha": "2026-06-26", "Partido": "Brasil 3ra fase de grupos", "Pitazo": 20, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 1.5},
            {"Fecha": "2026-06-29", "Partido": "Inicio Octavos de Final", "Pitazo": 19, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 2.0},
            {"Fecha": "2026-06-30", "Partido": "Octavos de Final", "Pitazo": 19, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 2.0},
            {"Fecha": "2026-07-04", "Partido": "Octavos de Final (últimos)", "Pitazo": 19, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 2.0},
            {"Fecha": "2026-07-11", "Partido": "Cuartos de Final", "Pitazo": 20, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 2.0},
            {"Fecha": "2026-07-15", "Partido": "Semifinales (2da)", "Pitazo": 20, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 2.0},
            {"Fecha": "2026-07-18", "Partido": "Tercer puesto", "Pitazo": 17, "Hora Inicio Impacto": 21, "Hora Fin Impacto": 1, "Factor": 1.5},
        ])

df_otros_edit = st.data_editor(
    st.session_state["partidos_otros"],
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Fecha": st.column_config.TextColumn("Fecha", help="Formato: YYYY-MM-DD"),
        "Partido": st.column_config.TextColumn("Partido"),
        "Pitazo": st.column_config.NumberColumn("Pitazo (Hora)", min_value=0, max_value=23, step=1),
        "Hora Inicio Impacto": st.column_config.NumberColumn("Hora Inicio Impacto", min_value=0, max_value=23, step=1),
        "Hora Fin Impacto": st.column_config.NumberColumn("Hora Fin Impacto", min_value=0, max_value=23, step=1),
        "Factor": st.column_config.NumberColumn("Factor (Impacto)", min_value=1.0, max_value=5.0, step=0.1, format="%.1f"),
    },
    key="editor_otros",
)
st.session_state["partidos_otros"] = df_otros_edit

if st.button("💾 Guardar Otros Partidos", key="btn_save_otros"):
    ARCHIVO_PARTIDOS_OTROS.write_text(
        df_otros_edit.to_json(orient="records", force_ascii=False), encoding="utf-8"
    )
    st.success("✅ Otros partidos guardados.")

# =====================================================================
# FUNCIONES DE CÁLCULO
# =====================================================================


def generar_ventanas_horarias(ini: int, fin: int) -> list:
    """Genera lista de (offset_día, hora) desde ini hasta fin."""
    out, h, off = [], ini, 0
    while True:
        out.append((off, h))
        if h == fin:
            break
        h = (h + 1) % 24
        if h == 0:
            off += 1
    return out


def mapear_celdas_afectadas(fecha: str, vent: list) -> set:
    """Mapea celdas (date, hora) afectadas por una ventana."""
    base = pd.Timestamp(fecha)
    return {((base + pd.Timedelta(days=o)).date(), h) for o, h in vent}


@st.cache_data
def construir_matriz_historica(df: pd.DataFrame, departamento: str) -> pd.DataFrame:
    """Construye matriz hora×día del período observado."""
    sub = df[
        (df["DEPARTAMENTO"] == departamento)
        & (df["fecha"] >= FECHA_OBS_INI)
        & (df["fecha"] <= FECHA_OBS_FIN)
    ]
    demanda_hora = (
        sub.groupby(["fecha", "hora"])["# AUTORIZACION"]
        .count()
        .rename("demanda")
        .reset_index()
    )
    mat = (
        demanda_hora.pivot_table(index="fecha", columns="hora", values="demanda", aggfunc="sum", fill_value=0)
        .reindex(columns=range(24), fill_value=0)
        .sort_index()
    )
    idx_completo = pd.date_range(FECHA_OBS_INI, FECHA_OBS_FIN, freq="D")
    return mat.reindex(idx_completo, fill_value=0)


def estimar_hora_para_fecha(mat: pd.DataFrame, fecha: pd.Timestamp, percentil_val: int, n_semanas: int) -> pd.Series:
    """Estima demanda por hora para una fecha usando semanas homólogas."""
    dow = fecha.weekday()
    candidatas = sorted(f for f in mat.index if f.weekday() == dow and f < fecha)[-n_semanas:]
    if not candidatas:
        candidatas = sorted(f for f in mat.index if f.weekday() == dow)[-n_semanas:]
    if not candidatas:
        return pd.Series(0.0, index=range(24))
    return mat.loc[candidatas].apply(lambda col: np.ceil(np.percentile(col, percentil_val)))


def calcular_proyeccion_desde_tablas(
    mat: pd.DataFrame, percentil_val: int, n_semanas: int,
    df_colombia: pd.DataFrame, df_otros: pd.DataFrame
) -> pd.DataFrame:
    """Genera proyección usando las tablas editables de partidos."""
    fechas_est = pd.date_range(FECHA_EST_INI, FECHA_EST_FIN, freq="D")
    filas = []
    for fecha in fechas_est:
        est_hora = estimar_hora_para_fecha(mat, fecha, percentil_val, n_semanas)
        for h in range(24):
            filas.append({"fecha": fecha, "hora": h, "estimacion_base": est_hora[h]})

    df_proy = pd.DataFrame(filas)
    df_proy["fecha_dt"] = pd.to_datetime(df_proy["fecha"])
    df_proy["_key"] = list(zip(df_proy.fecha_dt.dt.date, df_proy.hora))

    # Factores desde tablas
    factor_col = np.ones(len(df_proy))
    factor_otros = np.ones(len(df_proy))

    # Aplicar otros partidos
    for _, row in df_otros.iterrows():
        try:
            fecha_str = str(row["Fecha"]).strip()
            h_ini = int(row["Hora Inicio Impacto"])
            h_fin = int(row["Hora Fin Impacto"])
            factor_val = float(row["Factor"])
            celdas = mapear_celdas_afectadas(fecha_str, generar_ventanas_horarias(h_ini, h_fin))
            m = df_proy._key.isin(celdas).values
            factor_otros[m] = np.maximum(factor_otros[m], factor_val)
        except (ValueError, TypeError):
            continue

    # Aplicar partidos de Colombia (prioridad)
    for _, row in df_colombia.iterrows():
        try:
            fecha_str = str(row["Fecha"]).strip()
            h_ini = int(row["Hora Inicio Impacto"])
            h_fin = int(row["Hora Fin Impacto"])
            factor_val = float(row["Factor"])
            celdas = mapear_celdas_afectadas(fecha_str, generar_ventanas_horarias(h_ini, h_fin))
            m = df_proy._key.isin(celdas).values
            factor_col[m] = np.maximum(factor_col[m], factor_val)
        except (ValueError, TypeError):
            continue

    # Colombia tiene prioridad
    df_proy["factor"] = np.where(factor_col > 1, factor_col, factor_otros)
    df_proy["estimacion_con_mundial"] = (df_proy["estimacion_base"] * df_proy["factor"]).round(1)

    return df_proy[["fecha", "hora", "estimacion_base", "factor", "estimacion_con_mundial"]].copy()

def aplicar_piso_minimo(df_proy: pd.DataFrame, piso: float = 1.0) -> pd.DataFrame:
    """Garantiza un mínimo de `piso` por celda (Depto, Fecha, Hora),
    SOLO en horario nocturno 6 PM → 6 AM (18:00–23:00 y 00:00–06:00),
    que es donde se concentra la operación de Conductor Elegido.
    Fuera de ese rango (07:00–17:00) la estimación se deja intacta.
    """
    df_proy = df_proy.copy()
    # Nocturno: 6 PM en adelante (hora >= 18) o hasta las 6 AM (hora <= 6)
    mask_noche = (df_proy["hora"] >= 18) | (df_proy["hora"] <= 6)
    df_proy.loc[mask_noche, "estimacion_base"] = (
        df_proy.loc[mask_noche, "estimacion_base"].clip(lower=piso)
    )
    df_proy.loc[mask_noche, "estimacion_con_mundial"] = (
        df_proy.loc[mask_noche, "estimacion_con_mundial"].clip(lower=piso)
    )
    return df_proy

# =====================================================================
# CÁLCULOS PRINCIPALES
# =====================================================================
mat_hist = construir_matriz_historica(df_hist, departamento_sel)

df_proyeccion = calcular_proyeccion_desde_tablas(
    mat_hist, percentil, semanas_historicas, df_col_edit, df_otros_edit
)

# Aplicar % de operación Ruta Bolívar
factor_bolivar = pct_bolivar / 100.0
df_proyeccion["estimacion_base"] = (df_proyeccion["estimacion_base"] * factor_bolivar).round(1)
df_proyeccion["estimacion_con_mundial"] = (df_proyeccion["estimacion_con_mundial"] * factor_bolivar).round(1)

df_proyeccion = aplicar_piso_minimo(df_proyeccion, piso=1)

# Demanda real diaria (observada)
df_real_diario = (
    df_hist[
        (df_hist["DEPARTAMENTO"] == departamento_sel)
        & (df_hist["fecha"] >= FECHA_OBS_INI)
        & (df_hist["fecha"] <= FECHA_OBS_FIN)
    ]
    .groupby("fecha")["# AUTORIZACION"].count()
    .rename("demanda_real")
    .reset_index()
)

# Estimación diaria agregada
df_est_diario_base = df_proyeccion.groupby("fecha")["estimacion_base"].sum().reset_index()
df_est_diario_mundial = df_proyeccion.groupby("fecha")["estimacion_con_mundial"].sum().reset_index()

# =====================================================================
# GRÁFICO 1: SERIE TEMPORAL COMPLETA
# =====================================================================
st.markdown("---")
st.subheader(f"📈 Serie Temporal Completa — {departamento_sel}")
st.caption(f"P{percentil} | {semanas_historicas} semanas homólogas")

mostrar_mundial = st.toggle(
    "Mostrar Estimación + Mundial en el gráfico",
    value=True,
    help="Activa o desactiva la línea de estimación con factores de partidos del Mundial.",
)

todas_fechas = pd.date_range(FECHA_OBS_INI, FECHA_EST_FIN, freq="D")
df_grafico = pd.DataFrame({"fecha": todas_fechas})
df_grafico = df_grafico.merge(df_real_diario, on="fecha", how="left")
df_grafico = df_grafico.merge(df_est_diario_base.rename(columns={"estimacion_base": "est_base"}), on="fecha", how="left")
df_grafico = df_grafico.merge(df_est_diario_mundial.rename(columns={"estimacion_con_mundial": "est_mundial"}), on="fecha", how="left")

# Construir formato largo para Altair
series_long = []
for _, row in df_grafico.iterrows():
    if pd.notna(row["demanda_real"]):
        series_long.append({"fecha": row["fecha"], "valor": row["demanda_real"], "serie": "Demanda Real"})
    if pd.notna(row["est_base"]):
        series_long.append({"fecha": row["fecha"], "valor": row["est_base"], "serie": f"Estimación Base (P{percentil})"})
    if mostrar_mundial and pd.notna(row["est_mundial"]):
        series_long.append({"fecha": row["fecha"], "valor": row["est_mundial"], "serie": "Estimación + Mundial"})

df_long = pd.DataFrame(series_long)

color_scale = alt.Scale(
    domain=["Demanda Real", f"Estimación Base (P{percentil})", "Estimación + Mundial"],
    range=["#4C78A8", "#F58518", "#54A24B"],
)

_base = alt.Chart(df_long).encode(
    x=alt.X(
        "fecha:T",
        title="Fecha",
        scale=alt.Scale(domain=["2026-01-01", "2026-07-31"]),
        axis=alt.Axis(format="%b %Y", tickCount="month", labelAngle=-45),
    ),
    y=alt.Y("valor:Q", title="Servicios diarios"),
    color=alt.Color("serie:N", title="", scale=color_scale),
)

_linea = _base.mark_line(strokeWidth=1.5)

_puntos = _base.mark_circle(size=0, opacity=0).encode(
    tooltip=[
        alt.Tooltip("fecha:T", title="Fecha", format="%d %b %Y"),
        alt.Tooltip("serie:N", title="Serie"),
        alt.Tooltip("valor:Q", title="Servicios", format=".0f"),
    ]
).add_params(alt.selection_point(nearest=True, on="mouseover", fields=["fecha"], empty=False))

chart_serie = (_linea + _puntos).properties(height=400).interactive(bind_y=False)

st.altair_chart(chart_serie, use_container_width=True)

leyenda = (
    "🔵 **Demanda Real**: datos observados | "
    f"🟠 **Estimación Base (P{percentil})**: proyección sin factores"
)
if mostrar_mundial:
    leyenda += " | 🟢 **Estimación + Mundial**: proyección con factores de impacto aplicados"
st.caption(leyenda)


# =====================================================================
# GRÁFICO 2: IMPACTO DE LOS FACTORES
# =====================================================================
st.markdown("---")
st.subheader("⚽ Impacto de los Partidos sobre la Estimación")
st.caption("Diferencia diaria entre la estimación con factores vs la estimación base.")

df_impacto = df_proyeccion.groupby("fecha").agg(
    base=("estimacion_base", "sum"),
    con_mundial=("estimacion_con_mundial", "sum"),
).reset_index()
df_impacto["diferencia"] = df_impacto["con_mundial"] - df_impacto["base"]
df_impacto["incremento_pct"] = ((df_impacto["diferencia"] / df_impacto["base"].replace(0, np.nan)) * 100).round(1)

chart_impacto = df_impacto[["fecha", "base", "con_mundial"]].copy()
chart_impacto.columns = ["Fecha", "Estimación Base", "Estimación + Partidos"]
chart_impacto_long = chart_impacto.melt(id_vars="Fecha", var_name="Tipo", value_name="Servicios")

chart_alt_impacto = (
    alt.Chart(chart_impacto_long)
    .mark_bar()
    .encode(
        x=alt.X("Fecha:T", title="Fecha"),
        y=alt.Y("Servicios:Q", title="Servicios estimados"),
        color=alt.Color("Tipo:N", title=""),
        xOffset="Tipo:N",
    )
    .properties(height=400)
)
st.altair_chart(chart_alt_impacto, use_container_width=True)

dias_con_impacto = df_impacto[df_impacto["diferencia"] > 0][["fecha", "base", "con_mundial", "diferencia", "incremento_pct"]].copy()
dias_con_impacto.columns = ["Fecha", "Est. Base", "Est. + Partidos", "Δ Servicios", "Δ %"]
dias_con_impacto["Fecha"] = dias_con_impacto["Fecha"].dt.strftime("%Y-%m-%d")
if not dias_con_impacto.empty:
    with st.expander(f"📋 Días con impacto ({len(dias_con_impacto)} días)"):
        st.dataframe(dias_con_impacto.reset_index(drop=True), use_container_width=True)

# =====================================================================
# GRÁFICO 3: COMPARATIVA POR HORAS — FECHA REAL VS FECHA ESTIMADA
# =====================================================================
st.markdown("---")
st.subheader("🕐 Comparativa por Horas: Día Real vs Día Estimado")
st.markdown(
    "Compara la distribución horaria de un día **observado** (izquierda) "
    "contra un día **estimado** (derecha). Útil para validar si el modelo "
    "replica el patrón de un viernes real en un viernes futuro."
)

col_izq, col_der = st.columns(2)

fechas_reales_disp = sorted(df_real_diario["fecha"].dt.strftime("%Y-%m-%d").unique())
fechas_est_disp = sorted(df_proyeccion["fecha"].dt.strftime("%Y-%m-%d").unique())

with col_izq:
    st.markdown("**📅 Día Observado (Real)**")
    fecha_real_sel = st.selectbox(
        "Fecha real", options=fechas_reales_disp,
        index=len(fechas_reales_disp) - 1, key="comp_fecha_real",
    )

with col_der:
    st.markdown("**📅 Día Estimado (Proyectado)**")
    fecha_est_sel = st.selectbox(
        "Fecha estimada", options=fechas_est_disp,
        index=0, key="comp_fecha_est",
    )

fecha_real_dt = pd.Timestamp(fecha_real_sel)
fecha_est_dt = pd.Timestamp(fecha_est_sel)
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown(f"**{fecha_real_sel}** ({dias_semana[fecha_real_dt.weekday()]})")
    sub_real = df_hist[
        (df_hist["DEPARTAMENTO"] == departamento_sel) & (df_hist["fecha"] == fecha_real_dt)
    ]
    real_hora = sub_real.groupby("hora")["# AUTORIZACION"].count().reindex(range(24), fill_value=0)
    chart_real = pd.DataFrame({"Demanda Real": real_hora})
    chart_real.index.name = "Hora"
    st.bar_chart(chart_real, use_container_width=True)
    st.caption(f"Total: {int(real_hora.sum())} servicios")

with col_g2:
    st.markdown(f"**{fecha_est_sel}** ({dias_semana[fecha_est_dt.weekday()]})")
    sub_est = df_proyeccion[df_proyeccion["fecha"] == fecha_est_dt]
    est_base_hora = sub_est.set_index("hora")["estimacion_base"].reindex(range(24), fill_value=0)
    est_mundial_hora = sub_est.set_index("hora")["estimacion_con_mundial"].reindex(range(24), fill_value=0)

    chart_est_df = pd.DataFrame({
        "Hora": list(range(24)) * 2,
        "Servicios": list(est_base_hora.values) + list(est_mundial_hora.values),
        "Tipo": ["Est. Base"] * 24 + ["Est. + Partidos"] * 24,
    })
    chart_alt_est = (
        alt.Chart(chart_est_df)
        .mark_bar()
        .encode(
            x=alt.X("Hora:O", title="Hora"),
            y=alt.Y("Servicios:Q", title="Servicios"),
            color=alt.Color("Tipo:N", title=""),
            xOffset="Tipo:N",
        )
        .properties(height=350)
    )
    st.altair_chart(chart_alt_est, use_container_width=True)
    st.caption(f"Total base: {int(est_base_hora.sum())} | Total + partidos: {int(est_mundial_hora.sum())} servicios")

# =====================================================================
# GRÁFICO 4: SERVICIOS NOCTURNOS 6 PM → 6 AM (CRUZA MEDIANOCHE)
# =====================================================================
st.markdown("---")
st.subheader("🌙 Servicios Nocturnos: 6 PM → 6 AM del día siguiente")
st.markdown(
    "Selecciona el día de **inicio** de la noche. "
    "Se mostrarán los servicios estimados desde las **18:00** de ese día "
    "hasta las **06:00** del día siguiente."
)

fechas_est_disp_noct = sorted(df_proyeccion["fecha"].dt.strftime("%Y-%m-%d").unique())

fecha_noche_sel = st.selectbox(
    "Día de inicio de la noche",
    options=fechas_est_disp_noct,
    key="fecha_noche",
)

fecha_noche_dt = pd.Timestamp(fecha_noche_sel)
fecha_siguiente_dt = fecha_noche_dt + pd.Timedelta(days=1)

HORAS_NOCHE = list(range(18, 24)) + list(range(0, 7))   # 18,19,...,23,0,1,...,6
ETIQUETAS_NOCHE = [f"{h:02d}:00" for h in range(18, 24)] + [f"{h:02d}:00 (+1)" for h in range(0, 7)]

filas_noche = []
for i, h in enumerate(HORAS_NOCHE):
    fecha_buscar = fecha_noche_dt if h >= 18 else fecha_siguiente_dt
    sub = df_proyeccion[(df_proyeccion["fecha"] == fecha_buscar) & (df_proyeccion["hora"] == h)]
    base_val    = int(sub["estimacion_base"].values[0])    if len(sub) else 0
    mundial_val = int(sub["estimacion_con_mundial"].values[0]) if len(sub) else 0
    filas_noche.append({
        "Hora":          ETIQUETAS_NOCHE[i],
        "orden":         i,
        "Est. Base":     base_val,
        "Est. + Mundial": mundial_val,
    })

df_noche = pd.DataFrame(filas_noche)
df_noche_long = df_noche.melt(
    id_vars=["Hora", "orden"],
    value_vars=["Est. Base", "Est. + Mundial"],
    var_name="Tipo",
    value_name="Servicios",
)

# Si el toggle de mundial está apagado, ocultar esa serie
if not mostrar_mundial:
    df_noche_long = df_noche_long[df_noche_long["Tipo"] == "Est. Base"]

orden_horas = df_noche["Hora"].tolist()

chart_noche = (
    alt.Chart(df_noche_long)
    .mark_bar()
    .encode(
        x=alt.X("Hora:O", title="Hora", sort=orden_horas),
        y=alt.Y("Servicios:Q", title="Servicios estimados"),
        color=alt.Color(
            "Tipo:N",
            title="",
            scale=alt.Scale(
                domain=["Est. Base", "Est. + Mundial"],
                range=["#F58518", "#54A24B"],
            ),
        ),
        xOffset="Tipo:N",
        tooltip=[
            alt.Tooltip("Hora:O", title="Hora"),
            alt.Tooltip("Tipo:N", title="Serie"),
            alt.Tooltip("Servicios:Q", title="Servicios"),
        ],
    )
    .properties(height=350)
)

st.altair_chart(chart_noche, use_container_width=True)

# Totales de la noche
total_base_noche    = df_noche["Est. Base"].sum()
total_mundial_noche = df_noche["Est. + Mundial"].sum()

dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
label_inicio  = f"{fecha_noche_sel} ({dias_semana[fecha_noche_dt.weekday()]})"
label_fin     = f"{fecha_siguiente_dt.strftime('%Y-%m-%d')} ({dias_semana[fecha_siguiente_dt.weekday()]})"
st.caption(f"🌙 Noche del **{label_inicio}** al **{label_fin}**")

col_n1, col_n2 = st.columns(2)
with col_n1:
    st.metric("Total Est. Base (6 PM→6 AM)", f"{total_base_noche:,} servicios")
with col_n2:
    if mostrar_mundial:
        st.metric("Total Est. + Mundial (6 PM→6 AM)", f"{total_mundial_noche:,} servicios",
                  delta=f"+{total_mundial_noche - total_base_noche:,}" if total_mundial_noche > total_base_noche else "Sin impacto")

# =====================================================================
# BOTÓN GUARDAR MODELO
# =====================================================================
st.markdown("---")
st.subheader("💾 Guardar Modelo")
st.markdown(
    "Al guardar, se calcula la proyección con estos parámetros para **todos los departamentos** "
    "y se pasan a la página de **Estimación de Técnicos**."
)

if st.button("✅ Guardar Modelo y Continuar", type="primary", use_container_width=True):
    todos_deptos = sorted(df_hist["DEPARTAMENTO"].unique().tolist())
    proyecciones_nuevas = {}

    for depto in todos_deptos:
        mat = construir_matriz_historica(df_hist, depto)
        proy = calcular_proyeccion_desde_tablas(
            mat, percentil, semanas_historicas, df_col_edit, df_otros_edit
        )
        proy["estimacion_base"] = (proy["estimacion_base"] * (pct_bolivar / 100.0)).round(1)
        proy["estimacion_con_mundial"] = (proy["estimacion_con_mundial"] * (pct_bolivar / 100.0)).round(1)
        proy = aplicar_piso_minimo(proy, piso=1)
        proyecciones_nuevas[depto] = proy

    params_guardados = {
        "percentil": percentil,
        "semanas_historicas": semanas_historicas,
        "pct_bolivar": pct_bolivar,
        "partidos_colombia": df_col_edit.to_dict("records"),
        "partidos_otros": df_otros_edit.to_dict("records"),
    }

    st.session_state["proyecciones"] = proyecciones_nuevas
    st.session_state["parametros_modelo"] = params_guardados
    st.session_state["modelo_guardado"] = True

    st.success(
        f"✅ Modelo guardado para: **{', '.join(todos_deptos)}** — "
        f"P{percentil}, {semanas_historicas} semanas, Ruta Bolívar {pct_bolivar}%. "
        f"Ve a **Estimación de Técnicos** →"
    )

# =====================================================================
# DESCARGA DE PRONÓSTICOS (día operativo 18:00 → 17:59 del día siguiente)
# =====================================================================
if st.session_state.get("proyecciones"):
    st.markdown("---")
    st.subheader("⬇️ Descargar Pronósticos Guardados")
    st.caption("Se exportan todos los departamentos guardados con la estimación hora a hora.")

    trozos = []
    for depto, df_dl in st.session_state["proyecciones"].items():
        df_dl = df_dl.copy()
        df_dl["fecha"] = pd.to_datetime(df_dl["fecha"])
        df_dl["departamento"] = depto
        trozos.append(df_dl[[
            "departamento", "fecha", "hora",
            "estimacion_base", "factor", "estimacion_con_mundial",
        ]])

    df_export = pd.concat(trozos, ignore_index=True)
    df_export.columns = [
        "Departamento", "Fecha", "Hora",
        "Est. Base", "Factor Partido", "Est. + Mundial",
    ]
    df_export = df_export.sort_values(["Departamento", "Fecha", "Hora"]).reset_index(drop=True)

    p_dl = st.session_state.get("parametros_modelo", {})
    deptos_str = "_".join(d.replace(" ", "_") for d in sorted(st.session_state["proyecciones"].keys()))
    nombre_archivo = (
        f"pronostico_{deptos_str}"
        f"_P{p_dl.get('percentil','')}"
        f"_bolivar{p_dl.get('pct_bolivar', 100)}pct.csv"
    )

    csv_bytes = df_export.to_csv(index=False, sep=";").encode("utf-8")
    st.download_button(
        label="💾 Descargar Pronósticos — Todos los Departamentos (CSV)",
        data=csv_bytes,
        file_name=nombre_archivo,
        mime="text/csv",
        use_container_width=True,
    )
