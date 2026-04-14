# ==================================================
# IMPORTS
# ==================================================
import os
from io import BytesIO

import streamlit as st
from supabase import create_client, ClientOptions

import folium
from streamlit_folium import st_folium

import pandas as pd

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


# ==================================================
# CONFIG STREAMLIT
# ==================================================
st.set_page_config(
    page_title="Suelos – Sitios y análisis",
    layout="wide"
)


# ==================================================
# SUPABASE
# ==================================================
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


# ==================================================
# SESSION STATE
# ==================================================
if "session" not in st.session_state:
    st.session_state.session = None

if "sitio_id" not in st.session_state:
    st.session_state.sitio_id = None


# ==================================================
# LOGIN
# ==================================================
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


# ==================================================
# APP PRINCIPAL
# ==================================================
st.title("🗺️ Sitios y análisis de suelos")

if st.button("🚪 Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.session = None
    st.session_state.sitio_id = None
    st.rerun()


# ==================================================
# SITIOS
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
# SELECTOR SITIO
# ==================================================
sitio_sel = st.selectbox(
    "📍 Seleccione un sitio",
    sitios,
    format_func=lambda s: s["codigo_sitio"]
)

st.session_state.sitio_id = sitio_sel["id"]


# ==================================================
# MAPA (ZOOM CORRECTO)
# ==================================================
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


# ==================================================
# ANÁLISIS (RPC)
# ==================================================
st.subheader(f"🧪 Análisis – Sitio {sitio_sel['codigo_sitio']}")

data = supabase.rpc(
    "get_informe_suelo_por_sitio",
    {"p_sitio_id": int(st.session_state.sitio_id)}
).execute().data

if not data:
    st.info("No hay análisis disponibles.")
    st.stop()

row = data[0]


# ==================================================
# TABLAS EN PANTALLA
# ==================================================
def mostrar_tabla(titulo, filas):
    st.subheader(titulo)
    st.dataframe(
        pd.DataFrame(filas, columns=["Parámetro", "Valor"]),
        use_container_width=True,
        hide_index=True
    )


mostrar_tabla("📋 Información general", [
    ["Usuario", row["usuario"]],
    ["Sitio", row["sitio"]],
    ["Fecha de muestreo", row["fecha_muestreo"]],
    ["Número de laboratorio", row["numero_laboratorio"]],
    ["Profundidad", row["profundidad"]],
    ["Uso actual", row["uso_actual"]],
])

mostrar_tabla("🧱 Textura del suelo", [
    ["Arena (%)", row["arena"]],
    ["Limo (%)", row["limo"]],
    ["Arcilla (%)", row["arcilla"]],
    ["Clasificación textural", row["textura"]],
])

mostrar_tabla("🧪 Propiedades químicas", [
    ["pH", row["ph"]],
    ["Conductividad eléctrica", row["conductividad"]],
    ["Carbonato Ca + Mg", row["carbonato_ca_mg"]],
])

mostrar_tabla("🌱 Fertilidad y nutrientes", [
    ["Carbono orgánico", row["carbono_organico"]],
    ["Materia orgánica", row["materia_organica"]],
    ["Nitrógeno total", row["nitrogeno_total"]],
    ["Relación C/N", row["relacion_cn"]],
    ["Fósforo", row["fosforo"]],
    ["Potasio", row["potasio"]],
    ["Calcio", row["calcio"]],
])

mostrar_tabla("⚠️ Sales y otros parámetros", [
    ["Sodio", row["sodio"]],
    ["Cloruro (extracto)", row["cloruro_extracto"]],
    ["Cloruro (suelo seco)", row["cloruro_suelo_seco"]],
    ["EAS", row["eas"]],
    ["Boro", row["boro"]],
])


# ==================================================
# PDF – FUNCIÓN ESTABLE (SIN BUGS)
# ==================================================
def generar_pdf_informe(row, codigo_sitio):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    elements = []

    # --------------------------------------------------
    # LOGOS (estable, sin bug)
    # --------------------------------------------------
    def img(path, target_width=110, min_height=45):
    if not os.path.exists(path):
        return Spacer(target_width, min_height)

    img = Image(path)
    ratio = target_width / img.imageWidth
    img.drawWidth = target_width
    img.drawHeight = img.imageHeight * ratio
    return img

    
header = Table(
    [[
        img(os.path.join(BASE_DIR, "logo_inta.png")),
        img(os.path.join(BASE_DIR, "logo_argeninta.png"))
    ]],
    colWidths=[260, 260],
    rowHeights=[70]
)


    header.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(header)
    elements.append(Spacer(1, 18))

    # --------------------------------------------------
    # TÍTULO
    # --------------------------------------------------
    elements.append(Paragraph(
        f"<b>Informe de análisis de suelo</b><br/>Sitio: {codigo_sitio}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 14))

    # --------------------------------------------------
    # FUNCIÓN TABLAS
    # --------------------------------------------------
    def tabla(titulo, filas):
        elements.append(Paragraph(f"<b>{titulo}</b>", styles["Normal"]))
        elements.append(Spacer(1, 6))

        t = Table(
            [["Parámetro", "Valor"]] + filas,
            colWidths=[260, 190]
        )
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        elements.append(t)
        elements.append(Spacer(1, 12))

    # --------------------------------------------------
    # TODAS LAS SECCIONES (COMPLETO)
    # --------------------------------------------------
    tabla("Información general", [
        ["Usuario", row["usuario"]],
        ["Sitio", row["sitio"]],
        ["Fecha de muestreo", row["fecha_muestreo"]],
        ["Número de laboratorio", row["numero_laboratorio"]],
        ["Profundidad", row["profundidad"]],
        ["Uso actual", row["uso_actual"]],
        ["Uso anterior", row.get("uso_anterior", "")],
        ["Uso posterior", row.get("uso_posterior", "")],
        ["Observaciones", row.get("observaciones", "")],
    ])

    tabla("Textura del suelo", [
        ["Arena (%)", row["arena"]],
        ["Limo (%)", row["limo"]],
        ["Arcilla (%)", row["arcilla"]],
        ["Clasificación textural", row["textura"]],
    ])

    tabla("Propiedades químicas", [
        ["pH", row["ph"]],
        ["Conductividad eléctrica", row["conductividad"]],
        ["Carbonato Ca + Mg", row["carbonato_ca_mg"]],
    ])

    tabla("Fertilidad y nutrientes", [
        ["Carbono orgánico", row["carbono_organico"]],
        ["Materia orgánica", row["materia_organica"]],
        ["Nitrógeno total", row["nitrogeno_total"]],
        ["Relación C/N", row["relacion_cn"]],
        ["Fósforo", row["fosforo"]],
        ["Potasio", row["potasio"]],
        ["Calcio", row["calcio"]],
    ])

    tabla("Sales y otros parámetros", [
        ["Sodio", row["sodio"]],
        ["Cloruro (extracto)", row["cloruro_extracto"]],
        ["Cloruro (suelo seco)", row["cloruro_suelo_seco"]],
        ["EAS", row["eas"]],
        ["Boro", row["boro"]],
    ])

    # --------------------------------------------------
    # PIE
    # --------------------------------------------------
    elements.append(Spacer(1, 18))
    elements.append(Paragraph(
        "<i>Los análisis se realizan sobre muestras extraídas por el solicitante.</i>",
        styles["Normal"]
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==================================================
# BOTÓN DESCARGA PDF
# ==================================================
pdf_buffer = generar_pdf_informe(row, sitio_sel["codigo_sitio"])

st.download_button(
    "📄 Descargar informe PDF",
    pdf_buffer,
    file_name=f"informe_{sitio_sel['codigo_sitio']}.pdf",
    mime="application/pdf"
)
