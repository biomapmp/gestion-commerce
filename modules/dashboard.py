import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.orm import Session

from database.models import Sale, CashFlow, Expense, Product, Client
from utils.helpers import (
    obtener_metricas_dashboard,
    formato_moneda,
    formato_fecha_corta,
    today,
    primer_dia_mes,
)
from utils.charts import (
    ventas_diarias_chart,
    grafico_torta,
    flujo_caja_chart,
    stock_bajo_chart,
    COLORS,
)
from auth.auth import get_current_user


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown(
        f"""
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1>📊 Dashboard</h1>
            <p style="color: #666;">Bienvenido, <strong>{user['nombre']}</strong></p>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        fecha_desde = st.date_input("Desde", value=primer_dia_mes())
    with col2:
        fecha_hasta = st.date_input("Hasta", value=today())
    with col3:
        periodo = st.selectbox(
            "Período rápido",
            ["Personalizado", "Hoy", "Esta semana", "Este mes", "Este trimestre", "Este año"],
        )

    if periodo == "Hoy":
        fecha_desde = today()
        fecha_hasta = today()
    elif periodo == "Esta semana":
        fecha_desde = today() - timedelta(days=today().weekday())
        fecha_hasta = today()
    elif periodo == "Este mes":
        fecha_desde = primer_dia_mes()
        fecha_hasta = today()
    elif periodo == "Este trimestre":
        mes_actual = today().month
        trimestre_inicio = ((mes_actual - 1) // 3) * 3 + 1
        fecha_desde = date(today().year, trimestre_inicio, 1)
        fecha_hasta = today()
    elif periodo == "Este año":
        fecha_desde = date(today().year, 1, 1)
        fecha_hasta = today()

    metrics = obtener_metricas_dashboard(session, tenant_id, fecha_desde, fecha_hasta)

    st.markdown("---")

    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        st.metric(
            "Ventas Total",
            formato_moneda(metrics["total_ventas"]),
            delta=f"{metrics['cantidad_ventas']} ventas",
        )
    with kpi_cols[1]:
        st.metric("Ingresos", formato_moneda(metrics["ingresos"]))
    with kpi_cols[2]:
        st.metric("Egresos", formato_moneda(metrics["egresos"]), delta_color="inverse")
    with kpi_cols[3]:
        st.metric("Saldo Neto", formato_moneda(metrics["saldo_neto"]))
    with kpi_cols[4]:
        st.metric("Margen Bruto", formato_moneda(metrics["margen_bruto"]))

    kpi_cols2 = st.columns(4)
    with kpi_cols2[0]:
        st.metric("Productos", metrics["total_productos"])
    with kpi_cols2[1]:
        st.metric("Clientes", metrics["total_clientes"])
    with kpi_cols2[2]:
        st.metric("Stock Bajo", metrics["productos_bajo_stock"], delta_color="inverse")
    with kpi_cols2[3]:
        st.metric("Gastos", formato_moneda(metrics["total_gastos"]))

    st.markdown("---")

    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        fig_ventas = ventas_diarias_chart(metrics["ventas_diarias"])
        st.plotly_chart(fig_ventas, use_container_width=True)

    with col_graf2:
        ventas_por_cliente = (
            session.query(
                Client.nombre,
                Sale.client_id,
            )
            .filter(
                Sale.tenant_id == tenant_id,
                Sale.fecha.between(fecha_desde, fecha_hasta),
            )
            .join(Client, Sale.client_id == Client.id, isouter=True)
            .all()
        )

        clientes_df = pd.DataFrame(
            [
                {"cliente": c.nombre if c.nombre else "Consumidor Final", "cantidad": 1}
                for c in ventas_por_cliente
            ]
        )
        if not clientes_df.empty:
            clientes_agg = clientes_df.groupby("cliente").size().reset_index(name="cantidad")
            clientes_agg = clientes_agg.sort_values("cantidad", ascending=False).head(10)
            fig_clientes = grafico_torta(
                clientes_agg, "cantidad", "cliente", "Ventas por Cliente"
            )
            st.plotly_chart(fig_clientes, use_container_width=True)
        else:
            st.info("Sin datos de clientes para el período")

    col_graf3, col_graf4 = st.columns(2)

    with col_graf3:
        flujo = (
            session.query(CashFlow)
            .filter(
                CashFlow.tenant_id == tenant_id,
                CashFlow.fecha.between(fecha_desde, fecha_hasta),
            )
            .all()
        )
        flujo_df = pd.DataFrame(
            [
                {"fecha": f.fecha, "monto": float(f.monto), "tipo": f.tipo.value}
                for f in flujo
            ]
        )
        if not flujo_df.empty:
            flujo_agg = (
                flujo_df.groupby(["fecha", "tipo"])["monto"]
                .sum()
                .reset_index()
            )
            ingresos = flujo_agg[flujo_agg["tipo"] == "INGRESO"]
            egresos = flujo_agg[flujo_agg["tipo"] == "EGRESO"]
            fechas = sorted(flujo_agg["fecha"].unique())

            ingresos_vals = [
                ingresos[ingresos["fecha"] == f]["monto"].sum() for f in fechas
            ]
            egresos_vals = [
                egresos[egresos["fecha"] == f]["monto"].sum() for f in fechas
            ]

            fig_flujo = flujo_caja_chart(ingresos_vals, egresos_vals, fechas)
            st.plotly_chart(fig_flujo, use_container_width=True)
        else:
            st.info("Sin movimientos en el período")

    with col_graf4:
        stock_bajo = (
            session.query(Product)
            .filter(
                Product.tenant_id == tenant_id,
                Product.activo == True,
                Product.stock_actual <= Product.stock_minimo,
            )
            .all()
        )
        stock_df = pd.DataFrame(
            [
                {
                    "nombre": p.nombre,
                    "stock_actual": float(p.stock_actual),
                    "stock_minimo": float(p.stock_minimo),
                }
                for p in stock_bajo
            ]
        )
        fig_stock = stock_bajo_chart(stock_df)
        st.plotly_chart(fig_stock, use_container_width=True)

    st.markdown("---")

    st.subheader("📋 Últimas Ventas")
    ultimas_ventas = (
        session.query(Sale)
        .filter(
            Sale.tenant_id == tenant_id,
            Sale.fecha.between(fecha_desde, fecha_hasta),
        )
        .order_by(Sale.created_at.desc())
        .limit(10)
        .all()
    )

    if ultimas_ventas:
        ventas_data = []
        for v in ultimas_ventas:
            ventas_data.append(
                {
                    "Fecha": formato_fecha_corta(v.fecha),
                    "Comprobante": v.comprobante.value if v.comprobante else "",
                    "Número": v.numero_comprobante,
                    "Cliente": v.client.nombre if v.client else "Consumidor Final",
                    "Total": formato_moneda(v.total),
                    "Pago": v.forma_pago,
                }
            )
        st.dataframe(pd.DataFrame(ventas_data), use_container_width=True, hide_index=True)
    else:
        st.info("No hay ventas registradas en este período")
