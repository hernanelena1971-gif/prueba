import streamlit as st
from supabase import create_client
import folium
from streamlit_folium import st_folium
import pandas as pd
from supabase import create_client, ClientOptions

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generar_pdf_informe(informe, titulo="Informe de análisis de suelo"):
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
            c.setFont("Helvetica", 10)
            y = height - 50

        texto = f"{parametro}: {valor}"
        c.drawString(50, y, texto)
        y -= 15

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
    
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

data = (
    supabase
    .rpc(
        "public.get_informe_suelo_por_sitio",
        {"p_sitio_id": int(sitio_id)}
    )
    .execute()
).data

if not data:
    st.info("No hay análisis disponibles para este sitio.")
    st.stop()

row = data[0]

# ---------- Informe como lista (fuente única) ----------
informe = [
    ("Usuario", row["usuario"]),
    ("Sitio", row["sitio"]),
    ("Fecha de muestreo", row["fecha_muestreo"]),

    ("Número de laboratorio", row["numero_laboratorio"]),
    ("Profundidad de muestreo", row["profundidad"]),
    ("Uso actual", row["uso_actual"]),
    ("Uso anterior", row["uso_anterior"]),
    ("Uso posterior", row["uso_posterior"]),
    ("Observaciones", row["observaciones"]),

    ("Arena (%)", row["arena"]),
    ("Limo (%)", row["limo"]),
    ("Arcilla (%)", row["arcilla"]),
    ("Textura", row["textura"]),

    ("pH (pasta)", row["ph"]),
    ("Conductividad eléctrica", row["conductividad"]),
    ("Carbonato Ca + Mg", row["carbonato_ca_mg"]),
    ("Carbono orgánico", row["carbono_organico"]),
    ("Materia orgánica", row["materia_organica"]),
    ("Nitrógeno total", row["nitrogeno_total"]),
    ("Relación C/N", row["relacion_cn"]),
    ("Fósforo extractable", row["fosforo"]),
    ("Sodio intercambiable", row["sodio"]),
    ("Potasio intercambiable", row["potasio"]),
    ("Calcio intercambiable", row["calcio"]),
    ("Cloruro (extracto)", row["cloruro_extracto"]),
    ("Cloruro (suelo seco)", row["cloruro_suelo_seco"]),
    ("EAS", row["eas"]),
    ("Boro", row["boro"]),
]

# ---------- Mostrar tabla ----------
st.table(
    [{"Parámetro": k, "Valor": v} for k, v in informe]
)

# ---------- PASO 3: generar y descargar PDF ----------
pdf_buffer = generar_pdf_informe(
    informe,
    titulo=f"Informe de análisis de suelo - {row['sitio']}"
)

st.download_button(
    label="📄 Descargar informe en PDF",
    data=pdf_buffer,
    file_name=f"informe_suelo_{row['sitio']}.pdf",
    mime="application/pdf"
)
