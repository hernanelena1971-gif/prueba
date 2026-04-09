import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Supabase API Test", layout="wide")

st.title("Prueba de conexión a Supabase (API)")

# Crear cliente Supabase usando secrets
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

# 🔁 CAMBIÁ este nombre por tu tabla real
TABLE_NAME = "mi_tabla"

try:
    response = (
        supabase
        .table(TABLE_NAME)
        .select("*")
        .limit(10)
        .execute()
    )

    st.success("✅ Conectado correctamente a Supabase API")

    if response.data:
        st.subheader(f"Datos de la tabla `{TABLE_NAME}`")
        st.dataframe(response.data)
    else:
        st.warning(
            "La tabla existe pero no hay datos "
            "o no hay permisos (revisar RLS)."
        )

except Exception as e:
    st.error("❌ Error al conectar con Supabase")
    st.code(str(e), language="text")
