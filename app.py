import streamlit as st

st.set_page_config(
    page_title="GestionCommerce",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .stApp {
        background-color: #f8fafc;
    }
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e293b;
    }
    .card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
    }
    .metric-card {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 0.9rem !important;
    }
    .st-emotion-cache-1wivap2 {
        background-color: white;
        border-right: 1px solid #e2e8f0;
    }
    .stSidebar .sidebar-content {
        background-color: #ffffff;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #f1f5f9;
        border-radius: 8px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stDataFrame {
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    .sidebar-logo {
        text-align: center;
        padding: 1rem 0;
    }
    .sidebar-logo h2 {
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0.5rem 0 0 0;
    }
    .sidebar-logo p {
        color: #94a3b8;
        font-size: 0.85rem;
        margin: 0;
    }
    .user-info {
        padding: 1rem;
        background: #f8fafc;
        border-radius: 8px;
        margin: 1rem 0;
    }
    hr {
        border-color: #e2e8f0;
        margin: 1.5rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

from database.connection import get_session, init_db
from auth.auth import inicializar_sistema, login_form, check_auth, logout, get_current_user, es_admin


inicializar_sistema()

NAV_ITEMS = {
    "📊 Dashboard": "dashboard",
    "👥 Clientes": "clients",
    "📦 Stock": "stock",
    "🧾 Ventas": "sales",
    "💰 Flujo de Caja": "cashflow",
    "💸 Costos": "costs",
    "📒 Contabilidad": "accounting",
    "🛒 Tiendanube": "tiendanube",
    "📡 ARCA": "arca",
}

NAV_ICONS = {
    "dashboard": "📊",
    "clients": "👥",
    "stock": "📦",
    "sales": "🧾",
    "cashflow": "💰",
    "costs": "💸",
    "accounting": "📒",
    "tiendanube": "🛒",
    "arca": "📡",
}


def render_sidebar():
    with st.sidebar:
        st.markdown(
            """
        <div class="sidebar-logo">
            <h2>🏪 GestionCommerce</h2>
            <p>Gestión Integral</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        user = get_current_user()
        if user:
            st.markdown(
                f"""
            <div class="user-info">
                <strong>👤 {user['nombre']}</strong><br>
                <span style="color: #64748b; font-size: 0.85rem;">
                    {user['email']}<br>
                    Rol: {'🛡️ Admin' if user['rol'] == 'ADMIN' else '👤 Usuario'}
                </span>
            </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown("### Navegación")

        current_page = st.session_state.get("page", "dashboard")

        for label, page_id in NAV_ITEMS.items():
            icon = NAV_ICONS[page_id]
            btn_type = "primary" if current_page == page_id else "secondary"
            if st.button(
                f"{icon} {label.split(' ', 1)[1] if ' ' in label else label}",
                key=f"nav_{page_id}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state["page"] = page_id
                st.rerun()

        st.markdown("---")

        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            logout()


def main():
    if "page" not in st.session_state:
        st.session_state["page"] = "dashboard"

    if not check_auth():
        login_form()
        return

    render_sidebar()

    from database.connection import get_session
    session = get_session()

    try:
        page = st.session_state.get("page", "dashboard")

        if page == "dashboard":
            from modules.dashboard import render as render_dashboard
            render_dashboard(session)
        elif page == "clients":
            from modules.clients import render as render_clients
            render_clients(session)
        elif page == "stock":
            from modules.stock import render as render_stock
            render_stock(session)
        elif page == "sales":
            from modules.sales import render as render_sales
            render_sales(session)
        elif page == "cashflow":
            from modules.cashflow import render as render_cashflow
            render_cashflow(session)
        elif page == "costs":
            from modules.costs import render as render_costs
            render_costs(session)
        elif page == "accounting":
            from modules.accounting import render as render_accounting
            render_accounting(session)
        elif page == "tiendanube":
            from modules.tiendanube import render as render_tiendanube
            render_tiendanube(session)
        elif page == "arca":
            from modules.arca import render as render_arca
            render_arca(session)
    finally:
        session.close()

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #94a3b8; font-size: 0.8rem; padding: 1rem;'>"
        "🏪 GestionCommerce &copy; 2024 | Built with Streamlit | "
        "<a href='https://huggingface.co/spaces' target='_blank' style='color: #94a3b8;'>Hugging Face Spaces</a>"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
