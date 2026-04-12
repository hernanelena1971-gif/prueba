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
# RECOVERY PASSWORD DESDE LINK DE MAIL
# --------------------------------------------------
params = st.query_params

if params.get("type") == "recovery":
    st.title("🔐 Crear nueva contraseña")

    st.info(
        "Validamos tu identidad. Ahora elegí una nueva contraseña "
        "para acceder al sistema."
    )

    pw1 = st.text_input("Nueva contraseña", type="password")
    pw2 = st.text_input("Confirmar contraseña", type="password")

    if st.button("Guardar contraseña"):
        if not pw1 or not pw2:
            st.error("Completá ambos campos")
        elif pw1 != pw2:
            st.error("Las contraseñas no coinciden")
        elif len(pw1) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres")
        else:
            try:
                # ✅ Supabase ya tiene sesión por el token del link
                supabase.auth.update_user({"password": pw1})

                # ✅ Marcamos onboarding completo
                user = supabase.auth.get_user()
                supabase.table("perfiles").update({
                    "password_set": True
                }).eq("user_id", user.user.id).execute()

                st.success("✅ Contraseña creada correctamente")
                st.caption("Ya podés ingresar con tu email y contraseña")
                st.session_state.session = None
                st.rerun()

            except Exception as e:
                st.error("No se pudo actualizar la contraseña")
                st.code(str(e))

    st.stop()



# --------------------------------------------------
# LOGIN
# --------------------------------------------------
if st.session_state.session is None:
    st.title("🔐 Acceso al sistema")

    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Ingresar"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state.session = res.session
                st.success("Ingreso correcto")
                st.rerun()
            except Exception:
                st.error("Email o contraseña incorrectos")

    with col2:
        if st.button("¿Primer acceso / Olvidaste la contraseña?"):
            if not email:
                st.warning("Ingresá tu email primero")
            else:
                try:
                    supabase.auth.reset_password_email(email)
                    st.success(
                        "📧 Te enviamos un mail para crear o cambiar tu contraseña"
                    )
                except Exception as e:
                    st.error("No se pudo enviar el email")
                    st.code(str(e))

    st.stop()

# --------------------------------------------------
# USUARIO AUTENTICADO
# --------------------------------------------------
if "sitio_id" not in st.session_state:
    st.session_state.sitio_id = None
    
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
    format_func=lambda s: s["codigo_sitio"],
    index=0 if st.session_state.sitio_id is None else
    next(i for i, s in enumerate(sitios) if s["id"] == st.session_state.sitio_id)
)

st.session_state.sitio_id = sitio_sel["id"]


# --------------------------------------------------
# MAPA (siempre visible)
# --------------------------------------------------

lats = [s["latitud"] for s in sitios if s["latitud"] is not None]
lons = [s["longitud"] for s in sitios if s["longitud"] is not None]

bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]

m = folium.Map(tiles="OpenStreetMap")
m.fit_bounds(bounds)

# Recentrar si hay sitio seleccionado
if st.session_state.sitio_id is not None:
    sitio_activo = next(
        s for s in sitios if s["id"] == st.session_state.sitio_id
    )
    m.location = [sitio_activo["latitud"], sitio_activo["longitud"]]
    m.zoom_start = 14

for s in sitios:
    color = "red" if s["id"] == st.session_state.sitio_id else "blue"

    folium.Marker(
        location=[s["latitud"], s["longitud"]],
        popup=f"<b>{s['codigo_sitio']}</b>",
        tooltip=s["codigo_sitio"],
        icon=folium.Icon(color=color, icon="info-sign")
    ).add_to(m)

mapa = st_folium(m, width=1200, height=550)
# --------------------------------------
# Detectar clic en marcador y actualizar sitio
# --------------------------------------
if mapa and mapa.get("last_object_clicked"):
    lat = mapa["last_object_clicked"]["lat"]
    lng = mapa["last_object_clicked"]["lng"]

    for s in sitios:
        if abs(s["latitud"] - lat) < 0.0001 and abs(s["longitud"] - lng) < 0.0001:
            if st.session_state.sitio_id != s["id"]:
                st.session_state.sitio_id = s["id"]
                st.rerun()



# --------------------------------------------------
# ANALISIS DEL SITIO SELECCIONADO
# --------------------------------------------------

# ✅ GUARD: si todavía no hay sitio elegido
if st.session_state.sitio_id is None:
    st.info("Seleccioná un sitio en el mapa para ver el análisis.")
    st.stop()

# ✅ ACÁ VA sitio_activo (ESTE es el lugar correcto)
sitio_activo = next(
    s for s in sitios if s["id"] == st.session_state.sitio_id
)

# ✅ A PARTIR DE ACÁ usás sitio_activo
st.subheader(f"🧪 Análisis – Sitio {sitio_activo['codigo_sitio']}")

# ✅ RPC (no cambia)
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
