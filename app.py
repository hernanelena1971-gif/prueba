import streamlit as st
from supabase import create_client
import folium
from streamlit_folium import st_folium
from shapely.geometry import shape

st.set_page_config(
    page_title="Sitios por usuario",
    layout="wide"
)

st.title("🗺️ Sitios por usuario")

# ============================
# Supabase client
# ============================
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

# ============================
# 1. Cargar usuarios
# ============================
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

# ============================
# 2. Cargar sitios del usuario
# ============================
sitios_resp = (
    supabase
    .table("sitios")
    .select("id,nombre,geom")
    .eq("usuario_id", usuario_id)
    .execute()
)

sitios = sitios_resp.data

st.markdown("---")
st.subheader(f"📍 Sitios de {usuario_sel['nombre']}")

if not sitios:
    st.warning("Este usuario no tiene sitios cargados.")
    st.stop()

# ============================
# 3. Crear mapa
# ============================
# Tomamos el primer punto para centrar el mapa
first_geom = shape(sitios[0]["geom"])
center = [first_geom.y, first_geom.x]

m = folium.Map(
    location=center,
    zoom_start=8,
    tiles="OpenStreetMap"
)

# ============================
# 4. Agregar marcadores
# ============================
for s in sitios:
    if s["geom"] is None:
        continue

    geom = shape(s["geom"])

    folium.Marker(
        location=[geom.y, geom.x],
        popup=folium.Popup(
            f"<b>{s['nombre']}</b><br>ID sitio: {s['id']}",
            max_width=300
        ),
        tooltip=s["nombre"],
        icon=folium.Icon(color="green", icon="info-sign")
    ).add_to(m)

# ============================
# 5. Mostrar mapa
# ============================
st_folium(m, width=1100, height=600)

# ============================
# 6. Tabla (opcional y útil)
# ============================
with st.expander("📋 Ver tabla de sitios"):
    st.dataframe(sitios)
