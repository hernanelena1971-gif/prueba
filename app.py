import streamlit as st
from supabase import create_client
import folium
from streamlit_folium import st_folium
import pandas as pd
from supabase import create_client, ClientOptions


# --------------------------------------------------
# Configuración general
# --------------------------------------------------
st.set_page_config(
    page_title="Suelos – Sitios y análisis",
    layout="wide"
)

# --------------------------------------------------
# Supabase
# --------------------------------------------------
def get_supabase_client():
    if "session" in st.session_state and st.session_state.session:
        return create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_ANON_KEY"],
            ClientOptions(
                headers={
                    "Authorization": f"Bearer {st.session_state.session.access_token}"
                }
            )
        )
    else:
        return create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_ANON_KEY"]
        )

supabase = get_supabase_client()

# --------------------------------------------------
# Estado de sesión
# --------------------------------------------------
if "session" not in st.session_state:
    st.session_state.session = None

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
if st.session_state.session is None:
    st.title("🔐 Acceso al sistema")

    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        try:
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            st.session_state.session = res.session
            st.success("Ingreso correcto")
            st.rerun()
        except Exception as e:
            st.error("Error de login")
            st.code(str(e))


    st.stop()

# --------------------------------------------------
# USUARIO AUTENTICADO
# --------------------------------------------------

st.title("🗺️ Sitios y análisis de suelos")

if st.button("🚪 Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.session = None
    st.rerun()

# --------------------------------------------------
# SITIOS (RLS filtra automáticamente)
# --------------------------------------------------
sitios = (
    supabase
    .table("sitios")
    .select("id,codigo_sitio,latitud,longitud")
    .execute()
).data

if not sitios:
    st.info("No hay sitios asociados a este usuario.")
    st.stop()

# --------------------------------------------------
# Selector de sitio (UX, no seguridad)
# --------------------------------------------------
sitio_sel = st.selectbox(
    "📍 Seleccione un sitio",
    sitios,
    format_func=lambda s: s["codigo_sitio"]
)

sitio_id = sitio_sel["id"]

# --------------------------------------------------
# MAPA (siempre visible)
# --------------------------------------------------
center = [sitio_sel["latitud"], sitio_sel["longitud"]]

m = folium.Map(
    location=center,
    zoom_start=8,
    tiles="OpenStreetMap"
)

for s in sitios:
    if s["latitud"] is None or s["longitud"] is None:
        continue

    color = "red" if s["id"] == sitio_id else "blue"

    folium.Marker(
        location=[s["latitud"], s["longitud"]],
        popup=f"<b>{s['codigo_sitio']}</b>",
        tooltip=s["codigo_sitio"],
        icon=folium.Icon(color=color, icon="info-sign")
    ).add_to(m)

st_folium(m, width=1200, height=550)

# --------------------------------------------------
# ANALISIS DEL SITIO SELECCIONADO
# --------------------------------------------------
st.subheader(f"🧪 Análisis – Sitio {sitio_sel['codigo_sitio']}")

analisis = (
    supabase
    .table("analisis_suelos")
    .select(
        "*, muestras!inner(id, fecha, sitio_id)"
    )
    .eq("muestras.sitio_id", sitio_id)
    .execute()
).data

if not analisis:
    st.info("No hay análisis disponibles para este sitio.")
else:
    df = pd.DataFrame(analisis)
    st.dataframe(df, use_container_width=True)
