import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.orm import Session

from config import ARCA_ENABLED, ARCA_API_KEY, ARCA_ENDPOINT
from auth.auth import get_current_user, es_admin

"""
Módulo de integración con ARCA (ex AFIP).

ARCA es el organismo de recaudación y control aduanero argentino.
Este módulo permite la integración con la API de facturación electrónica.

API Reference: https://www.arca.gob.ar/desarrolladores

Para habilitar:
1. Configurar ARCA_ENABLED=true en .env
2. Obtener API Key en el portal de ARCA
3. Configurar ARCA_API_KEY en .env
"""


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown("<h1>📡 Integración ARCA</h1>", unsafe_allow_html=True)

    if not ARCA_ENABLED:
        st.warning(
            "🔌 La integración con ARCA está deshabilitada.\n\n"
            "Para habilitarla:\n"
            "1. Creá un archivo `.env` en la raíz del proyecto\n"
            "2. Agregá `ARCA_ENABLED=true`\n"
            "3. Agregá `ARCA_API_KEY=tu_api_key`\n"
            "4. Opcional: `ARCA_ENDPOINT=https://api.arca.afip.gob.ar/v1`"
        )
        if es_admin():
            with st.expander("⚙️ Configuración"):
                st.code(
                    f"""# .env
ARCA_ENABLED=true
ARCA_API_KEY=tu_api_key_aqui
ARCA_ENDPOINT={ARCA_ENDPOINT}
""",
                    language="bash",
                )
        return

    st.success("✅ Integración ARCA habilitada")

    with st.expander("📋 Estado del Servicio", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("API Key", "✅ Configurada" if ARCA_API_KEY else "❌ No configurada")
        with col2:
            st.metric("Endpoint", ARCA_ENDPOINT)
        with col3:
            st.metric("Estado", "🟢 En línea (simulado)" if ARCA_ENABLED else "🔴 Desconectado")

    if not ARCA_API_KEY:
        st.error("ARCA_API_KEY no configurada. Revisá tu archivo .env")
        return

    tab1, tab2, tab3 = st.tabs(["🧾 Facturación Electrónica", "📊 Consultas", "⚙️ Configuración"])

    with tab1:
        st.info(
            "🏗️ Esta sección permitirá emitir comprobantes electrónicos "
            "vía la API de ARCA.\n\n"
            "Funcionalidades próximas:\n"
            "- Emisión de Facturas A, B, C y E\n"
            "- Notas de crédito y débito\n"
            "- Consulta de comprobantes emitidos\n"
            "- Sincronización automática con ventas"
        )

        from database.models import Sale, TipoComprobante
        ventas_sin_facturar = (
            session.query(Sale)
            .filter(
                Sale.tenant_id == tenant_id,
                Sale.comprobante.in_([TipoComprobante.FACTURA_A, TipoComprobante.FACTURA_B, TipoComprobante.FACTURA_C]),
            )
            .count()
        )
        st.metric("Comprobantes pendientes de sincronización", ventas_sin_facturar)

    with tab2:
        st.info(
            "🏗️ Próximamente:\n"
            "- Consulta de CUIT\n"
            "- Padrón de contribuyentes\n"
            "- Alicuotas de IVA\n"
            "- Vencimientos"
        )

    with tab3:
        st.info("Configuración de parámetros de integración")

        with st.form("arca_config"):
            punto_venta = st.text_input("Punto de Venta", value="0001")
            cuit = st.text_input("CUIT", placeholder="XX-XXXXXXXX-X")
            ingresos_brutos = st.selectbox(
                "Condición IVA",
                ["Responsable Inscripto", "Monotributista", "Exento", "Consumidor Final"],
            )
            st.form_submit_button("💾 Guardar Configuración", use_container_width=True)


def sincronizar_factura(session: Session, venta_id: int) -> dict:
    """
    Envía una venta a la API de ARCA para generar el comprobante electrónico.
    """
    from database.models import Sale

    venta = session.query(Sale).filter_by(id=venta_id).first()
    if not venta:
        return {"success": False, "error": "Venta no encontrada"}

    if not ARCA_ENABLED or not ARCA_API_KEY:
        return {"success": False, "error": "ARCA no configurado"}

    payload = {
        "punto_venta": 1,
        "tipo_comprobante": venta.comprobante.value,
        "numero_comprobante": venta.numero_comprobante,
        "fecha": venta.fecha.isoformat(),
        "total": float(venta.total),
        "cliente": {
            "nombre": venta.client.nombre if venta.client else "Consumidor Final",
            "cuit": venta.client.cuit if venta.client else "",
        },
        "items": [
            {
                "descripcion": item.descripcion,
                "cantidad": float(item.cantidad),
                "precio": float(item.precio_unitario),
            }
            for item in venta.items
        ],
    }

    try:
        import requests
        response = requests.post(
            f"{ARCA_ENDPOINT}/facturas",
            json=payload,
            headers={"Authorization": f"Bearer {ARCA_API_KEY}"},
            timeout=30,
        )
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False,
                "error": f"Error ARCA: {response.status_code} - {response.text}",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
