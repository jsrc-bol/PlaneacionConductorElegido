import streamlit as st

st.set_page_config(page_title="Planeación Operativa - Conductor Elegido", layout="wide")

pagina_pronostico = st.Page("pages/pronostico.py", title="Pronóstico y Calibración", icon="📊")
pagina_tecnicos = st.Page("pages/tecnicos.py", title="Estimación de Técnicos", icon="🎛️")

nav = st.navigation([pagina_pronostico, pagina_tecnicos])
nav.run()
