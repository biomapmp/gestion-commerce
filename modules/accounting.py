import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.orm import Session

from database.models import AccountingEntry
from utils.helpers import formato_moneda, formato_fecha_corta, parse_decimal, today
from auth.auth import get_current_user


PLAN_CUENTAS = [
    "ACTIVO/CAJA",
    "ACTIVO/BANCOS",
    "ACTIVO/CLIENTES",
    "ACTIVO/MERCADERIAS",
    "ACTIVO/BIENES_USO",
    "PASIVO/PROVEEDORES",
    "PASIVO/IMPUESTOS",
    "PASIVO/PRESTAMOS",
    "PATRIMONIO/CAPITAL",
    "PATRIMONIO/RESULTADOS_ACUMULADOS",
    "RESULTADO/VENTAS",
    "RESULTADO/COMPRAS",
    "RESULTADO/GASTOS_ADMIN",
    "RESULTADO/GASTOS_VENTAS",
    "RESULTADO/GASTOS_FINANCIEROS",
    "RESULTADO/IMPUESTOS",
    "RESULTADO/IVA_DEBITO_FISCAL",
    "RESULTADO/IVA_CREDITO_FISCAL",
    "ORDEN/CUENTAS_ORDEN",
]


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown("<h1>📒 Contabilidad</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color: #666;'>Sistema de partida doble. "
        "Cada asiento contable registra un movimiento de Débito y un movimiento de Haber equivalentes.</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["📋 Libro Diario", "➕ Nuevo Asiento"])

    with tab1:
        render_libro_diario(session, tenant_id)
    with tab2:
        render_nuevo_asiento(session, tenant_id)


def render_libro_diario(session: Session, tenant_id: int):
    col1, col2 = st.columns(2)
    with col1:
        desde = st.date_input("Desde", value=today() - timedelta(days=30))
    with col2:
        hasta = st.date_input("Hasta", value=today())

    asientos = (
        session.query(AccountingEntry)
        .filter(
            AccountingEntry.tenant_id == tenant_id,
            AccountingEntry.fecha.between(desde, hasta),
        )
        .order_by(AccountingEntry.fecha, AccountingEntry.numero_asiento)
        .all()
    )

    total_debe = sum(float(a.debe) for a in asientos)
    total_haber = sum(float(a.haber) for a in asientos)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Débito", formato_moneda(total_debe))
    with col2:
        st.metric("Total Crédito", formato_moneda(total_haber))
    with col3:
        diferencia = total_debe - total_haber
        st.metric("Diferencia", formato_moneda(diferencia),
                  delta="✅ Cuadrado" if diferencia == 0 else "⚠️ Desbalanceado")

    if asientos:
        data = []
        for a in asientos:
            data.append({
                "Fecha": formato_fecha_corta(a.fecha),
                "N° Asiento": a.numero_asiento,
                "Cuenta": a.cuenta_contable,
                "Concepto": a.concepto,
                "Débito": formato_moneda(a.debe) if float(a.debe) > 0 else "",
                "Crédito": formato_moneda(a.haber) if float(a.haber) > 0 else "",
            })

        df = pd.DataFrame(data)

        estilo = df.style.applymap(
            lambda x: "background-color: #dcfce7" if isinstance(x, str) and "$" in x and x else "",
            subset=["Débito"],
        ).applymap(
            lambda x: "background-color: #fce7f3" if isinstance(x, str) and "$" in x and x else "",
            subset=["Crédito"],
        )

        st.dataframe(estilo, use_container_width=True, hide_index=True)

        if st.button("📥 Exportar a CSV"):
            csv = df.to_csv(index=False)
            st.download_button("Descargar CSV", csv, f"libro_diario_{desde}_{hasta}.csv", "text/csv")
    else:
        st.info("No hay asientos contables en este período")


def render_nuevo_asiento(session: Session, tenant_id: int):
    st.subheader("Nuevo Asiento Contable")

    ultimo_numero = (
        session.query(AccountingEntry)
        .filter(AccountingEntry.tenant_id == tenant_id)
        .count()
    ) + 1
    numero_asiento = f"A-{ultimo_numero:04d}"

    with st.form("nuevo_asiento"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=today())
            st.write(f"N° Asiento: **{numero_asiento}**")
        with col2:
            concepto = st.text_input("Concepto *", placeholder="Descripción del asiento")

        st.markdown("#### Líneas del Asiento")
        st.markdown("Agregá las líneas de débito y crédito (deben sumar igual)")

        lineas_count = st.number_input("Cantidad de líneas", min_value=2, max_value=20, value=2)

        total_debe = 0
        total_haber = 0
        lineas = []

        for i in range(int(lineas_count)):
            cols = st.columns([2, 1, 1])
            with cols[0]:
                cuenta = st.selectbox(
                    f"Cuenta {i+1}",
                    options=PLAN_CUENTAS,
                    key=f"cuenta_{i}",
                )
            with cols[1]:
                debe = st.number_input(f"Débito", min_value=0.0, format="%.2f", key=f"debe_{i}")
            with cols[2]:
                haber = st.number_input(f"Crédito", min_value=0.0, format="%.2f", key=f"haber_{i}")

            total_debe += debe
            total_haber += haber
            lineas.append({"cuenta": cuenta, "debe": debe, "haber": haber})

        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Débito", formato_moneda(total_debe))
        with col2:
            st.metric("Total Crédito", formato_moneda(total_haber))
        with col3:
            balance = total_debe - total_haber
            st.metric("Balance", formato_moneda(balance),
                      delta="✅" if balance == 0 else "❌")

        submitted = st.form_submit_button("💾 Registrar Asiento", use_container_width=True)

        if submitted:
            if not concepto:
                st.error("El concepto es obligatorio")
            elif total_debe != total_haber:
                st.error("❌ Los totales de Débito y Crédito no coinciden")
            elif total_debe == 0:
                st.error("Debe haber al menos un valor")
            else:
                for linea in lineas:
                    if linea["debe"] > 0 or linea["haber"] > 0:
                        asiento = AccountingEntry(
                            tenant_id=tenant_id,
                            fecha=fecha,
                            numero_asiento=numero_asiento,
                            concepto=concepto,
                            debe=parse_decimal(linea["debe"]),
                            haber=parse_decimal(linea["haber"]),
                            cuenta_contable=linea["cuenta"],
                        )
                        session.add(asiento)

                session.commit()
                st.success(f"✅ Asiento {numero_asiento} registrado correctamente")
                st.rerun()
