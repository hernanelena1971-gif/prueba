import streamlit as st
from supabase import create_client
import folium
from streamlit_folium import st_folium

# --------------------------------------------------
# Configuración de la página
# --------------------------------------------------
st.set_page_config(
    page_title="Sitios por usuario",
    layout="wide"
)

st.title("🗺️ Sitios por usuario")

# --------------------------------------------------
# Conexión a Supabase (API)
# --------------------------------------------------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

# --------------------------------------------------
# Cargar usuarios
# --------------------------------------------------
usuarios_resp = (
    supabase
    .table("usuarios")
    .select("id,nombre")
    .order("nombre")
    .execute()
)

if not usuarios_resp.data:
    st.error("No hay usuarios cargados.")
    st.stop()

usuarios = usuarios_resp.data

usuario_sel = st.selectbox(
    "👤 Seleccioná el usuario",
    options=usuarios,
    format_func=lambda u: u["nombre"]
)

usuario_id = usuario_sel["id"]

# --------------------------------------------------
# Cargar sitios del usuario (lat / lon)
# --------------------------------------------------
sitios_resp = (
    supabase
    .table("sitios")
    .select("id,latitud,longitud")
    .eq("usuario_id", usuario_id)
    .execute()
)

sitios = sitios_resp.data

st.markdown("---")

if not sitios:
    st.warning("Este usuario no tiene sitios cargados.")
    st.stop()

# --------------------------------------------------
# Crear mapa centrado en el primer sitio
# --------------------------------------------------
center = [
    sitios[0]["latitud"],
    sitios[0]["longitud"]
]

m = folium.Map(
    location=center,
    zoom_start=8,
    tiles="OpenStreetMap"
)

# --------------------------------------------------
# Agregar marcadores
# --------------------------------------------------
for s in sitios:
    if s["latitud"] is None or s["longitud"] is None:
        continue

    folium.Marker(
        location=[s["latitud"], s["longitud"]],
        popup=f"ID sitio: {s['id']}",
        tooltip=f"Sitio {s['id']}",
        icon=folium.Icon(color="green", icon="info-sign")
    ).add_to(m)

# --------------------------------------------------
# Mostrar mapa
# --------------------------------------------------
st_folium(m, width=1150, height=600)

# --------------------------------------------------
# Tabla opcional de sitios
# --------------------------------------------------
with st.expander("📋 Ver tabla de sitios"):
    st.dataframe(sitios)
