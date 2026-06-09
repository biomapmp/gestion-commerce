import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session

from database.models import (
    TiendanubeConfig, TiendanubeSyncLog, TiendanubeProductMap,
    Product,
)
from modules.tiendanube_client import (
    get_config, test_connection, sincronizar_productos,
    enviar_precios_tiendanube, registrar_webhooks,
)
from utils.helpers import formato_moneda, formato_fecha
from auth.auth import get_current_user


def render(session: Session):
    user = get_current_user()
    tenant_id = user["tenant_id"]

    st.markdown("<h1>🛒 Tiendanube</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color: #666;'>Sincronizá productos, precios y stock "
        "con tu tienda Tiendanube automáticamente.</p>",
        unsafe_allow_html=True,
    )

    config = get_config(session, tenant_id)

    tab1, tab2, tab3 = st.tabs([
        "🔌 Conexión",
        "🔄 Sincronización",
        "📋 Historial",
    ])

    with tab1:
        render_conexion(session, tenant_id, config)
    with tab2:
        render_sincronizacion(session, tenant_id, config)
    with tab3:
        render_historial(session, tenant_id)


def render_conexion(
    session: Session, tenant_id: int, config: TiendanubeConfig | None
):
    st.subheader("Configuración de Tiendanube")

    if config and config.activo:
        st.success(
            f"✅ Conectado a **{config.store_name or 'Tiendanube'}** "
            f"(Store ID: {config.store_id})"
        )
        if config.ultima_sincronizacion:
            st.info(
                f"Última sincronización: "
                f"{formato_fecha(config.ultima_sincronizacion)}"
            )

        with st.expander("📋 Detalles de conexión"):
            st.write(f"**Store ID:** {config.store_id}")
            st.write(f"**Store Name:** {config.store_name or '—'}")
            st.write(f"**Email:** {config.store_email or '—'}")
            st.write(f"**Auto-sync:** {'✅ Activado' if config.auto_sync else '❌ Desactivado'}")
            if config.auto_sync:
                st.write(f"**Intervalo:** cada {config.sync_interval_minutos} min")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔌 Probar Conexión", use_container_width=True):
                with st.spinner("Probando conexión..."):
                    result = test_connection(
                        config.store_id, config.access_token
                    )
                    if result["success"]:
                        store = result["store"]
                        config.store_name = store.get("name", "")
                        config.store_email = store.get("email", "")
                        session.commit()
                        st.success(
                            f"✅ Conexión exitosa: **{store.get('name')}**"
                        )
                    else:
                        st.error(f"❌ Error: {result.get('error')}")
        with col2:
            if st.button("🗑️ Desconectar", use_container_width=True, type="secondary"):
                config.activo = False
                session.commit()
                st.success("Tiendanube desconectado")
                st.rerun()

        with st.expander("⚙️ Auto-sincronización"):
            with st.form("auto_sync_form"):
                auto = st.checkbox(
                    "Activar sincronización automática",
                    value=config.auto_sync,
                )
                interval = st.number_input(
                    "Intervalo (minutos)",
                    min_value=5,
                    max_value=1440,
                    value=config.sync_interval_minutos or 60,
                )
                if st.form_submit_button("💾 Guardar"):
                    config.auto_sync = auto
                    config.sync_interval_minutos = interval
                    session.commit()
                    st.success("Configuración guardada")
                    st.rerun()

    with st.expander(
        "🔗 Conectar nueva tienda", expanded=not (config and config.activo)
    ):
        st.markdown(
            """
        ### ¿Cómo obtener los datos de conexión?

        1. Andá a [Panel de Partners Tiendanube](https://www.tiendanube.com/partners)
        2. Creá una **nueva App** o usá una existente
        3. En la app, obtené el **Client ID** y **Client Secret**
        4. Usá la URL de instalación para conectar una tienda:
           `https://www.tiendanube.com/apps/{app_id}/authorize`
        5. Después de instalar, vas a recibir un **código de autorización**
        6. Intercambiá ese código por un **Access Token** (vía POST a
           `https://www.tiendanube.com/apps/authorize/token`)
        """
        )

        with st.form("conexion_form"):
            col1, col2 = st.columns(2)
            with col1:
                store_id = st.text_input(
                    "Store ID *",
                    placeholder="123456",
                    help="ID numérico de la tienda",
                )
                access_token = st.text_input(
                    "Access Token *",
                    type="password",
                    placeholder="Bearer token",
                )
            with col2:
                client_id = st.text_input("Client ID (opcional)")
                client_secret = st.text_input(
                    "Client Secret (opcional)", type="password"
                )

            if st.form_submit_button("🔌 Conectar", use_container_width=True):
                if not store_id or not access_token:
                    st.error("Store ID y Access Token son obligatorios")
                else:
                    with st.spinner("Verificando conexión..."):
                        result = test_connection(store_id, access_token)
                        if result["success"]:
                            store = result["store"]
                            if config:
                                config.store_id = store_id
                                config.access_token = access_token
                                config.client_id = client_id
                                config.client_secret = client_secret
                                config.store_name = store.get("name", "")
                                config.store_email = store.get("email", "")
                                config.activo = True
                            else:
                                config = TiendanubeConfig(
                                    tenant_id=tenant_id,
                                    store_id=store_id,
                                    access_token=access_token,
                                    client_id=client_id,
                                    client_secret=client_secret,
                                    store_name=store.get("name", ""),
                                    store_email=store.get("email", ""),
                                    activo=True,
                                )
                                session.add(config)
                            session.commit()
                            st.success(
                                f"✅ Conectado a **{store.get('name')}**"
                            )
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {result.get('error')}")


def render_sincronizacion(
    session: Session, tenant_id: int, config: TiendanubeConfig | None
):
    if not config or not config.activo:
        st.info("Conectá una tienda de Tiendanube primero")
        return

    st.subheader("Sincronización de Productos")

    mapeos = session.query(TiendanubeProductMap).filter_by(
        tenant_id=tenant_id
    ).count()
    productos_locales = session.query(Product).filter_by(
        tenant_id=tenant_id
    ).count()
    productos_sincronizados = mapeos

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Productos en GestionCommerce", productos_locales)
    with col2:
        st.metric("Productos mapeados (TN)", productos_sincronizados)
    with col3:
        pct = (productos_sincronizados / productos_locales * 100) if productos_locales else 0
        st.metric("Sincronizados", f"{pct:.0f}%")

    st.markdown("### 📥 Tiendanube → GestionCommerce")
    st.markdown(
        "Descarga productos desde Tiendanube y los crea o actualiza "
        "en tu base local."
    )

    if st.button("⬇️ Sincronizar desde Tiendanube", use_container_width=True, type="primary"):
        with st.spinner("Sincronizando productos..."):
            log = sincronizar_productos(session, tenant_id, config)

        if log.estado == "COMPLETADO":
            st.success(
                f"✅ Sincronización completada:\n"
                f"- {log.productos_descargados} procesados\n"
                f"- {log.productos_creados} creados\n"
                f"- {log.productos_actualizados} actualizados"
            )
            if log.errores:
                st.warning(f"Errores:\n{log.errores}")
        else:
            st.error(f"❌ Error: {log.errores}")
        st.rerun()

    st.markdown("---")
    st.markdown("### 📤 GestionCommerce → Tiendanube")
    st.markdown(
        "Envía precios y stock actualizados desde GestionCommerce "
        "hacia Tiendanube."
    )

    if st.button("⬆️ Actualizar precios en Tiendanube", use_container_width=True):
        with st.spinner("Actualizando precios..."):
            log = enviar_precios_tiendanube(session, tenant_id, config)

        if log.estado == "COMPLETADO":
            st.success(
                f"✅ Precios actualizados: {log.productos_actualizados} productos"
            )
            if log.errores:
                st.warning(f"Errores:\n{log.errores}")
        else:
            st.error(f"❌ Error: {log.errores}")
        st.rerun()

    st.markdown("---")
    st.markdown("### 🔔 Webhooks")
    st.markdown(
        "Configurá webhooks para que Tiendanube notifique "
        "automáticamente cuando un producto cambie."
    )

    base_url = st.text_input(
        "URL de tu servidor",
        value="https://gestion-commerce.fly.dev",
        help="URL donde está hosteada tu app",
    )

    if st.button("🔔 Registrar Webhooks", use_container_width=True):
        with st.spinner("Registrando webhooks..."):
            webhook_url = f"{base_url.rstrip('/')}/webhooks/tiendanube"
            resultados = registrar_webhooks(
                config.store_id, config.access_token, webhook_url
            )

        for r in resultados:
            if r["success"]:
                st.success(f"✅ Webhook {r['evento']} registrado")
            else:
                st.error(f"❌ Webhook {r['evento']}: {r.get('error')}")


def render_historial(session: Session, tenant_id: int):
    st.subheader("Historial de Sincronización")

    logs = (
        session.query(TiendanubeSyncLog)
        .filter_by(tenant_id=tenant_id)
        .order_by(TiendanubeSyncLog.created_at.desc())
        .limit(50)
        .all()
    )

    if not logs:
        st.info("No hay sincronizaciones todavía")
        return

    data = []
    for log in logs:
        estado_icon = {
            "COMPLETADO": "✅",
            "ERROR": "❌",
            "EJECUTANDO": "🔄",
            "PENDIENTE": "⏳",
        }.get(log.estado, "❓")

        data.append({
            "Fecha": formato_fecha(log.created_at),
            "Tipo": log.tipo,
            "Estado": f"{estado_icon} {log.estado}",
            "Descargados": log.productos_descargados,
            "Creados": log.productos_creados,
            "Actualizados": log.productos_actualizados,
            "Detalle": log.detalle or "",
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("🗑️ Limpiar historial", type="secondary"):
        session.query(TiendanubeSyncLog).filter_by(
            tenant_id=tenant_id
        ).delete()
        session.commit()
        st.success("Historial limpiado")
        st.rerun()
