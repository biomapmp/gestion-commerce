import requests
import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy.orm import Session

from database.models import (
    TiendanubeConfig, TiendanubeSyncLog, TiendanubeProductMap,
    Product, Category, StockMovement, TipoMovimientoStock,
)

API_BASE = "https://api.tiendanube.com/v1"
API_VERSION = "2025-03"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "GestionCommerce (mawucano@gmail.com)",
}


def get_config(session: Session, tenant_id: int) -> TiendanubeConfig | None:
    return session.query(TiendanubeConfig).filter_by(
        tenant_id=tenant_id, activo=True
    ).first()


def _api_request(
    method: str,
    store_id: str,
    access_token: str,
    endpoint: str,
    data: dict | None = None,
    params: dict | None = None,
) -> Any:
    url = f"{API_BASE}/{store_id}/{endpoint}"
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=data,
        params=params,
        timeout=30,
    )

    if response.status_code == 429:
        raise Exception("Rate limit exceeded (429)")
    if response.status_code == 402:
        raise Exception("Suscripción suspendida (402)")
    if response.status_code == 403:
        raise Exception("Acceso denegado (403)")
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise Exception(f"Error API: {response.status_code} - {response.text}")

    return response.json()


def test_connection(store_id: str, access_token: str) -> dict:
    try:
        store = _api_request("GET", store_id, access_token, "store")
        return {"success": True, "store": store}
    except Exception as e:
        return {"success": False, "error": str(e)}


def obtener_productos_tiendanube(
    store_id: str, access_token: str, page: int = 1, per_page: int = 200
) -> tuple[list[dict], int]:
    productos = _api_request(
        "GET", store_id, access_token, "products",
        params={"page": page, "per_page": per_page},
    )
    if productos is None:
        return [], 0

    total = len(productos)
    return productos, total


def obtener_variantes(
    store_id: str, access_token: str, product_id: int
) -> list[dict]:
    variantes = _api_request(
        "GET", store_id, access_token, f"products/{product_id}/variants",
    )
    return variantes or []


def _producto_tn_a_local(
    tn_product: dict, variantes: list[dict], tenant_id: int, category_id: int | None
) -> dict:
    variant = variantes[0] if variantes else {}

    nombre = tn_product.get("name", {}).get("es", tn_product.get("name", ""))
    if isinstance(nombre, dict):
        nombre = nombre.get("es", "")

    descripcion = tn_product.get("description", {}).get("es", "")
    if isinstance(descripcion, dict):
        descripcion = descripcion.get("es", "")

    precio = float(variant.get("price", tn_product.get("variants", [{}])[0].get("price", 0)))
    stock = float(variant.get("stock", 0))
    sku = variant.get("sku", tn_product.get("sku", ""))
    peso = float(variant.get("weight", 0))

    return {
        "codigo": sku or str(tn_product.get("id", "")),
        "nombre": nombre or f"Producto TN #{tn_product.get('id')}",
        "descripcion": descripcion,
        "precio_compra": Decimal(str(precio * 0.6)).quantize(Decimal("0.01")),
        "precio_venta": Decimal(str(precio)).quantize(Decimal("0.01")),
        "stock_actual": Decimal(str(stock)),
        "stock_minimo": Decimal("5"),
        "unidad_medida": "unidad",
        "activo": tn_product.get("published", True),
        "tenant_id": tenant_id,
        "category_id": category_id,
        "peso": peso,
        "tiendanube_id": tn_product.get("id"),
        "variant_id": variant.get("id"),
        "images": tn_product.get("images", []),
    }


def sincronizar_productos(
    session: Session, tenant_id: int, config: TiendanubeConfig
) -> TiendanubeSyncLog:
    log = TiendanubeSyncLog(
        tenant_id=tenant_id,
        tipo="SINCRONIZACION_PRODUCTOS",
        estado="EJECUTANDO",
    )
    session.add(log)
    session.flush()

    errores = []
    descargados = 0
    actualizados = 0
    creados = 0

    try:
        cat = session.query(Category).filter_by(
            tenant_id=tenant_id, nombre="Tiendanube", tipo="PRODUCTO"
        ).first()
        if not cat:
            cat = Category(tenant_id=tenant_id, nombre="Tiendanube", tipo="PRODUCTO")
            session.add(cat)
            session.flush()

        page = 1
        while True:
            productos_tn, _ = obtener_productos_tiendanube(
                config.store_id, config.access_token, page=page
            )
            if not productos_tn:
                break

            for tn_p in productos_tn:
                try:
                    tn_id = tn_p["id"]
                    variantes = obtener_variantes(
                        config.store_id, config.access_token, tn_id
                    )

                    local_data = _producto_tn_a_local(
                        tn_p, variantes, tenant_id, cat.id
                    )
                    tn_product_id = local_data.pop("tiendanube_id")
                    tn_variant_id = local_data.pop("variant_id")
                    local_data.pop("images", None)
                    local_data.pop("peso", None)

                    mapping = session.query(TiendanubeProductMap).filter_by(
                        tenant_id=tenant_id,
                        tiendanube_product_id=tn_product_id,
                    ).first()

                    if mapping:
                        producto = session.query(Product).filter_by(
                            id=mapping.product_id, tenant_id=tenant_id
                        ).first()
                        if producto:
                            for key, val in local_data.items():
                                if key not in ("tenant_id", "category_id"):
                                    setattr(producto, key, val)
                            mapping.ultima_sincronizacion = datetime.utcnow()
                            actualizados += 1
                    else:
                        producto = Product(**local_data)
                        session.add(producto)
                        session.flush()

                        mapping = TiendanubeProductMap(
                            tenant_id=tenant_id,
                            product_id=producto.id,
                            tiendanube_product_id=tn_product_id,
                            tiendanube_variant_id=tn_variant_id,
                        )
                        session.add(mapping)
                        creados += 1

                    descargados += 1
                except Exception as e:
                    errores.append(f"Producto #{tn_p.get('id')}: {str(e)}")

            page += 1

        config.ultima_sincronizacion = datetime.utcnow()
        session.commit()

        log.estado = "COMPLETADO"
        log.productos_descargados = descargados
        log.productos_actualizados = actualizados
        log.productos_creados = creados
        if errores:
            log.errores = "\n".join(errores[:10])
        log.detalle = (
            f"Descargados: {descargados} | "
            f"Creados: {creados} | "
            f"Actualizados: {actualizados} | "
            f"Errores: {len(errores)}"
        )
        session.commit()

    except Exception as e:
        log.estado = "ERROR"
        log.errores = str(e)
        session.commit()

    return log


def enviar_precios_tiendanube(
    session: Session, tenant_id: int, config: TiendanubeConfig
) -> TiendanubeSyncLog:
    log = TiendanubeSyncLog(
        tenant_id=tenant_id,
        tipo="ACTUALIZACION_PRECIOS",
        estado="EJECUTANDO",
    )
    session.add(log)
    session.flush()

    errores = []
    actualizados = 0

    try:
        mappings = session.query(TiendanubeProductMap).filter_by(
            tenant_id=tenant_id
        ).all()

        for mapping in mappings:
            producto = session.query(Product).filter_by(
                id=mapping.product_id, tenant_id=tenant_id
            ).first()
            if not producto:
                continue

            try:
                variant_id = mapping.tiendanube_variant_id
                if not variant_id:
                    variantes = obtener_variantes(
                        config.store_id, config.access_token,
                        mapping.tiendanube_product_id,
                    )
                    if variantes:
                        variant_id = variantes[0]["id"]

                if variant_id:
                    _api_request(
                        "PUT",
                        config.store_id, config.access_token,
                        f"products/{mapping.tiendanube_product_id}/variants/{variant_id}",
                        data={
                            "price": float(producto.precio_venta),
                            "stock": int(float(producto.stock_actual)),
                        },
                    )
                    actualizados += 1

            except Exception as e:
                errores.append(
                    f"Producto #{mapping.tiendanube_product_id}: {str(e)}"
                )

        session.commit()

        log.estado = "COMPLETADO"
        log.productos_actualizados = actualizados
        if errores:
            log.errores = "\n".join(errores[:10])
        log.detalle = f"Actualizados: {actualizados} | Errores: {len(errores)}"
        session.commit()

    except Exception as e:
        log.estado = "ERROR"
        log.errores = str(e)
        session.commit()

    return log


def registrar_webhooks(
    store_id: str, access_token: str, webhook_url: str
) -> list[dict]:
    eventos = [
        "products/create",
        "products/update",
        "products/delete",
    ]
    resultados = []

    for evento in eventos:
        try:
            result = _api_request(
                "POST", store_id, access_token, "webhooks",
                data={
                    "event": evento,
                    "url": webhook_url,
                },
            )
            resultados.append({"evento": evento, "success": True, "data": result})
        except Exception as e:
            resultados.append({"evento": evento, "success": False, "error": str(e)})

    return resultados
