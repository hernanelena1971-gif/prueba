import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Prueba login", layout="centered")

# ---------- Supabase ----------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

# ---------- Session state ----------
if "session" not in st.session_state:
    st.session_state.session = None

if "user" not in st.session_state:
    st.session_state.user = None

# ---------- Helper seguro ----------
def get_auth_user_id(user):
    if isinstance(user, dict):
        return user.get("id")
    return getattr(user, "id", None)

# ---------- Login ----------
if st.session_state.session is None:
    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Entrar"):
        try:
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            st.session_state.session = res.session
            st.session_state.user = res.user
            st.rerun()
        except Exception as e:
            st.error("Login fallido")
            st.exception(e)

    st.stop()

# ---------- Usuario autenticado ----------
user = st.session_state.user
auth_user_id = get_auth_user_id(user)

if not auth_user_id:
    st.error("No se pudo obtener el usuario autenticado")
    st.stop()

st.success("Login OK ✅")
st.write("Auth user id:", auth_user_id)
st.write("Email:", user.email)

if st.button("Logout"):
    supabase.auth.sign_out()
    st.session_state.session = None
    st.session_state.user = None
    st.rerun()
