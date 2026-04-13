import streamlit as st
from supabase import create_client
import folium
from streamlit_folium import st_folium
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ==================================================
# CONFIGURACIÓN GENERAL
# ==================================================
st.set_page_config(page_title="Suelos – Sitios y análisis", layout="wide")

# ==================================================
# SUPABASE (UN SOLO CLIENTE)
# ==================================================
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

# ==================================================
# ESTADO DE SESIÓN STREAMLIT
# ==================================================
if "session" not in st.session_state:
    st.session_state.session = None
if "user" not in st.session_state:
    st.session_state.user = None
if "sitio_id" not in st.session_state:
    st.session_state.sitio_id = None

# ==================================================
# LOGIN EMAIL + PASSWORD
# ==================================================
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
            # Guardamos SESSION y USER (NO usar get_user())
            st.session_state.session = res.session
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.error("Email o contraseña incorrectos")

    st.stop()
def get_auth_user_id(user):
    # soporta objeto o dict
    if isinstance(user, dict):
        return user.get("id")
    return getattr(user, "id", None)

# ==================================================
# USUARIO AUTENTICADO (DESDE SESSION_STATE)
# ==================================================
user = st.session_state.user          # dict
auth_user_id = user["id"]             # UUID
user_email = user.get("email", "")

# ==================================================
# PERFIL (COMPATIBLE CON USUARIOS VIEJOS)
# ==================================================
perfil_res = (
    supabase
    .table("perfiles")
    .select("must_change_password")
    .eq("user_id", auth_user_id)
    .execute()
)

# Si el usuario es antiguo y no tenía perfil, lo creamos
if not perfil_res.data:
    supabase.table("perfiles").insert({
        "user_id": auth_user_id,
        "must_change_password": False
    }).execute()
    must_change_password = False
else:
    must_change_password = perfil_res.data[0]["must_change_password"]

# ==================================================
# CAMBIO OBLIGATORIO DE CONTRASEÑA (SOLO SI CORRESPONDE)
# ==================================================
if must_change_password:
    st.title("🔑 Primer ingreso")
    st.info("Por seguridad, debés cambiar tu contraseña temporal.")

    new_pass = st.text_input("Nueva contraseña", type="password")
    confirm = st.text_input("Confirmar contraseña", type="password")

    if st.button("Cambiar contraseña"):
        if not new_pass or not confirm:
            st.warning("Completá ambos campos")
        elif new_pass != confirm:
            st.error("Las contraseñas no coinciden")
        elif len(new_pass) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres")
        else:
            try:
                supabase.auth.update_user({"password": new_pass})
                supabase.table("perfiles").update({
                    "must_change_password": False
                }).eq("user_id", auth_user_id).execute()
                st.success("✅ Contraseña actualizada")
                st.rerun()
            except Exception as e:
                st.error("No se pudo actualizar la contraseña")
                st.exception(e)

    st.stop()

# ==================================================
# APLICACIÓN PRINCIPAL
# ==================================================
st.title("🗺️ Sitios y análisis de suelos")
st.caption(f"Usuario: {user_email}")

if st.button("🚪 Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.session = None
    st.session_state.user = None
    st.session_state.sitio_id = None
    st.rerun()

# ==================================================
# SITIOS (RLS FILTRA POR auth.uid())
# ==================================================
sitios = (
    supabase
    .table("sitios")
    .select("id,codigo_sitio,latitud,longitud")
    .execute()
).data

if not sitios:
    st.info("No hay sitios asociados a este usuario.")
    st.stop()

# ==================================================
# SELECTOR DE SITIO
# ==================================================
def index_by_id(items, item_id):
    for i, it in enumerate(items):
        if it["id"] == item_id:
            return i
    return 0

sitio_sel = st.selectbox(
    "📍 Seleccione un sitio",
    sitios,
    format_func=lambda s: s["codigo_sitio"],
    index=index_by_id(sitios, st.session_state.sitio_id)
)

st.session_state.sitio_id = sitio_sel["id"]

# ==================================================
# MAPA
# ==================================================
m = folium.Map(tiles="OpenStreetMap")
lats = [s["latitud"] for s in sitios if s["latitud"] is not None]
lons = [s["longitud"] for s in sitios if s["longitud"] is not None]
if lats and lons:
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

for s in sitios:
    folium.Marker(
        [s["latitud"], s["longitud"]],
        tooltip=s["codigo_sitio"],
        icon=folium.Icon(color="red" if s["id"] == st.session_state.sitio_id else "blue")
    ).add_to(m)

st_folium(m, height=500)

# ==================================================
# ANÁLISIS (RPC ORIGINAL)
# ==================================================
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
    st.info("No hay análisis disponibles.")
    st.stop()

row = data[0]

# ==================================================
# INFORME
# ==================================================
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

# ==================================================
# PDF
# ==================================================
def generar_pdf(inf, titulo):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
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
    buf.seek(0)
    return buf

pdf = generar_pdf(informe, f"Informe – {sitio_sel['codigo_sitio']}")

st.download_button(
    "📄 Descargar PDF",
    pdf,
    f"informe_{sitio_sel['codigo_sitio']}.pdf",
    "application/pdf"
)
