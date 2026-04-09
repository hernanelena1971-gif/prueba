import streamlit as st
from supabase import create_client
import json

st.set_page_config(page_title="Supabase GIS API", layout="wide")

st.title("Supabase + GIS (API)")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

# 🔁 CAMBIAR por tu tabla GIS real
TABLE_NAME = "parcelas"

try:
    response = (
        supabase
        .table(TABLE_NAME)
        .select("id, geom")
        .limit(5)
        .execute()
    )

    st.success("✅ Conectado a Supabase API")

    if response.data:
        st.subheader("Datos GeoJSON")
        st.json(response.data)

        # Ejemplo: exportar a archivo GeoJSON
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": row["geom"],
                    "properties": {
                        "id": row["id"]
                    },
                }
                for row in response.data
                if row["geom"] is not None
            ],
        }

        st.download_button(
            "⬇️ Descargar GeoJSON",
            json.dumps(geojson),
            file_name="datos.geojson",
            mime="application/geo+json",
        )

    else:
        st.warning("No hay datos o falta policy RLS")

except Exception as e:
    st.error("❌ Error")
    st.code(str(e))
