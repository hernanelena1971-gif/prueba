import streamlit as st
import psycopg2

conn = psycopg2.connect(
    host=st.secrets["DB_HOST"],
    port=st.secrets["DB_PORT"],
    dbname=st.secrets["DB_NAME"],
    user=st.secrets["DB_USER"],
    password=st.secrets["DB_PASSWORD"],
    sslmode="require",
)

cur = conn.cursor()
cur.execute("SELECT current_database(), current_user;")
db, user = cur.fetchone()

st.success("✅ Conectado a Supabase")
st.write("Base:", db)
st.write("Usuario:", user)

cur.close()
conn.close()
