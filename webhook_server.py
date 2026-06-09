"""
Servidor webhook para recibir notificaciones de Tiendanube.

Correr en paralelo con la app:
  python webhook_server.py

Recibe POST en /webhooks/tiendanube y procesa
eventos de productos (create/update/delete).
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from database.connection import get_session, init_db
from database.models import (
    TiendanubeConfig, TiendanubeProductMap, TiendanubeSyncLog,
    Product, StockMovement, TipoMovimientoStock,
)
from modules.tiendanube_client import (
    obtener_productos_tiendanube, obtener_variantes,
)

PORT = 8081


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhooks/tiendanube":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body)

        event = self.headers.get("X-Tiendanube-Event", "unknown")
        store_id = str(data.get("store_id", ""))

        print(f"[{datetime.now()}] Webhook recibido: {event} (store: {store_id})")

        try:
            session = get_session()
            config = session.query(TiendanubeConfig).filter_by(
                store_id=store_id, activo=True
            ).first()

            if not config:
                print(f"  ❌ No hay config para store {store_id}")
                self.send_response(200)
                self.end_headers()
                return

            if event == "products/create":
                product_id = data.get("id")
                if product_id:
                    _procesar_producto_creado(session, config, product_id)

            elif event == "products/update":
                product_id = data.get("id")
                if product_id:
                    _procesar_producto_actualizado(session, config, product_id)

            elif event == "products/delete":
                product_id = data.get("id")
                if product_id:
                    _procesar_producto_eliminado(session, config, product_id)

            session.close()
        except Exception as e:
            print(f"  ❌ Error: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def log_message(self, format, *args):
        if "health" not in str(args):
            print(f"[webhook] {args[0]} {args[1]} {args[2]}")


def _procesar_producto_creado(session, config, tn_product_id):
    print(f"  Procesando producto creado #{tn_product_id}")
    productos, _ = obtener_productos_tiendanube(
        config.store_id, config.access_token,
        params={"ids": str(tn_product_id)},
    )
    if not productos:
        print(f"  Producto #{tn_product_id} no encontrado en API")
        return

    tn_product = productos[0]
    variantes = obtener_variantes(
        config.store_id, config.access_token, tn_product_id
    )

    from modules.tiendanube_client import _producto_tn_a_local
    from database.models import Category

    cat = session.query(Category).filter_by(
        tenant_id=config.tenant_id, nombre="Tiendanube", tipo="PRODUCTO"
    ).first()

    local_data = _producto_tn_a_local(tn_product, variantes, config.tenant_id, cat.id if cat else None)
    tn_id = local_data.pop("tiendanube_id")
    tn_variant_id = local_data.pop("variant_id")
    local_data.pop("images", None)
    local_data.pop("peso", None)

    producto = Product(**local_data)
    session.add(producto)
    session.flush()

    mapping = TiendanubeProductMap(
        tenant_id=config.tenant_id,
        product_id=producto.id,
        tiendanube_product_id=tn_id,
        tiendanube_variant_id=tn_variant_id,
    )
    session.add(mapping)
    session.commit()
    print(f"  ✅ Producto #{producto.id} creado desde TN #{tn_id}")


def _procesar_producto_actualizado(session, config, tn_product_id):
    print(f"  Procesando producto actualizado #{tn_product_id}")

    mapping = session.query(TiendanubeProductMap).filter_by(
        tenant_id=config.tenant_id,
        tiendanube_product_id=tn_product_id,
    ).first()

    if not mapping:
        print(f"  Producto #{tn_product_id} no mapeado, creando...")
        return _procesar_producto_creado(session, config, tn_product_id)

    productos, _ = obtener_productos_tiendanube(
        config.store_id, config.access_token,
        params={"ids": str(tn_product_id)},
    )
    if not productos:
        return

    tn_product = productos[0]
    variantes = obtener_variantes(
        config.store_id, config.access_token, tn_product_id
    )

    from modules.tiendanube_client import _producto_tn_a_local

    cat = session.query(Category).filter_by(
        tenant_id=config.tenant_id, nombre="Tiendanube", tipo="PRODUCTO"
    ).first()

    local_data = _producto_tn_a_local(tn_product, variantes, config.tenant_id, cat.id if cat else None)
    local_data.pop("tiendanube_id")
    local_data.pop("variant_id")
    local_data.pop("images", None)
    local_data.pop("peso", None)

    producto = session.query(Product).filter_by(id=mapping.product_id).first()
    if producto:
        for key, val in local_data.items():
            if key not in ("tenant_id", "category_id"):
                setattr(producto, key, val)
        mapping.ultima_sincronizacion = datetime.utcnow()
        session.commit()
        print(f"  ✅ Producto #{producto.id} actualizado desde TN #{tn_product_id}")


def _procesar_producto_eliminado(session, config, tn_product_id):
    print(f"  Procesando producto eliminado #{tn_product_id}")

    mapping = session.query(TiendanubeProductMap).filter_by(
        tenant_id=config.tenant_id,
        tiendanube_product_id=tn_product_id,
    ).first()

    if mapping:
        producto = session.query(Product).filter_by(id=mapping.product_id).first()
        if producto:
            producto.activo = False
            session.delete(mapping)
            session.commit()
            print(f"  ✅ Producto #{producto.id} desactivado (TN #{tn_product_id} eliminado)")


def main():
    init_db()
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"🌐 Servidor webhook escuchando en http://0.0.0.0:{PORT}/webhooks/tiendanube")
    print(f"   (configurá esta URL en tu app de Tiendanube)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
        server.server_close()


if __name__ == "__main__":
    main()
