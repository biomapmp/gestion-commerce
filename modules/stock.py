import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session

from database.models import Product, Category, StockMovement, TipoMovimientoStock, SaleItem, TiendanubeProductMap
from utils.helpers import formato_moneda, formato_fecha_corta, parse_decimal
from auth.auth import get_current_user


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown("<h1>📦 Stock / Productos</h1>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Productos", "➕ Nuevo Producto", "📂 Categorías", "📊 Movimientos"])

    with tab1:
        render_productos(session, tenant_id)
    with tab2:
        render_nuevo_producto(session, tenant_id)
    with tab3:
        render_categorias(session, tenant_id)
    with tab4:
        render_movimientos(session, tenant_id)


def render_productos(session: Session, tenant_id: int):
    productos = (
        session.query(Product)
        .filter(Product.tenant_id == tenant_id)
        .order_by(Product.nombre)
        .all()
    )

    search = st.text_input("🔍 Buscar producto por nombre o código")
    if search:
        productos = [
            p for p in productos
            if search.lower() in p.nombre.lower() or search.lower() in p.codigo.lower()
        ]

    data = []
    for p in productos:
        categoria = p.category.nombre if p.category else "Sin categoría"
        estado = "✅" if float(p.stock_actual) > float(p.stock_minimo) else "⚠️"
        data.append(
            {
                "ID": p.id,
                "Código": p.codigo,
                "Nombre": p.nombre,
                "Categoría": categoria,
                "Stock Actual": float(p.stock_actual),
                "Stock Mínimo": float(p.stock_minimo),
                "P. Compra": formato_moneda(p.precio_compra),
                "P. Venta": formato_moneda(p.precio_venta),
                "Margen": f"{((float(p.precio_venta) - float(p.precio_compra)) / float(p.precio_compra) * 100):.1f}%" if float(p.precio_compra) > 0 else "N/A",
                "Estado": estado,
                "Unidad": p.unidad_medida,
            }
        )

    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay productos registrados")

    st.markdown("### ✏️ Editar Producto")
    prod_dict = {f"{p.id} - {p.nombre}": p.id for p in productos}
    if prod_dict:
        selected = st.selectbox("Seleccionar producto", options=list(prod_dict.keys()))
        if selected:
            pid = prod_dict[selected]
            producto = session.query(Product).filter_by(id=pid, tenant_id=tenant_id).first()
            if producto:
                with st.expander(f"✏️ {producto.nombre}", expanded=True):
                    with st.form(f"edit_producto_{producto.id}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            codigo = st.text_input("Código", value=producto.codigo)
                            nombre = st.text_input("Nombre", value=producto.nombre)
                            categorias = session.query(Category).filter(
                                Category.tenant_id == tenant_id,
                                Category.tipo == "PRODUCTO",
                            ).all()
                            cat_dict = {c.nombre: c.id for c in categorias}
                            cat_dict["Sin categoría"] = None
                            cat_actual = producto.category.nombre if producto.category else "Sin categoría"
                            cat_selected = st.selectbox(
                                "Categoría",
                                options=list(cat_dict.keys()),
                                index=list(cat_dict.keys()).index(cat_actual) if cat_actual in cat_dict else 0,
                            )
                            precio_compra = st.number_input(
                                "Precio Compra",
                                value=float(producto.precio_compra),
                                format="%.2f",
                            )
                        with col2:
                            precio_venta = st.number_input(
                                "Precio Venta",
                                value=float(producto.precio_venta),
                                format="%.2f",
                            )
                            stock_actual = st.number_input(
                                "Stock Actual",
                                value=float(producto.stock_actual),
                                format="%.2f",
                            )
                            stock_minimo = st.number_input(
                                "Stock Mínimo",
                                value=float(producto.stock_minimo),
                                format="%.2f",
                            )
                            unidad = st.text_input("Unidad de Medida", value=producto.unidad_medida)

                        descripcion = st.text_area("Descripción", value=producto.descripcion)

                        if st.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                            producto.codigo = codigo
                            producto.nombre = nombre
                            producto.category_id = cat_dict[cat_selected]
                            producto.precio_compra = parse_decimal(precio_compra)
                            producto.precio_venta = parse_decimal(precio_venta)
                            producto.stock_actual = parse_decimal(stock_actual)
                            producto.stock_minimo = parse_decimal(stock_minimo)
                            producto.unidad_medida = unidad
                            producto.descripcion = descripcion
                            session.commit()
                            st.success("Producto actualizado")
                            st.rerun()

                    st.markdown("---")
                    st.markdown("### 🗑️ Zona de Peligro")
                    confirmar = st.checkbox(f"Confirmar eliminación de **{producto.nombre}**", key=f"del_confirm_{producto.id}")
                    if confirmar:
                        if st.button("🗑️ Eliminar Producto", type="primary", use_container_width=True):
                            session.query(TiendanubeProductMap).filter_by(product_id=producto.id).delete()
                            session.query(SaleItem).filter(SaleItem.product_id == producto.id).update({"product_id": None})
                            session.delete(producto)
                            session.commit()
                            st.success("Producto eliminado")
                            st.rerun()


def render_nuevo_producto(session: Session, tenant_id: int):
    categorias = session.query(Category).filter(
        Category.tenant_id == tenant_id,
        Category.tipo == "PRODUCTO",
    ).all()

    cat_opts = {c.nombre: c.id for c in categorias}
    cat_opts["Sin categoría"] = None

    with st.form("nuevo_producto"):
        col1, col2 = st.columns(2)
        with col1:
            codigo = st.text_input("Código", placeholder="Opcional")
            nombre = st.text_input("Nombre *", placeholder="Nombre del producto")
            categoria_nombre = st.selectbox(
                "Categoría",
                options=list(cat_opts.keys()),
            )
            categoria_id = cat_opts[categoria_nombre]
            precio_compra = st.number_input("Precio de Compra", min_value=0.0, format="%.2f")
        with col2:
            precio_venta = st.number_input("Precio de Venta", min_value=0.0, format="%.2f")
            stock_inicial = st.number_input("Stock Inicial", min_value=0.0, format="%.2f")
            stock_minimo = st.number_input("Stock Mínimo", min_value=0.0, format="%.2f")
            unidad_medida = st.text_input("Unidad de Medida", value="unidad")

        descripcion = st.text_area("Descripción")

        if st.form_submit_button("💾 Guardar Producto", use_container_width=True):
            if not nombre:
                st.error("El nombre es obligatorio")
            else:
                producto = Product(
                    tenant_id=tenant_id,
                    category_id=categoria_id if categoria_id else None,
                    codigo=codigo,
                    nombre=nombre,
                    descripcion=descripcion,
                    precio_compra=parse_decimal(precio_compra),
                    precio_venta=parse_decimal(precio_venta),
                    stock_actual=parse_decimal(stock_inicial),
                    stock_minimo=parse_decimal(stock_minimo),
                    unidad_medida=unidad_medida,
                )
                session.add(producto)
                session.flush()

                if stock_inicial > 0:
                    movimiento = StockMovement(
                        product_id=producto.id,
                        tipo=TipoMovimientoStock.ENTRADA,
                        cantidad=parse_decimal(stock_inicial),
                        stock_resultante=parse_decimal(stock_inicial),
                        motivo="Stock inicial",
                    )
                    session.add(movimiento)

                session.commit()
                st.success(f"Producto {nombre} creado correctamente")
                st.rerun()


def render_categorias(session: Session, tenant_id: int):
    st.subheader("Categorías de Productos")

    categorias = (
        session.query(Category)
        .filter(Category.tenant_id == tenant_id, Category.tipo == "PRODUCTO")
        .all()
    )

    if categorias:
        data = [
            {
                "ID": c.id,
                "Nombre": c.nombre,
                "Descripción": c.descripcion,
                "Productos": (
                    session.query(Product)
                    .filter(Product.category_id == c.id)
                    .count()
                ),
            }
            for c in categorias
        ]
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    with st.form("nueva_categoria"):
        nombre = st.text_input("Nombre de la categoría")
        descripcion = st.text_input("Descripción (opcional)")

        if st.form_submit_button("➕ Agregar Categoría"):
            if nombre:
                existe = (
                    session.query(Category)
                    .filter(
                        Category.tenant_id == tenant_id,
                        Category.tipo == "PRODUCTO",
                        Category.nombre == nombre,
                    )
                    .first()
                )
                if existe:
                    st.error("Ya existe una categoría con ese nombre")
                else:
                    cat = Category(
                        tenant_id=tenant_id,
                        nombre=nombre,
                        tipo="PRODUCTO",
                        descripcion=descripcion,
                    )
                    session.add(cat)
                    session.commit()
                    st.success(f"Categoría {nombre} creada")
                    st.rerun()
            else:
                st.error("El nombre es obligatorio")


def render_movimientos(session: Session, tenant_id: int):
    st.subheader("Movimientos de Stock")

    col1, col2 = st.columns(2)
    with col1:
        producto_id = st.selectbox(
            "Filtrar por producto",
            options=[None],
            format_func=lambda x: "Todos los productos",
        )
    with col2:
        tipo_filtro = st.selectbox(
            "Tipo de movimiento",
            ["Todos", "ENTRADA", "SALIDA", "AJUSTE"],
        )

    movimientos = (
        session.query(StockMovement)
        .join(Product)
        .filter(Product.tenant_id == tenant_id)
        .order_by(StockMovement.created_at.desc())
        .limit(100)
        .all()
    )

    if movimientos:
        data = [
            {
                "Fecha": formato_fecha_corta(m.created_at),
                "Producto": m.product.nombre,
                "Tipo": m.tipo.value,
                "Cantidad": float(m.cantidad),
                "Stock Resultante": float(m.stock_resultante),
                "Motivo": m.motivo,
            }
            for m in movimientos
        ]
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("No hay movimientos registrados")

    st.markdown("### ➕ Registrar Movimiento Manual")
    productos = (
        session.query(Product)
        .filter(Product.tenant_id == tenant_id)
        .all()
    )
    prod_dict = {p.nombre: p for p in productos}

    with st.form("movimiento_manual"):
        col1, col2, col3 = st.columns(3)
        with col1:
            prod_name = st.selectbox("Producto", options=list(prod_dict.keys()))
        with col2:
            tipo_mov = st.selectbox(
                "Tipo", [t.value for t in TipoMovimientoStock]
            )
        with col3:
            cantidad = st.number_input("Cantidad", min_value=0.01, format="%.2f")

        motivo = st.text_input("Motivo")

        if st.form_submit_button("💾 Registrar Movimiento"):
            producto = prod_dict[prod_name]
            if tipo_mov == TipoMovimientoStock.ENTRADA.value:
                nuevo_stock = float(producto.stock_actual) + cantidad
            elif tipo_mov == TipoMovimientoStock.SALIDA.value:
                nuevo_stock = float(producto.stock_actual) - cantidad
            else:
                nuevo_stock = cantidad

            movimiento = StockMovement(
                product_id=producto.id,
                tipo=TipoMovimientoStock(tipo_mov),
                cantidad=parse_decimal(cantidad),
                stock_resultante=parse_decimal(nuevo_stock),
                motivo=motivo,
            )
            producto.stock_actual = parse_decimal(nuevo_stock)
            session.add(movimiento)
            session.commit()
            st.success("Movimiento registrado")
            st.rerun()
