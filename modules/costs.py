import streamlit as st
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from database.models import Expense
from utils.helpers import (
    formato_moneda, formato_fecha_corta, parse_decimal, today,
)
from utils.charts import grafico_torta, COLORS
from auth.auth import get_current_user


CATEGORIAS_GASTOS = [
    "ALQUILER",
    "SERVICIOS",
    "SUELDOS",
    "CARGAS_SOCIALES",
    "IMPUESTOS",
    "PROVEEDORES",
    "LOGISTICA",
    "MARKETING",
    "MANTENIMIENTO",
    "SEGUROS",
    "HONORARIOS",
    "INSUMOS",
    "VIATICOS",
    "OTROS",
]


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown("<h1>💸 Costos y Gastos</h1>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 Historial de Gastos", "➕ Nuevo Gasto"])

    with tab1:
        render_historial(session, tenant_id)
    with tab2:
        render_nuevo_gasto(session, tenant_id)


def render_historial(session: Session, tenant_id: int):
    col1, col2 = st.columns(2)
    with col1:
        desde = st.date_input("Desde", value=today() - timedelta(days=30))
    with col2:
        hasta = st.date_input("Hasta", value=today())

    gastos = (
        session.query(Expense)
        .filter(
            Expense.tenant_id == tenant_id,
            Expense.fecha.between(desde, hasta),
        )
        .order_by(Expense.fecha.desc())
        .all()
    )

    total_gastos = sum(float(g.monto_total) for g in gastos)
    total_iva = sum(float(g.iva) for g in gastos)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Gastos", formato_moneda(total_gastos))
    with col2:
        st.metric("IVA", formato_moneda(total_iva))
    with col3:
        st.metric("Cantidad", len(gastos))

    if gastos:
        data = []
        for g in gastos:
            data.append({
                "Fecha": formato_fecha_corta(g.fecha),
                "Categoría": g.categoria,
                "Descripción": g.descripcion,
                "Proveedor": g.proveedor,
                "Neto": formato_moneda(g.monto),
                "IVA": formato_moneda(g.iva),
                "Total": formato_moneda(g.monto_total),
                "Pago": g.forma_pago,
                "Período": g.periodicidad,
            })

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### 📊 Análisis de Gastos")

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            cat_agg = df.groupby("Categoría")["Total"].apply(
                lambda x: sum(float(v.replace("$ ", "").replace(",", "")) for v in x)
            ).reset_index()
            cat_agg.columns = ["Categoría", "Total"]
            fig = grafico_torta(cat_agg, "Total", "Categoría", "Gastos por Categoría")
            st.plotly_chart(fig, use_container_width=True)

        with col_g2:
            gastos_df = pd.DataFrame([
                {"fecha": g.fecha, "total": float(g.monto_total), "categoria": g.categoria}
                for g in gastos
            ])
            diario = gastos_df.groupby("fecha")["total"].sum().reset_index()
            fig2 = st.dataframe(
                diario.sort_values("fecha", ascending=False),
                use_container_width=True,
                hide_index=True,
            )

        if st.button("📥 Exportar Gastos a CSV"):
            csv = df.to_csv(index=False)
            st.download_button(
                "Descargar CSV",
                csv,
                f"gastos_{desde}_{hasta}.csv",
                "text/csv",
            )
    else:
        st.info("No hay gastos registrados en este período")


def render_nuevo_gasto(session: Session, tenant_id: int):
    st.subheader("Registrar Nuevo Gasto")

    with st.form("nuevo_gasto"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=today())
            categoria = st.selectbox("Categoría", options=CATEGORIAS_GASTOS)
            proveedor = st.text_input("Proveedor", placeholder="Nombre del proveedor")
        with col2:
            monto_neto = st.number_input("Monto Neto ($)", min_value=0.01, format="%.2f")
            iva_tasa = st.selectbox("IVA (%)", options=[0, 10.5, 21, 27], index=2)
            forma_pago = st.selectbox(
                "Forma de Pago",
                ["EFECTIVO", "TRANSFERENCIA", "TARJETA_CREDITO", "TARJETA_DEBITO", "CHEQUE", "CUENTA_CORRIENTE", "OTRO"],
            )

        iva_calculado = monto_neto * (float(iva_tasa) / 100)
        monto_total = monto_neto + iva_calculado

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Neto", formato_moneda(monto_neto))
        with col2:
            st.metric(f"IVA ({iva_tasa}%)", formato_moneda(iva_calculado))
        with col3:
            st.metric("Total", formato_moneda(monto_total))

        descripcion = st.text_input("Descripción *", placeholder="Detalle del gasto")
        comprobante = st.text_input("N° Comprobante", placeholder="Opcional")
        periodicidad = st.selectbox(
            "Periodicidad",
            ["UNICO", "MENSUAL", "BIMESTRAL", "TRIMESTRAL", "SEMESTRAL", "ANUAL"],
        )
        notas = st.text_area("Notas adicionales")

        if st.form_submit_button("💾 Registrar Gasto", use_container_width=True):
            if not descripcion:
                st.error("La descripción es obligatoria")
            else:
                gasto = Expense(
                    tenant_id=tenant_id,
                    fecha=fecha,
                    categoria=categoria,
                    descripcion=descripcion,
                    proveedor=proveedor,
                    monto=parse_decimal(monto_neto),
                    iva=parse_decimal(iva_calculado),
                    monto_total=parse_decimal(monto_total),
                    forma_pago=forma_pago,
                    comprobante=comprobante,
                    periodicidad=periodicidad,
                    notas=notas,
                )
                session.add(gasto)

                from database.models import CashFlow, MovimientoTipo
                flujo = CashFlow(
                    tenant_id=tenant_id,
                    fecha=fecha,
                    tipo=MovimientoTipo.EGRESO,
                    categoria=f"GASTOS_{categoria}",
                    descripcion=f"Gasto: {descripcion}",
                    monto=parse_decimal(monto_total),
                    forma_pago=forma_pago,
                )
                session.add(flujo)

                session.commit()
                st.success("✅ Gasto registrado correctamente")
                st.rerun()
