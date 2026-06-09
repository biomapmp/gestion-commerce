import streamlit as st
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from database.models import CashFlow, MovimientoTipo
from utils.helpers import (
    formato_moneda, formato_fecha_corta, parse_decimal, today,
)
from utils.charts import flujo_caja_chart, grafico_torta
from auth.auth import get_current_user


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown("<h1>💰 Flujo de Caja</h1>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 Movimientos", "➕ Nuevo Movimiento"])

    with tab1:
        render_movimientos(session, tenant_id)
    with tab2:
        render_nuevo_movimiento(session, tenant_id)


def render_movimientos(session: Session, tenant_id: int):
    col1, col2 = st.columns(2)
    with col1:
        desde = st.date_input("Desde", value=today() - timedelta(days=30))
    with col2:
        hasta = st.date_input("Hasta", value=today())

    tipo_filtro = st.selectbox(
        "Filtrar por tipo",
        ["Todos", "INGRESO", "EGRESO"],
    )

    query = session.query(CashFlow).filter(
        CashFlow.tenant_id == tenant_id,
        CashFlow.fecha.between(desde, hasta),
    )

    if tipo_filtro != "Todos":
        query = query.filter(CashFlow.tipo == MovimientoTipo(tipo_filtro))

    movimientos = query.order_by(CashFlow.fecha.desc(), CashFlow.created_at.desc()).all()

    if not movimientos:
        st.info("No hay movimientos en este período")
        return

    ingresos = sum(float(m.monto) for m in movimientos if m.tipo == MovimientoTipo.INGRESO)
    egresos = sum(float(m.monto) for m in movimientos if m.tipo == MovimientoTipo.EGRESO)
    saldo = ingresos - egresos

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Ingresos", formato_moneda(ingresos))
    with col2:
        st.metric("Egresos", formato_moneda(egresos))
    with col3:
        st.metric("Saldo", formato_moneda(saldo),
                  delta=f"{'Positivo' if saldo >= 0 else 'Negativo'}")

    data = []
    for m in movimientos:
        tipo_icon = "📈" if m.tipo == MovimientoTipo.INGRESO else "📉"
        data.append({
            "Fecha": formato_fecha_corta(m.fecha),
            "Tipo": f"{tipo_icon} {m.tipo.value}",
            "Categoría": m.categoria,
            "Descripción": m.descripcion,
            "Monto": formato_moneda(m.monto),
            "Forma Pago": m.forma_pago,
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### 📊 Resumen Gráfico")

    flujo_df = pd.DataFrame([
        {"fecha": m.fecha, "monto": float(m.monto), "tipo": m.tipo.value}
        for m in movimientos
    ])

    if not flujo_df.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            cat_agg = flujo_df.groupby("tipo")["monto"].sum().reset_index()
            fig = grafico_torta(cat_agg, "monto", "tipo", "Ingresos vs Egresos")
            st.plotly_chart(fig, use_container_width=True)

        with col_g2:
            flujo_agg = flujo_df.groupby(["fecha", "tipo"])["monto"].sum().reset_index()
            fechas = sorted(flujo_df["fecha"].unique())
            ingresos_vals = [
                flujo_agg[(flujo_agg["fecha"] == f) & (flujo_agg["tipo"] == "INGRESO")]["monto"].sum()
                for f in fechas
            ]
            egresos_vals = [
                flujo_agg[(flujo_agg["fecha"] == f) & (flujo_agg["tipo"] == "EGRESO")]["monto"].sum()
                for f in fechas
            ]
            fig2 = flujo_caja_chart(ingresos_vals, egresos_vals, fechas)
            st.plotly_chart(fig2, use_container_width=True)


def render_nuevo_movimiento(session: Session, tenant_id: int):
    st.subheader("Registrar Movimiento de Caja")

    with st.form("nuevo_movimiento"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=today())
            tipo = st.selectbox("Tipo", options=[t.value for t in MovimientoTipo])
        with col2:
            monto = st.number_input("Monto ($)", min_value=0.01, format="%.2f")
            forma_pago = st.selectbox(
                "Forma de Pago",
                ["EFECTIVO", "TRANSFERENCIA", "TARJETA_CREDITO", "TARJETA_DEBITO", "MERCADO_PAGO", "CHEQUE", "OTRO"],
            )

        categorias_ingreso = ["VENTAS", "COBRANZAS", "PRESTAMOS", "APORTES", "OTROS_INGRESOS"]
        categorias_egreso = ["COMPRAS", "SUELDOS", "SERVICIOS", "ALQUILER", "IMPUESTOS", "PROVEEDORES", "OTROS_EGRESOS"]

        categorias = categorias_ingreso + categorias_egreso
        categoria = st.selectbox("Categoría", options=categorias)

        descripcion = st.text_input("Descripción *", placeholder="Describí el movimiento")

        if st.form_submit_button("💾 Registrar Movimiento", use_container_width=True):
            if not descripcion:
                st.error("La descripción es obligatoria")
            else:
                movimiento = CashFlow(
                    tenant_id=tenant_id,
                    fecha=fecha,
                    tipo=MovimientoTipo(tipo),
                    categoria=categoria,
                    descripcion=descripcion,
                    monto=parse_decimal(monto),
                    forma_pago=forma_pago,
                )
                session.add(movimiento)
                session.commit()
                st.success("✅ Movimiento registrado correctamente")
                st.rerun()
