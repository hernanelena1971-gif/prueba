import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="ios - Supabase API",
    layout="wide"
)

st.title("Tabla sitios (Supabase API)")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

try:
    response = (
        supabase
        .table("sitios")
        .select("*")
        .limit(20)
        .execute()
    )

    st.success("✅ Conectado a Supabase API")

    if response.data:
        st.subheader("Registros de la tabla `sitios`")
        st.dataframe(response.data)
        st.caption(f"Mostrando {len(response.data)} de 92 registros")
    else:
        st.warning("La tabla existe pero no se devolvieron datos.")

except Exception as e:
    st.error("❌ Error accediendo a la tabla `sitios`")
    st.code(str(e), language="text")
