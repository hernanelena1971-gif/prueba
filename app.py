import streamlit as st
from supabase import create_client
import folium
from streamlit_folium import st_folium
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

# --------------------------------------------------
# Session state (solo auth)
# --------------------------------------------------
if "session" not in st.session_state:
    st.session_state.session = None
if "user" not in st.session_state:
    st.session_state.user = None
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
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            st.session_state.session = res.session
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.error("Email o contraseña incorrectos")

    st.stop()

# --------------------------------------------------
# Usuario autenticado (Auth)
# --------------------------------------------------
user = st.session_state.user
auth_user_id = user.id
user_email = user.email

# --------------------------------------------------
# Usuario histórico (SIEMPRE recalculado desde Auth)
# --------------------------------------------------
usuario_res = (
    supabase
    .table("usuarios")
    .select("id,nombre")
    .eq("auth_user_id", auth_user_id)
    .single()
    .execute()
)

st.title("🗺️ Sitios y análisis de suelos")
st.caption(f"Usuario autenticado: {user_email}")

if not usuario_res.data:
    st.info("No hay sitios asociados a este usuario.")
    if st.button("Cerrar sesión"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()
    st.stop()

usuario_id = usuario_res.data["id"]
usuario_nombre = usuario_res.data["nombre"]

# --------------------------------------------------
# Logout
# --------------------------------------------------
if st.button("🚪 Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

# --------------------------------------------------
# Sitios del usuario (MISMA lógica que antes)
# --------------------------------------------------
sitios = (
    supabase
    .table("sitios")
    .select("id,codigo_sitio,latitud,longitud")
    .eq("usuario_id", usuario_id)
    .execute()
).data

if not sitios:
    st.info("No hay sitios asociados.")
    st.stop()

def idx_by_id(items, sid):
    for i, s in enumerate(items):
        if s["id"] == sid:
            return i
    return 0

sitio_sel = st.selectbox(
    "📍 Seleccione un sitio",
    sitios,
    format_func=lambda s: s["codigo_sitio"],
    index=idx_by_id(sitios, st.session_state.sitio_id)
)

st.session_state.sitio_id = sitio_sel["id"]

# --------------------------------------------------
# Mapa
# --------------------------------------------------
lats = [s["latitud"] for s in sitios if s["latitud"] is not None]
lons = [s["longitud"] for s in sitios if s["longitud"] is not None]

m = folium.Map(tiles="OpenStreetMap")
if lats and lons:
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

for s in sitios:
    folium.Marker(
        [s["latitud"], s["longitud"]],
        tooltip=s["codigo_sitio"],
        icon=folium.Icon(
            color="red" if s["id"] == st.session_state.sitio_id else "blue"
        )
    ).add_to(m)

st_folium(m, height=500)

# --------------------------------------------------
# Análisis (RPC original)
# --------------------------------------------------
st.subheader(f"🧪 Análisis – {sitio_sel['codigo_sitio']}")

data = (
    supabase
    .rpc(
        "get_informe_suelo_por_sitio",
        {"p_sitio_id": int(st.session_state.sitio_id)}
    )
    .execute()
).data

if not data:
    st.info("No hay análisis disponibles para este sitio.")
    st.stop()

row = data[0]

# --------------------------------------------------
# Informe completo (TODOS los análisis)
# --------------------------------------------------
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

st.table([{"Parámetro": k, "Valor": v} for k, v in informe])

# --------------------------------------------------
# PDF
# --------------------------------------------------
def generar_pdf(inf, titulo):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = A4[1] - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, titulo)
    y -= 30
    c.setFont("Helvetica", 10)

    for k, v in inf:
        if y < 50:
            c.showPage()
            y = A4[1] - 50
        c.drawString(50, y, f"{k}: {v}")
        y -= 14

    c.save()
    buffer.seek(0)
    return buffer

pdf = generar_pdf(
    informe,
    f"Informe de análisis de suelo – {sitio_sel['codigo_sitio']}"
)

st.download_button(
    "📄 Descargar informe PDF",
    pdf,
    file_name=f"informe_{sitio_sel['codigo_sitio']}.pdf",
    mime="application/pdf"
)
