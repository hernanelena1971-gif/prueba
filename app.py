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
    Paragraph, Spacer, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
 
from folium.plugins import LocateControl, Fullscreen



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
st.session_state.setdefault("session", None)
st.session_state.setdefault("sitio_id", None)


# ==================================================
# PRESENTACIÓN INSTITUCIONAL + LOGIN
# ==================================================
if st.session_state.session is None:

    # 🔹 LOGOS INSTITUCIONALES (forma CORRECTA en Streamlit)
    
    
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.image("logo_inta.png", width=95)
    
    with col_right:
        st.image("logo_argeninta.png", width=115)
    
    st.divider()



    # 🔹 PRESENTACIÓN INSTITUCIONAL
    st.html(
        """
        <style>
          .inicio-container {
            background-color: #f5f7f6;
            padding: 2.5rem 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            border-left: 6px solid #2e7d32;
          }
          .inicio-title {
            font-size: 2.1rem;
            font-weight: 700;
            color: #1b5e20;
            margin-bottom: 0.6rem;
          }
          .inicio-subtitle {
            font-size: 1.1rem;
            font-weight: 600;
            color: #2e7d32;
            margin-bottom: 0.3rem;
          }
          .inicio-text {
            font-size: 0.95rem;
            color: #333;
            margin-top: 1rem;
            line-height: 1.6;
            max-width: 900px;
          }
          .inicio-separador {
            margin: 1.5rem 0;
            border-top: 1px solid #cfcfcf;
          }
        </style>

        <div class="inicio-container">
            <div class="inicio-title">
                Sistema de Consulta de Análisis de Suelos
            </div>

            <div class="inicio-subtitle">
                Laboratorio de Suelos, Agua y Fertilizantes – LabSAF
            </div>
            <div class="inicio-subtitle">
                Grupo Recursos Naturales
            </div>
            <div class="inicio-subtitle">
                INTA – EEA Salta
            </div>

            <div class="inicio-separador"></div>

            <div class="inicio-text">
                Plataforma destinada a la consulta, visualización e interpretación de análisis de suelos,
                agua y fertilizantes realizados por el Laboratorio de Suelos, Agua y Fertilizantes (LabSAF),
                permitiendo el acceso a resultados analíticos, información geográfica de sitios de muestreo
                y documentación técnica asociada.
            </div>
        </div>
        """
    )

    # 🔹 LOGIN
    st.subheader("🔐 Acceso al sistema")
    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        try:
            res = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            st.session_state.session = res.session
            st.rerun()
        except Exception:
            st.error("Error de login")

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
# SELECTOR SITIO (SIN PISAR EL MAPA)
# ==================================================
if st.session_state.sitio_id is None:
    st.session_state.sitio_id = sitios[0]["id"]

sitio_sel = st.selectbox(
    "📍 Seleccione un sitio",
    sitios,
    format_func=lambda s: s["codigo_sitio"],
    index=next(
        i for i, s in enumerate(sitios)
        if s["id"] == st.session_state.sitio_id
    )
)

# solo actualizar si el selector cambió
if sitio_sel["id"] != st.session_state.sitio_id:
    st.session_state.sitio_id = sitio_sel["id"]
    st.rerun()

# ==================================================
# MAPA — configuracion
# ==================================================
st.markdown(
    """
    <style>
    /* Contenedor principal de Leaflet */
    .leaflet-container {
        height: 70vh !important;     /* ⬅️ ajustá: 60–80vh */
        width: 100% !important;
        min-height: 500px;           /* seguridad pantallas chicas */
        max-height: 850px;
        border-radius: 8px;
    }

    /* Mantener controles dentro del área */
    .leaflet-control {
        margin: 10px !important;
    }

    /* Selector de capas desplazable */
    .leaflet-control-layers {
        max-height: 80%;
        overflow-y: auto;
    }

    /* Atribución siempre visible */
    .leaflet-control-attribution {
        white-space: normal !important;
        font-size: 11px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ==================================================
# MAPA — zoom a todos los sitios + click selecciona
# ==================================================
mapa = None

lats = [s["latitud"] for s in sitios if s["latitud"] is not None]
lons = [s["longitud"] for s in sitios if s["longitud"] is not None]

m = folium.Map(
    location=[-24.8, -65.4],
    zoom_start=8,
    tiles=None
)

# OpenStreetMap
folium.TileLayer(
    tiles="OpenStreetMap",
    name="Mapa (OSM)",
    control=True
).add_to(m)

# Google Satélite
folium.TileLayer(
    tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr="Google",
    name="Google Satélite",
    overlay=False,
    control=True
).add_to(m)

# Botón mi ubicación
LocateControl(
    position="topleft",
    flyTo=True,
    drawMarker=True,
    drawCircle=True,
    showCompass=True,
    strings={"title": "Ir a mi ubicación"}
).add_to(m)

# Ajustar vista a todos los sitios
if lats and lons:
    m.fit_bounds([
        [min(lats), min(lons)],
        [max(lats), max(lons)]
    ])

# Marcadores
for s in sitios:
    folium.Marker(
        location=[s["latitud"], s["longitud"]],
        tooltip=s["codigo_sitio"],
        icon=folium.Icon(
            color="red" if s["id"] == st.session_state.sitio_id else "blue"
        )
    ).add_to(m)

# Selector de capas
folium.LayerControl(collapsed=False).add_to(m)

# Pantalla completa
Fullscreen(
    position="topleft",
    title="Pantalla completa",
    title_cancel="Salir de pantalla completa",
    force_separate_button=True
).add_to(m)

# ✅ RENDER DEL MAPA EN STREAMLIT (ESTO FALTABA)
mapa = st_folium(
    m,
    width=None,      # ⬅️ deja al CSS manejarlo
    height=700,      # fallback
    returned_objects=["last_object_clicked"],
    key="mapa"
)


# --------------------------------------------------
# CLICK EN MARCADOR → CAMBIA SITIO ACTIVO
# --------------------------------------------------
if mapa and mapa.get("last_object_clicked"):
    lat = mapa["last_object_clicked"]["lat"]
    lng = mapa["last_object_clicked"]["lng"]

    for s in sitios:
        if (
            s["latitud"] is not None and
            s["longitud"] is not None and
            abs(s["latitud"] - lat) < 0.0001 and
            abs(s["longitud"] - lng) < 0.0001
        ):
            if st.session_state.sitio_id != s["id"]:
                st.session_state.sitio_id = s["id"]
                st.rerun()


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
# PDF
# ==================================================
def generar_pdf_informe(row, codigo_sitio):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=90,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    elements = []

    # --------------------------------------------------
    # LOGOS (proporcionales, estables)
    # --------------------------------------------------
    def img(path, target_height=40, min_width=45):
        if not os.path.exists(path):
            return Spacer(min_width, target_height)
    
        i = Image(path)
        ratio = target_height / i.imageHeight
        i.drawHeight = target_height
        i.drawWidth = i.imageWidth * ratio
        return i
    
    # ✅ ESTO VA ACÁ DENTRO
    logo_inta = img(os.path.join(BASE_DIR, "logo_inta.png"))
    logo_arg = img(os.path.join(BASE_DIR, "logo_argeninta.png"))

    

    # ==================================================
    # HEADER + FOOTER (todas las páginas)
    # ==================================================
    def header_footer(canvas, doc):
        canvas.saveState()

        # -------------------------
        # HEADER (logos + línea)
        # -------------------------
        y = A4[1] - 50  # altura del encabezado

        if logo_inta:
            logo_inta.drawOn(canvas, 40, y)

        if logo_arg:
            logo_arg.drawOn(
                canvas,
                A4[0] - 40 - logo_arg.drawWidth,
                y
            )

        # Línea horizontal gris
        canvas.setStrokeColorRGB(0.7, 0.7, 0.7)
        canvas.setLineWidth(1)
        canvas.line(40, y - 8, A4[0] - 40, y - 8)

        # -------------------------
        # FOOTER INSTITUCIONAL
        # -------------------------
        canvas.setFont("Helvetica", 8)
        canvas.setFillColorRGB(0.4, 0.4, 0.4)

        canvas.drawString(
            40,
            45,
            "E.E.A. SALTA INTA. RN. 68 - Km 172 - C.P. 4403"
        )
        canvas.drawString(
            40,
            34,
            "Cerrillos / Salta | WhatsApp +54 9 11 6562-8753"
        )
        canvas.drawString(
            40,
            23,
            "Email: eeasalta.lab@inta.gob.ar | https://www.argentina.gob.ar/inta"
        )

        # Número de página (estilo INTA)
        canvas.drawRightString(
            A4[0] - 40,
            23,
            f"Página {doc.page}"
        )

        canvas.restoreState()


    
    # --------------------------------------------------
    # TÍTULO
    # --------------------------------------------------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "<b>Laboratorio de Suelos, Agua y Fertilizantes - LabSAF</b><br/>"
        "<b>Grupo Recursos Naturales</b>",
        styles["Title"]
    ))
    elements.append(Spacer(1, 28))
    
    elements.append(Paragraph(
        f"<b>Sitio:</b> {codigo_sitio}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 20))
    


    
    # --------------------------------------------------
    # FUNCIÓN PARA TABLAS (PDF)
    # --------------------------------------------------
    def tabla_pdf(titulo, filas):
        elements.append(Paragraph(f"<b>{titulo}</b>", styles["Normal"]))
        elements.append(Spacer(1, 6))

        t = Table(
            [["Parámetro", "Valor"]] + filas,
            colWidths=[260, 190]
        )

        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ]))

        elements.append(t)
        elements.append(Spacer(1, 12))

    # --------------------------------------------------
    # MISMAS SECCIONES QUE STREAMLIT
    # --------------------------------------------------
    tabla_pdf("Información general", [
        ["Usuario", row["usuario"]],
        ["Sitio", row["sitio"]],
        ["Fecha de muestreo", row["fecha_muestreo"]],
        ["Número de laboratorio", row["numero_laboratorio"]],
        ["Profundidad", row["profundidad"]],
        ["Uso actual", row["uso_actual"]],
    ])

    tabla_pdf("Textura del suelo", [
        ["Arena (%)", row["arena"]],
        ["Limo (%)", row["limo"]],
        ["Arcilla (%)", row["arcilla"]],
        ["Clasificación textural", row["textura"]],
    ])

    tabla_pdf("Propiedades químicas", [
        ["pH", row["ph"]],
        ["Conductividad eléctrica", row["conductividad"]],
        ["Carbonato Ca + Mg", row["carbonato_ca_mg"]],
    ])

    tabla_pdf("Fertilidad y nutrientes", [
        ["Carbono orgánico", row["carbono_organico"]],
        ["Materia orgánica", row["materia_organica"]],
        ["Nitrógeno total", row["nitrogeno_total"]],
        ["Relación C/N", row["relacion_cn"]],
        ["Fósforo", row["fosforo"]],
        ["Potasio", row["potasio"]],
        ["Calcio", row["calcio"]],
    ])
    elements.append(PageBreak())
    tabla_pdf("Sales y otros parámetros", [
        ["Sodio", row["sodio"]],
        ["Cloruro (extracto)", row["cloruro_extracto"]],
        ["Cloruro (suelo seco)", row["cloruro_suelo_seco"]],
        ["EAS", row["eas"]],
        ["Boro", row["boro"]],
    ])
# --------------------------------------------------
    # TÉCNICAS EMPLEADAS
    # --------------------------------------------------
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "<b>Técnicas empleadas</b>",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 8))

    tecnicas = [
        "Textura: Bouyoucos",
        "Materia Orgánica: micro Walkley-Black",
        "Nitrógeno total: micro Kjeldahl",
        "Fósforo \"extractable\": Bray-Kurtz Nº I (modificada)",
        "Cationes de intercambio: extracción con Acetato de Amonio 1.0 N a pH 7.0",
        "Cuantificación por Absorción Atómica",
        "<i>n.d.: no detectado</i>",
    ]

    for t in tecnicas:
        elements.append(Paragraph(f"- {t}", styles["Normal"]))
        elements.append(Spacer(1, 4))


    # --------------------------------------------------
    # ACLARACIONES
    # --------------------------------------------------
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(
        "<b>Aclaraciones</b>",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 8))

    aclaraciones = [
        "Los análisis se realizan sobre muestras extraídas por el solicitante.",
        "Las muestras permanecerán almacenadas por 3 meses; transcurrido este período, "
        "el Laboratorio no se responsabiliza por el destino de las mismas.",
        "Las determinaciones de Ca y Mg \"intercambiable\" no se realizan en muestras que "
        "contienen Carbonato de Ca y Mg.",
    ]

    for a in aclaraciones:
        elements.append(Paragraph(f"- {a}", styles["Normal"]))
        elements.append(Spacer(1, 4))


    # --------------------------------------------------
    # BUILD FINAL
    # --------------------------------------------------
    doc.build(
        elements,
        onFirstPage=header_footer,
        onLaterPages=header_footer
    )

    buffer.seek(0)
    return buffer

# ==================================================
# BOTÓN PDF
# ==================================================
pdf_buffer = generar_pdf_informe(row, sitio_sel["codigo_sitio"])

st.download_button(
    "📄 Descargar informe PDF",
    pdf_buffer,
    file_name=f"informe_{sitio_sel['codigo_sitio']}.pdf",
    mime="application/pdf"
)
