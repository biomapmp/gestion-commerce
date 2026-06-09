import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session

from database.models import Client, Sale
from utils.helpers import formato_moneda, formato_fecha_corta
from auth.auth import get_current_user


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown("<h1>👥 Clientes</h1>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo Cliente"])

    with tab1:
        clientes = (
            session.query(Client)
            .filter(Client.tenant_id == tenant_id)
            .order_by(Client.nombre)
            .all()
        )
        render_listado(session, clientes, tenant_id)

    with tab2:
        render_formulario(session, tenant_id)


def render_listado(session: Session, clientes: list, tenant_id: int):
    if not clientes:
        st.info("No hay clientes registrados todavía")
        return

    search = st.text_input("🔍 Buscar cliente por nombre, documento o email")
    if search:
        clientes = [c for c in clientes if search.lower() in c.nombre.lower()
                    or search.lower() in c.documento.lower()
                    or search.lower() in c.email.lower()]

    data = []
    for c in clientes:
        ventas = (
            session.query(Sale)
            .filter(Sale.tenant_id == tenant_id, Sale.client_id == c.id)
            .count()
        )
        total_ventas = (
            session.query(Sale)
            .filter(Sale.tenant_id == tenant_id, Sale.client_id == c.id)
            .all()
        )
        total = sum(float(v.total) for v in total_ventas)

        data.append(
            {
                "ID": c.id,
                "Nombre": c.nombre,
                "Documento": c.tipo_doc + " " + c.documento if c.documento else "",
                "Email": c.email,
                "Teléfono": c.telefono,
                "Ventas": ventas,
                "Total Ventas": formato_moneda(total),
                "Localidad": c.localidad,
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### ✏️ Editar / Eliminar Cliente")
    cliente_ids = {f"{c.id} - {c.nombre}": c.id for c in clientes}
    selected = st.selectbox("Seleccionar cliente", options=list(cliente_ids.keys()))

    if selected:
        cid = cliente_ids[selected]
        cliente = session.query(Client).filter_by(id=cid, tenant_id=tenant_id).first()
        if cliente:
            with st.expander(f"✏️ Editar {cliente.nombre}", expanded=True):
                with st.form(f"edit_cliente_{cliente.id}"):
                    nombre = st.text_input("Nombre", value=cliente.nombre)
                    tipo_doc = st.selectbox(
                        "Tipo Documento",
                        ["DNI", "CI", "Pasaporte", "Otro"],
                        index=["DNI", "CI", "Pasaporte", "Otro"].index(
                            cliente.tipo_doc if cliente.tipo_doc in ["DNI", "CI", "Pasaporte", "Otro"] else "DNI"
                        ),
                    )
                    documento = st.text_input("Documento", value=cliente.documento)
                    cuit = st.text_input("CUIT", value=cliente.cuit)
                    email = st.text_input("Email", value=cliente.email)
                    telefono = st.text_input("Teléfono", value=cliente.telefono)
                    direccion = st.text_area("Dirección", value=cliente.direccion)
                    localidad = st.text_input("Localidad", value=cliente.localidad)
                    provincia = st.text_input("Provincia", value=cliente.provincia)
                    notas = st.text_area("Notas", value=cliente.notas)

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                            cliente.nombre = nombre
                            cliente.tipo_doc = tipo_doc
                            cliente.documento = documento
                            cliente.cuit = cuit
                            cliente.email = email
                            cliente.telefono = telefono
                            cliente.direccion = direccion
                            cliente.localidad = localidad
                            cliente.provincia = provincia
                            cliente.notas = notas
                            session.commit()
                            st.success("Cliente actualizado")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("🗑️ Eliminar", use_container_width=True, type="secondary"):
                            session.delete(cliente)
                            session.commit()
                            st.success("Cliente eliminado")
                            st.rerun()


def render_formulario(session: Session, tenant_id: int):
    with st.form("nuevo_cliente"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre *", placeholder="Nombre del cliente")
            tipo_doc = st.selectbox(
                "Tipo Documento", ["DNI", "CI", "Pasaporte", "Otro"]
            )
            documento = st.text_input("N° Documento")
            cuit = st.text_input("CUIT")
            email = st.text_input("Email")
        with col2:
            telefono = st.text_input("Teléfono")
            direccion = st.text_area("Dirección")
            localidad = st.text_input("Localidad")
            provincia = st.text_input("Provincia")
            codigo_postal = st.text_input("Código Postal")

        notas = st.text_area("Notas")

        if st.form_submit_button("💾 Guardar Cliente", use_container_width=True):
            if not nombre:
                st.error("El nombre es obligatorio")
            else:
                cliente = Client(
                    tenant_id=tenant_id,
                    nombre=nombre,
                    tipo_doc=tipo_doc,
                    documento=documento,
                    cuit=cuit,
                    email=email,
                    telefono=telefono,
                    direccion=direccion,
                    localidad=localidad,
                    provincia=provincia,
                    codigo_postal=codigo_postal,
                    notas=notas,
                )
                session.add(cliente)
                session.commit()
                st.success(f"Cliente {nombre} creado correctamente")
                st.rerun()
