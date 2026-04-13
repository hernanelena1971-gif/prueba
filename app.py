import streamlit as st
from supabase import create_client
import folium
from streamlit_folium import st_folium
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from streamlit.components.v1 import html

# ==================================================
# CONFIGURACIÓN GENERAL
# ==================================================
st.set_page_config(
    page_title="Suelos – Sitios y análisis",
    layout="wide"
)

# ==================================================
# SUPABASE
# ==================================================
def get_supabase_client():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"]
    )

supabase = get_supabase_client()

# ==================================================
# ESTADO DE SESIÓN
# ==================================================
if "session" not in st.session_state:
    st.session_state.session = None

if "sitio_id" not in st.session_state:
    st.session_state.sitio_id = None

if "supabase_tokens" not in st.session_state:
    st.session_state.supabase_tokens = None

# ==================================================
# CAPTURAR TOKENS DESDE URL (#hash) CON JS
# ==================================================
html(
    """
    <script>
    (function() {
        const hash = window.location.hash.substring(1);
        if (!hash) return;

        const params = new URLSearchParams(hash);
        const data = {};
        for (const [k, v] of params.entries()) {
            data[k] = v;
        }

        window.parent.postMessage(
            { type: "SUPABASE_AUTH", payload: data },
            "*"
        );
    })();
    </script>
    """,
    height=0
)

# ==================================================
# LEER TOKENS CAPTURADOS Y CREAR SESIÓN
# ==================================================
def handle_magic_link_login():
    tokens = st.session_state.get("supabase_tokens")
    if not tokens:
        return

    if "access_token" in tokens:
        supabase.auth.set_session(
            tokens["access_token"],
            tokens.get("refresh_token")
        )
        st.session_state.session = supabase.auth.get_session()
        st.session_state.supabase_tokens = None
        st.rerun()

handle_magic_link_login()

# ==================================================
# LOGIN CON MAGIC LINK
# ==================================================
session = supabase.auth.get_session()
if session and session.user:
    st.session_state.session = session
else:
    st.session_state.session = None

if st.session_state.session is None:
    st.title("🔐 Acceso a resultados de análisis")

    email = st.text_input("Email")

    if st.button("📨 Enviar link de acceso"):
        if not email:
            st.warning("Ingresá tu email")
        else:
            try:
                supabase.auth.sign_in_with_otp(
                    {
                        "email": email,
                        "options": {
                            "emailRedirectTo": "https://supabasesuelos.streamlit.app"
                        }
                    }
                )
                st.success(
                    "✅ Te enviamos un mail con el link de acceso.\n\n"
                    "Abrí tu correo y hacé click en el link para ingresar."
                )
            except Exception as e:
                st.error("No se pudo enviar el link de acceso")
                st.exception(e)

    st.stop()

# ==================================================
# USUARIO AUTENTICADO
# ==================================================
user = supabase.auth.get_user()

st.title("🗺️ Sitios y análisis de suelos")
st.caption(f"Usuario autenticado: {user.user.email}")

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
if st.session_state.sitio_id is None:
    st.info("Seleccioná un sitio para ver el análisis.")
    st.stop()

st.subheader(f"🧪 Análisis – Sitio {sitio_sel['codigo_sitio']}")

try:
    data = (
        supabase
        .rpc(
            "get_informe_suelo_por_sitio",
            {"p_sitio_id": int(st.session_state.sitio_id)}
        )
        .execute()
    ).data
except Exception as e:
    st.error("❌ Error ejecutando el informe")
    st.code(str(e))
    st.stop()

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
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, titulo)
    y -= 30

    c.setFont("Helvetica", 10)
    for k, v in informe:
        if y < 50:
            c.showPage()
            y = height - 50
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
