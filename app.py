import streamlit as st
from supabase import create_client, ClientOptions
import folium
from streamlit_folium import st_folium
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# --------------------------------------------------
# PDF
# --------------------------------------------------
def generar_pdf_informe(informe, titulo):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, titulo)
    y -= 30

    c.setFont("Helvetica", 10)
    for parametro, valor in informe:
        if y < 50:
            c.showPage()
            y = height - 50
        c.drawString(50, y, f"{parametro}: {valor}")
        y -= 15

    c.save()
    buffer.seek(0)
    return buffer

# --------------------------------------------------
# Config
# --------------------------------------------------
st.set_page_config(page_title="Suelos – Sitios y análisis", layout="wide")

# --------------------------------------------------
# Supabase client (CLAVE PARA RLS)
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
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"]
    )

supabase = get_supabase_client()

# --------------------------------------------------
# Session state
# --------------------------------------------------
if "session" not in st.session_state:
    st.session_state.session = None
if "sitio_id" not in st.session_state:
    st.session_state.sitio_id = None

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
if st.session_state.session is None:
    st.title("🔐 Acceso al sistema")

    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        try:
            res = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            st.session_state.session = res.session
            st.success("Ingreso correcto")
            st.rerun()
        except Exception as e:
            st.error("Error de login")
            st.code(str(e))
    st.stop()

# --------------------------------------------------
# App principal
# --------------------------------------------------
st.title("🗺️ Sitios y análisis de suelos")

if st.button("🚪 Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.session = None
    st.session_state.sitio_id = None
    st.rerun()

# --------------------------------------------------
# SITIOS – RLS FILTRA (COMO ANTES)
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

sitio_sel = st.selectbox(
    "📍 Seleccione un sitio",
    sitios,
    format_func=lambda s: s["codigo_sitio"],
    index=0 if st.session_state.sitio_id is None else
    next(i for i, s in enumerate(sitios) if s["id"] == st.session_state.sitio_id)
)

st.session_state.sitio_id = sitio_sel["id"]

# --------------------------------------------------
# MAPA
# --------------------------------------------------
lats = [s["latitud"] for s in sitios if s["latitud"] is not None]
lons = [s["longitud"] for s in sitios if s["longitud"] is not None]

m = folium.Map(tiles="OpenStreetMap")

if lats and lons:
    m.fit_bounds([
        [min(lats), min(lons)],
        [max(lats), max(lons)]
    ])

for s in sitios:
    folium.Marker(
        [s["latitud"], s["longitud"]],
        tooltip=s["codigo_sitio"],
        icon=folium.Icon(
            color="red" if s["id"] == st.session_state.sitio_id else "blue"
        )
    ).add_to(m)

st_folium(m, width=1200, height=550)

# --------------------------------------------------
# ANÁLISIS (RPC)
# --------------------------------------------------
st.subheader(f"🧪 Análisis – Sitio {sitio_sel['codigo_sitio']}")

data = supabase.rpc(
    "get_informe_suelo_por_sitio",
    {"p_sitio_id": int(st.session_state.sitio_id)}
).execute().data

if not data:
    st.info("No hay análisis disponibles.")
    st.stop()

row = data[0]

informe = [(k.replace("_"," ").title(), v) for k,v in row.items()]
st.table([{"Parámetro": k, "Valor": v} for k,v in informe])

pdf_buffer = generar_pdf_informe(
    informe,
    f"Informe de análisis de suelo – {sitio_sel['codigo_sitio']}"
)

st.download_button(
    "📄 Descargar informe PDF",
    pdf_buffer,
    file_name=f"informe_{sitio_sel['codigo_sitio']}.pdf",
    mime="application/pdf"
)
