import streamlit as st
from supabase import create_client, ClientOptions
import folium
from streamlit_folium import st_folium
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pandas as pd

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
# Supabase client (con sesión para RLS)
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
# SITIOS (RLS filtra)
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
# Selector de sitio
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
# MAPA — zoom a todos los sitios + click selecciona
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

mapa = st_folium(m, width=1200, height=550)

# Click en marcador → cambia sitio activo
if mapa and mapa.get("last_object_clicked"):
    lat = mapa["last_object_clicked"]["lat"]
    lng = mapa["last_object_clicked"]["lng"]

    for s in sitios:
        if (
            abs(s["latitud"] - lat) < 0.0001 and
            abs(s["longitud"] - lng) < 0.0001
        ):
            if st.session_state.sitio_id != s["id"]:
                st.session_state.sitio_id = s["id"]
                st.rerun()

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

#informe = [(k.replace("_"," ").title(), v) for k,v in row.items()]
#st.table([{"Parámetro": k, "Valor": v} for k,v in informe])




df_info = pd.DataFrame([
    {"Parámetro": "Usuario", "Valor": row["usuario"]},
    {"Parámetro": "Sitio", "Valor": row["sitio"]},
    {"Parámetro": "Fecha de muestreo", "Valor": row["fecha_muestreo"]},
    {"Parámetro": "Número de laboratorio", "Valor": row["numero_laboratorio"]},
    {"Parámetro": "Profundidad", "Valor": row["profundidad"]},
    {"Parámetro": "Uso actual", "Valor": row["uso_actual"]},
])

st.subheader("📋 Información general")
st.dataframe(
    df_info,
    use_container_width=True,
    hide_index=True
)

st.subheader("🧱 Textura del suelo")

df_textura = pd.DataFrame([
    {"Parámetro": "Arena (%)", "Valor": row["arena"]},
    {"Parámetro": "Limo (%)", "Valor": row["limo"]},
    {"Parámetro": "Arcilla (%)", "Valor": row["arcilla"]},
    {"Parámetro": "Clasificación textural", "Valor": row["textura"]},
])

st.dataframe(
    df_textura,
    use_container_width=True,
    hide_index=True
)

st.subheader("🧪 Propiedades químicas")

df_quimica = pd.DataFrame([
    {"Parámetro": "pH (pasta)", "Valor": row["ph"]},
    {"Parámetro": "Conductividad eléctrica", "Valor": row["conductividad"]},
    {"Parámetro": "Carbonato Ca + Mg", "Valor": row["carbonato_ca_mg"]},
])

st.dataframe(
    df_quimica,
    use_container_width=True,
    hide_index=True
)

st.subheader("🌱 Fertilidad y nutrientes")

df_fertilidad = pd.DataFrame([
    {"Parámetro": "Carbono orgánico", "Valor": row["carbono_organico"]},
    {"Parámetro": "Materia orgánica", "Valor": row["materia_organica"]},
    {"Parámetro": "Nitrógeno total", "Valor": row["nitrogeno_total"]},
    {"Parámetro": "Relación C/N", "Valor": row["relacion_cn"]},
    {"Parámetro": "Fósforo", "Valor": row["fosforo"]},
    {"Parámetro": "Potasio", "Valor": row["potasio"]},
    {"Parámetro": "Calcio", "Valor": row["calcio"]},
])

st.dataframe(
    df_fertilidad,
    use_container_width=True,
    hide_index=True
)

st.subheader("⚠️ Sales y otros parámetros")

df_sales = pd.DataFrame([
    {"Parámetro": "Sodio intercambiable", "Valor": row["sodio"]},
    {"Parámetro": "Cloruro (extracto)", "Valor": row["cloruro_extracto"]},
    {"Parámetro": "Cloruro (suelo seco)", "Valor": row["cloruro_suelo_seco"]},
    {"Parámetro": "EAS", "Valor": row["eas"]},
    {"Parámetro": "Boro", "Valor": row["boro"]},
])

st.dataframe(
    df_sales,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# INFORME PLANO SOLO PARA PDF
# --------------------------------------------------
informe = [
    ("Usuario", row["usuario"]),
    ("Sitio", row["sitio"]),
    ("Fecha de muestreo", row["fecha_muestreo"]),
    ("Número de laboratorio", row["numero_laboratorio"]),
    ("Profundidad", row["profundidad"]),
    ("Uso actual", row["uso_actual"]),
    ("Uso anterior", row["uso_anterior"]),
    ("Uso posterior", row["uso_posterior"]),
    ("Observaciones", row["observaciones"]),
    ("Arena (%)", row["arena"]),
    ("Limo (%)", row["limo"]),
    ("Arcilla (%)", row["arcilla"]),
    ("Textura", row["textura"]),
    ("pH", row["ph"]),
    ("Conductividad eléctrica", row["conductividad"]),
    ("Carbonato Ca + Mg", row["carbonato_ca_mg"]),
    ("Carbono orgánico", row["carbono_organico"]),
    ("Materia orgánica", row["materia_organica"]),
    ("Nitrógeno total", row["nitrogeno_total"]),
    ("Relación C/N", row["relacion_cn"]),
    ("Fósforo", row["fosforo"]),
    ("Sodio", row["sodio"]),
    ("Potasio", row["potasio"]),
    ("Calcio", row["calcio"]),
    ("Cloruro (extracto)", row["cloruro_extracto"]),
    ("Cloruro (suelo seco)", row["cloruro_suelo_seco"]),
    ("EAS", row["eas"]),
    ("Boro", row["boro"]),
]
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
