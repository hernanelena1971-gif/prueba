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
# UTILIDAD SEGURA PARA IMÁGENES
# ==================================================
def safe_image(path, width, min_height=40):
    if path and os.path.exists(path):
        return Image(path, width=width, kind="proportional")
    return Spacer(width, min_height)


# ==================================================
# PDF
# ==================================================
def generar_pdf_informe(row, codigo_sitio):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    elements = []

    # -------------------------
    # ENCABEZADO CON LOGOS
    # -------------------------
    logo_inta = safe_image(
        os.path.join(BASE_DIR, "logo_inta.png"),
        width=120
    )
    logo_arg = safe_image(
        os.path.join(BASE_DIR, "logo_argeninta.png"),
        width=120
    )

    header = Table(
        [[logo_inta, logo_arg]],
        colWidths=[260, 260]
    )

    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))

    elements.append(header)
    elements.append(Spacer(1, 20))

    # -------------------------
    # TÍTULO
    # -------------------------
    elements.append(
        Paragraph(
            f"<b>Informe de análisis de suelo</b><br/>Sitio: {codigo_sitio}",
            styles["Normal"]
        )
    )
    elements.append(Spacer(1, 14))

    # -------------------------
    # FUNCIÓN TABLAS
    # -------------------------
    def tabla_parametros(titulo, filas):
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>{titulo}</b>", styles["Normal"]))
        elements.append(Spacer(1, 6))

        data = [["Parámetro", "Valor"]] + filas
        t = Table(data, colWidths=[250, 200])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(t)

    # -------------------------
    # TABLAS
    # -------------------------
    tabla_parametros("Información general", [
        ["Usuario", row["usuario"]],
        ["Sitio", row["sitio"]],
        ["Fecha de muestreo", row["fecha_muestreo"]],
        ["Número de laboratorio", row["numero_laboratorio"]],
        ["Profundidad", row["profundidad"]],
        ["Uso actual", row["uso_actual"]],
    ])

    tabla_parametros("Textura del suelo", [
        ["Arena (%)", row["arena"]],
        ["Limo (%)", row["limo"]],
        ["Arcilla (%)", row["arcilla"]],
        ["Clasificación textural", row["textura"]],
    ])

    tabla_parametros("Propiedades químicas", [
        ["pH", row["ph"]],
        ["Conductividad eléctrica", row["conductividad"]],
        ["Carbonato Ca + Mg", row["carbonato_ca_mg"]],
    ])

    tabla_parametros("Fertilidad y nutrientes", [
        ["Carbono orgánico", row["carbono_organico"]],
        ["Materia orgánica", row["materia_organica"]],
        ["Nitrógeno total", row["nitrogeno_total"]],
        ["Relación C/N", row["relacion_cn"]],
        ["Fósforo", row["fosforo"]],
        ["Potasio", row["potasio"]],
        ["Calcio", row["calcio"]],
    ])

    tabla_parametros("Sales y otros parámetros", [
        ["Sodio", row["sodio"]],
        ["Cloruro (extracto)", row["cloruro_extracto"]],
        ["Cloruro (suelo seco)", row["cloruro_suelo_seco"]],
        ["EAS", row["eas"]],
        ["Boro", row["boro"]],
    ])

    elements.append(Spacer(1, 20))
    elements.append(
        Paragraph(
            "<i>Los análisis se realizan sobre muestras extraídas por el solicitante.</i>",
            styles["Normal"]
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==================================================
# STREAMLIT APP
# ==================================================
st.set_page_config(
    page_title="Suelos – Sitios y análisis",
    layout="wide"
)

# -------------------------
# SUPABASE
# -------------------------
def get_supabase_client():
    if "session" in st.session_state and st.session_state.session:
        return create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_ANON_KEY"],
            ClientOptions(
                headers={"Authorization": f"Bearer {st.session_state.session.access_token}"}
            ),
        )
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"]
    )

supabase = get_supabase_client()

# -------------------------
# SESSION STATE
# -------------------------
st.session_state.setdefault("session", None)
st.session_state.setdefault("sitio_id", None)

# -------------------------
# LOGIN
# -------------------------
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

# -------------------------
# APP PRINCIPAL
# -------------------------
st.title("🗺️ Sitios y análisis de suelos")

if st.button("🚪 Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.session = None
    st.session_state.sitio_id = None
    st.rerun()

# -------------------------
# SITIOS
# -------------------------
sitios = (
    supabase
    .table("sitios")
    .select("id,codigo_sitio,latitud,longitud")
    .execute()
).data

sitio_sel = st.selectbox(
    "📍 Seleccione un sitio",
    sitios,
    format_func=lambda s: s["codigo_sitio"]
)
st.session_state.sitio_id = sitio_sel["id"]

# -------------------------
# MAPA
# -------------------------
m = folium.Map(tiles="OpenStreetMap")
for s in sitios:
    folium.Marker(
        [s["latitud"], s["longitud"]],
        tooltip=s["codigo_sitio"]
    ).add_to(m)

st_folium(m, width=1200, height=500)

# -------------------------
# INFORME
# -------------------------
data = supabase.rpc(
    "get_informe_suelo_por_sitio",
    {"p_sitio_id": int(st.session_state.sitio_id)}
).execute().data

row = data[0]

pdf_buffer = generar_pdf_informe(
    row,
    sitio_sel["codigo_sitio"]
)

st.download_button(
    "📄 Descargar informe PDF",
    pdf_buffer,
    file_name=f"informe_{sitio_sel['codigo_sitio']}.pdf",
    mime="application/pdf",
)
