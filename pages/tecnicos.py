import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import linprog

st.title("🎛️ Estimación de Técnicos — Optimización de Turnos")

# =====================================================================
# VALIDAR QUE EL MODELO FUE GUARDADO
# =====================================================================
if "modelo_guardado" not in st.session_state or not st.session_state.get("modelo_guardado"):
    st.warning(
        "⚠️ No hay un modelo guardado. Ve a la página **Pronóstico y Calibración**, "
        "ajusta los parámetros y haz clic en **Guardar Modelo**."
    )
    st.stop()

df_proyeccion = st.session_state["proyeccion"].copy()
params = st.session_state["parametros_modelo"]

st.success(
    f"Modelo cargado: P{params['percentil']} | {params['semanas_historicas']} semanas | "
    f"{params['departamento']}"
)

# =====================================================================
# SIDEBAR — PARÁMETROS DE OPTIMIZACIÓN
# =====================================================================
st.sidebar.header("⚙️ Motor de Optimización")

# --- CONFIGURACIÓN DE TIPOS DE TURNO ---
st.sidebar.markdown("**📐 Tipos de Turno Disponibles:**")
st.sidebar.caption("Selecciona las duraciones que quieres probar (3–9 horas). Puedes agregar varias.")

duraciones_disponibles = list(range(3, 10))  # 3, 4, 5, 6, 7, 8, 9

duraciones_seleccionadas = st.sidebar.multiselect(
    "Duraciones de turno (horas)",
    options=duraciones_disponibles,
    default=[6, 8],
    format_func=lambda x: f"{x} Horas",
    help="Mínimo 3h, máximo 9h. El optimizador solo creará turnos con las duraciones seleccionadas.",
)

if not duraciones_seleccionadas:
    st.sidebar.error("Selecciona al menos una duración de turno.")
    st.stop()

# Costos por cada duración seleccionada
st.sidebar.markdown("**💰 Costo por Tipo de Turno:**")
costos_turno = {}
for dur in sorted(duraciones_seleccionadas):
    default_cost = round(3.0 + (dur - 3) * 0.25, 1)  # Escalado base
    costos_turno[dur] = st.sidebar.number_input(
        f"Costo Turno {dur}h", value=default_cost, step=0.5, min_value=0.5, key=f"costo_{dur}h",
    )

st.sidebar.markdown("---")
st.sidebar.markdown("**⚡ Eficiencia y Penalizaciones:**")
productividad = st.sidebar.slider(
    "Productividad (Viajes/Hora por conductor)", 0.5, 1.5, 6.0 / 7.0, 0.05,
)
penalizacion = st.sidebar.number_input(
    "Penalización por Servicio Incumplido", value=4.0, step=0.5,
    help="Valores bajos (3-5) = conservador, solo abre turnos cuando la demanda lo justifica.",
)

# =====================================================================
# EJECUTAR OPTIMIZACIÓN
# =====================================================================
if st.sidebar.button("🚀 Correr Optimización", use_container_width=True):
    with st.spinner("Resolviendo optimización matemática..."):
        try:
            departamento = params["departamento"]
            df_dept = df_proyeccion.copy().reset_index(drop=True)
            T = len(df_dept)
            D = df_dept["estimacion_con_mundial"].values

            # Generar variables válidas para cada duración de turno
            turnos_config = []  # Lista de (duración, indices_válidos, costo)
            for dur in sorted(duraciones_seleccionadas):
                valid_indices = [
                    t for t in range(T)
                    if (df_dept.loc[t, "hora"] >= 18 or df_dept.loc[t, "hora"] <= 5)
                    and t <= T - dur
                ]
                turnos_config.append((dur, valid_indices, costos_turno[dur]))

            # Calcular total de variables de turno
            total_turno_vars = sum(len(indices) for _, indices, _ in turnos_config)
            num_vars = total_turno_vars + T  # + variables de slack (demanda incumplida)

            # Vector de costos
            c = []
            for dur, indices, costo in turnos_config:
                c.extend([costo] * len(indices))
            c.extend([penalizacion] * T)

            # Restricciones: para cada slot t, la cobertura debe >= demanda
            A_ub, b_ub = [], []
            for t in range(T):
                row = [0.0] * num_vars
                h = df_dept.loc[t, "hora"]
                demanda_objetivo = D[t] if (h >= 18 or h <= 6) else 0.0

                # Para cada tipo de turno, ver qué turnos cubren el slot t
                offset = 0
                for dur, indices, _ in turnos_config:
                    for idx, s in enumerate(indices):
                        if s <= t <= s + dur - 1:
                            row[offset + idx] = -productividad
                    offset += len(indices)

                # Variable de slack
                row[total_turno_vars + t] = -1.0
                A_ub.append(row)
                b_ub.append(-demanda_objetivo)

            # Resolver
            integrality = [1] * total_turno_vars + [0] * T
            res = linprog(
                c, A_ub=A_ub, b_ub=b_ub,
                bounds=[(0, None)] * num_vars,
                integrality=integrality,
            )

            shift_rows = []
            if res.success:
                offset = 0
                for dur, indices, _ in turnos_config:
                    X = np.round(res.x[offset:offset + len(indices)]).astype(int)
                    for idx, s in enumerate(indices):
                        if X[idx] > 0:
                            row_data = df_dept.loc[s]
                            shift_rows.append({
                                "Fecha": pd.Timestamp(row_data["fecha"]).strftime("%Y-%m-%d"),
                                "Servicios Estimados": int(sum(D[s:s + dur])),
                                "Hora inicio": f"{int(row_data['hora'])}:00",
                                "Hora final": f"{int((row_data['hora'] + dur) % 24)}:00",
                                "Duracion de turno": f"{dur} Horas",
                                "Departamento": departamento,
                                "# de turnos": X[idx],
                            })
                    offset += len(indices)

            df_malla = pd.DataFrame(shift_rows)
            st.session_state["malla_simulada"] = df_malla
            st.success("🎯 Optimización completada.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# =====================================================================
# RESULTADOS
# =====================================================================
st.write("---")

if "malla_simulada" in st.session_state and not st.session_state["malla_simulada"].empty:
    df_res = st.session_state["malla_simulada"].copy()

    # KPIs dinámicos según duraciones en los resultados
    duraciones_resultado = sorted(df_res["Duracion de turno"].unique())
    cols_kpi = st.columns(min(len(duraciones_resultado) + 1, 4))
    with cols_kpi[0]:
        st.metric("Conductores Totales Citados", f"{int(df_res['# de turnos'].sum()):,}")
    for i, dur_label in enumerate(duraciones_resultado[:3]):
        with cols_kpi[i + 1]:
            n_bloques = len(df_res[df_res["Duracion de turno"] == dur_label])
            st.metric(f"Bloques {dur_label}", f"{n_bloques:,}")

    # Pivot de turnos
    matriz_pivot = df_res.pivot_table(
        index=["Departamento", "Hora inicio", "Hora final", "Duracion de turno"],
        columns="Fecha",
        values="# de turnos",
        aggfunc="sum",
    ).fillna(0).astype(int)

    # Pivot de servicios estimados
    matriz_servicios = df_res.pivot_table(
        index=["Departamento", "Hora inicio", "Hora final", "Duracion de turno"],
        columns="Fecha",
        values="Servicios Estimados",
        aggfunc="sum",
    ).fillna(0).astype(int)

    st.subheader("🗓️ Matriz de Distribución de Turnos")

    vista_matriz = st.radio(
        "Vista:",
        options=["Técnicos asignados", "Servicios estimados", "Combinada (técnicos / servicios)"],
        horizontal=True,
        key="vista_matriz",
    )

    if vista_matriz == "Técnicos asignados":
        st.dataframe(matriz_pivot, use_container_width=True)
    elif vista_matriz == "Servicios estimados":
        st.dataframe(matriz_servicios, use_container_width=True)
    else:
        # Combinada: "turnos (servicios)"
        matriz_combinada = matriz_pivot.copy().astype(str)
        for col in matriz_pivot.columns:
            for idx in matriz_pivot.index:
                t = int(matriz_pivot.loc[idx, col])
                s = int(matriz_servicios.loc[idx, col]) if idx in matriz_servicios.index else 0
                if t > 0:
                    matriz_combinada.loc[idx, col] = f"{t} ({s} svcs)"
                else:
                    matriz_combinada.loc[idx, col] = "—"
        st.dataframe(matriz_combinada, use_container_width=True)

    st.caption("💡 Usa el selector de vista para alternar entre técnicos, servicios o ambos.")

    csv_data = df_res.to_csv(index=False, sep=";").encode("utf-8")
    st.download_button(
        "💾 Descargar Malla (CSV)", data=csv_data,
        file_name="malla_turnos_optimizada.csv", mime="text/csv",
    )
else:
    st.info("💡 Ajusta los parámetros y haz clic en **Correr Optimización** para generar la malla.")
