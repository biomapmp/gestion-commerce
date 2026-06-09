import streamlit as st
import bcrypt
from sqlalchemy.orm import Session

from database.models import User, Tenant, RolUsuario
from database.connection import get_session, init_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def crear_tenant_inicial(session: Session) -> Tenant:
    tenant = session.query(Tenant).filter_by(nombre="Demo Commerce").first()
    if not tenant:
        tenant = Tenant(
            nombre="Demo Commerce",
            nombre_fantasia="Mi Comercio",
            moneda="ARS",
        )
        session.add(tenant)
        session.commit()
    return tenant


def crear_admin_inicial(session: Session, tenant: Tenant):
    admin = session.query(User).filter_by(email="admin@demo.com").first()
    if not admin:
        admin = User(
            tenant_id=tenant.id,
            nombre="Administrador",
            email="admin@demo.com",
            password_hash=hash_password("admin123"),
            rol=RolUsuario.ADMIN,
        )
        session.add(admin)
        session.commit()


def inicializar_sistema():
    init_db()
    session = get_session()
    try:
        tenant = crear_tenant_inicial(session)
        crear_admin_inicial(session, tenant)
    finally:
        session.close()


def autenticar(email: str, password: str) -> User | None:
    session = get_session()
    try:
        user = session.query(User).filter_by(email=email, activo=True).first()
        if user and verify_password(password, user.password_hash):
            return user
        return None
    finally:
        session.close()


def login_form():
    st.markdown(
        f"""
    <div style="text-align: center; padding: 2rem;">
        <h1>🏪 GestionCommerce</h1>
        <p style="color: #666;">Plataforma de gestión integral para comercios</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="admin@demo.com")
        password = st.text_input(
            "Contraseña", type="password", placeholder="admin123"
        )
        submitted = st.form_submit_button("Ingresar", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Completá todos los campos")
                return None
            user = autenticar(email, password)
            if user:
                st.session_state["user"] = {
                    "id": user.id,
                    "tenant_id": user.tenant_id,
                    "nombre": user.nombre,
                    "email": user.email,
                    "rol": user.rol.value,
                }
                st.rerun()
            else:
                st.error("Credenciales inválidas")
                return None

    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #888; font-size: 0.9em;'>"
        "Demo: admin@demo.com / admin123</p>",
        unsafe_allow_html=True,
    )

    return None


def check_auth():
    if "user" not in st.session_state:
        return False
    return True


def logout():
    st.session_state.pop("user", None)
    st.rerun()


def get_current_user():
    return st.session_state.get("user")


def es_admin():
    user = get_current_user()
    return user and user.get("rol") == RolUsuario.ADMIN.value
