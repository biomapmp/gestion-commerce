import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.orm import Session

from database.models import (
    Sale, SaleItem, Client, Product, StockMovement,
    TipoMovimientoStock, TipoComprobante, CashFlow, MovimientoTipo,
)
from utils.helpers import (
    formato_moneda, formato_fecha_corta, parse_decimal,
    calcular_iva, generar_numero_comprobante, today,
)
from utils.charts import ventas_diarias_chart, grafico_torta
from auth.auth import get_current_user


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown("<h1>🧾 Ventas</h1>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📋 Historial", "➕ Nueva Venta", "📊 Reportes"])

    with tab1:
        render_historial(session, tenant_id)
    with tab2:
        render_nueva_venta(session, tenant_id)
    with tab3:
        render_reportes(session, tenant_id)


def render_historial(session: Session, tenant_id: int):
    col1, col2 = st.columns(2)
    with col1:
        desde = st.date_input("Desde", value=today() - timedelta(days=30))
    with col2:
        hasta = st.date_input("Hasta", value=today())

    ventas = (
        session.query(Sale)
        .filter(
            Sale.tenant_id == tenant_id,
            Sale.fecha.between(desde, hasta),
        )
        .order_by(Sale.fecha.desc(), Sale.created_at.desc())
        .all()
    )

    if not ventas:
        st.info("No hay ventas en este período")
        return

    total_periodo = sum(float(v.total) for v in ventas)
    st.metric("Total del Período", formato_moneda(total_periodo), f"{len(ventas)} ventas")

    data = []
    for v in ventas:
        data.append({
            "ID": v.id,
            "Fecha": formato_fecha_corta(v.fecha),
            "Comprobante": v.comprobante.value if v.comprobante else "",
            "Número": v.numero_comprobante,
            "Cliente": v.client.nombre if v.client else "Consumidor Final",
            "Items": sum(float(i.cantidad) for i in v.items),
            "Subtotal": formato_moneda(v.subtotal),
            "Descuento": formato_moneda(v.descuento),
            "IVA": formato_moneda(v.iva),
            "Total": formato_moneda(v.total),
            "Pago": v.forma_pago,
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### 👁️ Ver Detalle de Venta")
    venta_dict = {f"#{v.id} - {formato_fecha_corta(v.fecha)} - {v.client.nombre if v.client else 'Consumidor Final'} - {formato_moneda(v.total)}": v.id for v in ventas}
    selected = st.selectbox("Seleccionar venta", options=list(venta_dict.keys()))

    if selected:
        vid = venta_dict[selected]
        venta = session.query(Sale).filter_by(id=vid, tenant_id=tenant_id).first()
        if venta:
            with st.expander(f"Venta #{venta.id}", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Fecha:** {formato_fecha_corta(venta.fecha)}")
                    st.write(f"**Comprobante:** {venta.comprobante.value}")
                with col2:
                    st.write(f"**Cliente:** {venta.client.nombre if venta.client else 'Consumidor Final'}")
                    st.write(f"**Forma de Pago:** {venta.forma_pago}")
                with col3:
                    st.write(f"**Total:** {formato_moneda(venta.total)}")
                    st.write(f"**N° Comprobante:** {venta.numero_comprobante}")

                st.write("**Items:**")
                items_data = [
                    {
                        "Descripción": i.descripcion,
                        "Cantidad": float(i.cantidad),
                        "P. Unitario": formato_moneda(i.precio_unitario),
                        "Subtotal": formato_moneda(i.subtotal),
                    }
                    for i in venta.items
                ]
                st.dataframe(pd.DataFrame(items_data), use_container_width=True, hide_index=True)


def render_nueva_venta(session: Session, tenant_id: int):
    clientes = session.query(Client).filter(Client.tenant_id == tenant_id).order_by(Client.nombre).all()
    productos = session.query(Product).filter(Product.tenant_id == tenant_id, Product.activo == True).all()

    st.subheader("Registrar Nueva Venta")

    with st.form("nueva_venta"):
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha = st.date_input("Fecha", value=today())
            cliente_id = st.selectbox(
                "Cliente",
                options=[None] + [c.id for c in clientes],
                format_func=lambda x: "Consumidor Final" if x is None else next(
                    (c.nombre for c in clientes if c.id == x), ""
                ),
            )
        with col2:
            comprobante = st.selectbox(
                "Tipo Comprobante",
                options=[t.value for t in TipoComprobante],
                index=3,
            )
            forma_pago = st.selectbox(
                "Forma de Pago",
                ["EFECTIVO", "TRANSFERENCIA", "TARJETA_CREDITO", "TARJETA_DEBITO", "MERCADO_PAGO", "CUENTA_CORRIENTE", "OTRO"],
            )
        with col3:
            descuento = st.number_input("Descuento ($)", min_value=0.0, format="%.2f")
            iva_tasa = st.selectbox("IVA (%)", options=[0, 10.5, 21, 27], index=2)

        st.markdown("#### Items de la Venta")
        items_count = st.number_input("Cantidad de productos diferentes", min_value=1, max_value=20, value=1)

        items_data = []
        for i in range(int(items_count)):
            cols = st.columns([3, 1, 1, 1])
            with cols[0]:
                prod = st.selectbox(
                    f"Producto {i+1}",
                    options=[None] + [p.id for p in productos],
                    format_func=lambda x: "Seleccionar..." if x is None else next(
                        (f"{p.nombre} (${float(p.precio_venta):.2f})" for p in productos if p.id == x), ""
                    ),
                    key=f"prod_{i}",
                )
            with cols[1]:
                cantidad = st.number_input(f"Cantidad", min_value=0.01, value=1.0, format="%.2f", key=f"cant_{i}")
            with cols[2]:
                precio = st.number_input(f"Precio Unit.", min_value=0.0, format="%.2f", key=f"precio_{i}",
                                         value=float(next((p.precio_venta for p in productos if p.id == prod), 0)) if prod else 0.0)
            with cols[3]:
                if prod and precio:
                    st.metric("Subtotal", f"${float(cantidad) * float(precio):.2f}")

            items_data.append({"product_id": prod, "cantidad": cantidad, "precio": precio})

        observaciones = st.text_area("Observaciones")

        items_validos = [it for it in items_data if it["product_id"] and it["cantidad"] > 0]
        if items_validos:
            subtotal_calculado = sum(
                float(it["cantidad"]) * float(it["precio"]) for it in items_validos
            )
            descuento_val = float(descuento)
            base_imponible = subtotal_calculado - descuento_val
            iva_val = base_imponible * (float(iva_tasa) / 100)
            total_calculado = base_imponible + iva_val

            st.markdown("---")
            resumen_cols = st.columns(4)
            with resumen_cols[0]:
                st.metric("Subtotal", formato_moneda(subtotal_calculado))
            with resumen_cols[1]:
                st.metric("Descuento", formato_moneda(descuento_val))
            with resumen_cols[2]:
                st.metric(f"IVA ({iva_tasa}%)", formato_moneda(iva_val))
            with resumen_cols[3]:
                st.metric("TOTAL", formato_moneda(total_calculado))

        if st.form_submit_button("💾 Registrar Venta", use_container_width=True):
            if not items_validos:
                st.error("Agregá al menos un producto a la venta")
            else:
                ultimo_numero = session.query(Sale).filter(
                    Sale.tenant_id == tenant_id,
                    Sale.comprobante == comprobante,
                ).count() + 1

                venta = Sale(
                    tenant_id=tenant_id,
                    client_id=cliente_id,
                    fecha=fecha,
                    comprobante=TipoComprobante(comprobante),
                    numero_comprobante=generar_numero_comprobante(comprobante, ultimo_numero),
                    subtotal=parse_decimal(subtotal_calculado),
                    descuento=parse_decimal(descuento_val),
                    iva=parse_decimal(iva_val),
                    total=parse_decimal(total_calculado),
                    forma_pago=forma_pago,
                    observaciones=observaciones,
                )
                session.add(venta)
                session.flush()

                for it in items_validos:
                    producto = session.query(Product).filter_by(id=it["product_id"]).first()
                    subtotal_item = float(it["cantidad"]) * float(it["precio"])
                    item = SaleItem(
                        sale_id=venta.id,
                        product_id=it["product_id"],
                        descripcion=producto.nombre if producto else f"Item #{it['product_id']}",
                        cantidad=parse_decimal(it["cantidad"]),
                        precio_unitario=parse_decimal(it["precio"]),
                        subtotal=parse_decimal(subtotal_item),
                    )
                    session.add(item)

                    if producto:
                        nuevo_stock = float(producto.stock_actual) - float(it["cantidad"])
                        movimiento = StockMovement(
                            product_id=producto.id,
                            tipo=TipoMovimientoStock.SALIDA,
                            cantidad=parse_decimal(it["cantidad"]),
                            stock_resultante=parse_decimal(max(0, nuevo_stock)),
                            motivo=f"Venta #{venta.id}",
                            referencia_id=venta.id,
                        )
                        session.add(movimiento)
                        producto.stock_actual = parse_decimal(max(0, nuevo_stock))

                flujo = CashFlow(
                    tenant_id=tenant_id,
                    fecha=fecha,
                    tipo=MovimientoTipo.INGRESO,
                    categoria="VENTAS",
                    descripcion=f"Venta #{venta.id} - {comprobante}",
                    monto=parse_decimal(total_calculado),
                    forma_pago=forma_pago,
                    referencia_id=venta.id,
                    referencia_tipo="VENTA",
                )
                session.add(flujo)

                session.commit()
                st.success(f"✅ Venta registrada correctamente. Total: {formato_moneda(total_calculado)}")
                st.rerun()


def render_reportes(session: Session, tenant_id: int):
    st.subheader("📊 Reportes de Ventas")

    col1, col2 = st.columns(2)
    with col1:
        reporte_desde = st.date_input("Desde", value=today() - timedelta(days=30), key="reporte_desde")
    with col2:
        reporte_hasta = st.date_input("Hasta", value=today(), key="reporte_hasta")

    ventas = (
        session.query(Sale)
        .filter(
            Sale.tenant_id == tenant_id,
            Sale.fecha.between(reporte_desde, reporte_hasta),
        )
        .all()
    )

    if not ventas:
        st.info("Sin datos para el período")
        return

    df = pd.DataFrame([
        {"fecha": v.fecha, "total": float(v.total), "cliente": v.client.nombre if v.client else "Consumidor Final",
         "forma_pago": v.forma_pago, "comprobante": v.comprobante.value}
        for v in ventas
    ])

    total = df["total"].sum()
    promedio = df["total"].mean()
    max_venta = df["total"].max()
    cantidad = len(df)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Ventas", formato_moneda(total))
    with col2:
        st.metric("Promedio", formato_moneda(promedio))
    with col3:
        st.metric("Venta Máxima", formato_moneda(max_venta))
    with col4:
        st.metric("Cantidad", cantidad)

    ventas_diarias = df.groupby("fecha")["total"].sum().reset_index()
    fig_ventas = ventas_diarias_chart(ventas_diarias, "Ventas del Período")
    st.plotly_chart(fig_ventas, use_container_width=True)

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        pago_agg = df.groupby("forma_pago")["total"].sum().reset_index()
        fig_pago = grafico_torta(pago_agg, "total", "forma_pago", "Ventas por Forma de Pago")
        st.plotly_chart(fig_pago, use_container_width=True)

    with col_p2:
        comp_agg = df.groupby("comprobante")["total"].sum().reset_index()
        fig_comp = grafico_torta(comp_agg, "total", "comprobante", "Ventas por Tipo Comprobante")
        st.plotly_chart(fig_comp, use_container_width=True)

    st.subheader("📥 Exportar Datos")
    if st.button("📥 Descargar CSV de Ventas"):
        csv = df.to_csv(index=False)
        st.download_button(
            "Descargar CSV",
            csv,
            f"ventas_{reporte_desde}_{reporte_hasta}.csv",
            "text/csv",
        )
