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
st.set_page_config(
    page_title="Suelos – Sitios y análisis",
    layout="wide"
)

# ==================================================
# SUPABASE — UN SOLO CLIENTE (MUY IMPORTANTE)
# ==================================================
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

# ==================================================
# ESTADO DE SESIÓN
# ==================================================
if "session" not in st.session_state:
    st.session_state.session = None

if "sitio_id" not in st.session_state:
    st.session_state.sitio_id = None

# ==================================================
# LOGIN SIMPLE (EMAIL + PASSWORD)
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
            st.session_state.session = res.session
            st.rerun()
        except Exception:
            st.error("Email o contraseña incorrectos")

    st.stop()

# ==================================================
# USUARIO AUTENTICADO
# ==================================================
user_response = supabase.auth.get_user()

if not user_response or not user_response.user:
    st.error("No se pudo obtener el usuario autenticado")
    st.stop()

# ✅ MUY IMPORTANTE: el user es un DICcionario
auth_user_id = user_response.user["id"]
user_email = user_response.user.get("email", "")

# ==================================================
# PERFIL — SOPORTA USUARIOS VIEJOS Y NUEVOS
# ==================================================
perfil_res = (
    supabase
    .table("perfiles")
    .select("must_change_password")
    .eq("user_id", auth_user_id)
    .execute()
)

# ✅ Si el perfil NO existe (usuarios antiguos), lo creamos
if not perfil_res.data:
    supabase.table("perfiles").insert({
        "user_id": auth_user_id,
        "must_change_password": False  # usuarios históricos NO forzados
    }).execute()
    must_change_password = False
else:
    must_change_password = perfil_res.data[0]["must_change_password"]

# ==================================================
# OBLIGAR CAMBIO DE CONTRASEÑA SOLO SI CORRESPONDE
# ==================================================
if must_change_password:
    st.title("🔑 Primer ingreso")

    st.info(
        "Por seguridad, debés cambiar la contraseña temporal antes de continuar."
    )

    new_pass = st.text_input("Nueva contraseña", type="password")
    confirm_pass = st.text_input("Confirmar contraseña", type="password")

    if st.button("Cambiar contraseña"):
        if not new_pass or not confirm_pass:
            st.warning("Completá ambos campos")
        elif new_pass != confirm_pass:
            st.error("Las contraseñas no coinciden")
        elif len(new_pass) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres")
        else:
            try:
                supabase.auth.update_user({
                    "password": new_pass
                })

                supabase.table("perfiles").update({
                    "must_change_password": False
                }).eq("user_id", auth_user_id).execute()

                st.success("✅ Contraseña actualizada correctamente")
                st.rerun()
            except Exception as e:
                st.error("No se pudo actualizar la contraseña")
                st.exception(e)

    st.stop()

# ==================================================
# APLICACIÓN NORMAL
# ==================================================
st.title("🗺️ Sitios y análisis de suelos")
st.caption(f"Usuario: {user_email}")

if st.button("🚪 Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.session = None
    st.rerun()

# ==================================================
# SITIOS (RLS FILTRA AUTOMÁTICAMENTE)
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
def get_index_by_id(items, item_id):
    for i, s in enumerate(items):
        if s["id"] == item_id:
            return i
    return 0

index = get_index_by_id(sitios, st.session_state.sitio_id)

sitio_sel = st.selectbox(
    "📍 Seleccione un sitio",
    sitios,
    format_func=lambda s: s["codigo_sitio"],
    index=index
)

st.session_state.sitio_id = sitio_sel["id"]

# ==================================================
# MAPA
# ==================================================
lats = [s["latitud"] for s in sitios if s["latitud"] is not None]
lons = [s["longitud"] for s in sitios if s["longitud"] is not None]

m = folium.Map(tiles="OpenStreetMap")

if lats and lons:
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

for s in sitios:
    color = "red" if s["id"] == st.session_state.sitio_id else "blue"
    folium.Marker(
        location=[s["latitud"], s["longitud"]],
        tooltip=s["codigo_sitio"],
        icon=folium.Icon(color=color)
    ).add_to(m)

st_folium(m, height=500)

# ==================================================
# ANÁLISIS DEL SITIO
# ==================================================
st.subheader(f"🧪 Análisis – Sitio {sitio_sel['codigo_sitio']}")

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
# INFORME COMPLETO
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
def generar_pdf_informe(informe, titulo):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = A4[1] - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, titulo)
    y -= 30

    c.setFont("Helvetica", 10)
    for k, v in informe:
        if y < 50:
            c.showPage()
            y = A4[1] - 50
        c.drawString(50, y, f"{k}: {v}")
        y -= 14

    c.save()
    buffer.seek(0)
    return buffer

pdf_buffer = generar_pdf_informe(
    informe,
    f"Informe de análisis de suelo – {row['sitio']}"
)

st.download_button(
    "📄 Descargar informe PDF",
    pdf_buffer,
    file_name=f"informe_suelo_{row['sitio']}.pdf",
    mime="application/pdf"
)
