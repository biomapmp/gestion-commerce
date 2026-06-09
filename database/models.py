from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Text, Numeric, DateTime, Date,
    ForeignKey, Boolean, Enum as SAEnum, create_engine
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class MovimientoTipo(str, enum.Enum):
    INGRESO = "INGRESO"
    EGRESO = "EGRESO"


class TipoComprobante(str, enum.Enum):
    FACTURA_A = "FACTURA_A"
    FACTURA_B = "FACTURA_B"
    FACTURA_C = "FACTURA_C"
    TICKET = "TICKET"
    NOTA_CREDITO = "NOTA_CREDITO"
    NOTA_DEBITO = "NOTA_DEBITO"
    RECIBO = "RECIBO"
    OTRO = "OTRO"


class TipoMovimientoStock(str, enum.Enum):
    ENTRADA = "ENTRADA"
    SALIDA = "SALIDA"
    AJUSTE = "AJUSTE"


class RolUsuario(str, enum.Enum):
    ADMIN = "ADMIN"
    USUARIO = "USUARIO"
    VIEWER = "VIEWER"


# ─── Multi-Tenant ──────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(200), nullable=False)
    nombre_fantasia = Column(String(200), default="")
    cuit = Column(String(20), default="")
    direccion = Column(Text, default="")
    telefono = Column(String(50), default="")
    email = Column(String(200), default="")
    logo_url = Column(String(500), default="")
    moneda = Column(String(10), default="ARS")
    created_at = Column(DateTime, default=datetime.utcnow)
    activo = Column(Boolean, default=True)

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="tenant", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="tenant", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="tenant", cascade="all, delete-orphan")
    cash_flow = relationship("CashFlow", back_populates="tenant", cascade="all, delete-orphan")
    accounting_entries = relationship("AccountingEntry", back_populates="tenant", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="tenant", cascade="all, delete-orphan")
    tiendanube_configs = relationship("TiendanubeConfig", backref="tenant", cascade="all, delete-orphan")
    tiendanube_sync_logs = relationship("TiendanubeSyncLog", backref="tenant", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    rol = Column(SAEnum(RolUsuario), default=RolUsuario.USUARIO)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


# ─── Clientes ──────────────────────────────────────────────

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    nombre = Column(String(200), nullable=False)
    tipo_doc = Column(String(20), default="DNI")
    documento = Column(String(20), default="")
    cuit = Column(String(20), default="")
    email = Column(String(200), default="")
    telefono = Column(String(50), default="")
    direccion = Column(Text, default="")
    localidad = Column(String(100), default="")
    provincia = Column(String(100), default="")
    codigo_postal = Column(String(20), default="")
    notas = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="clients")
    sales = relationship("Sale", back_populates="client")


# ─── Categorías ────────────────────────────────────────────

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    tipo = Column(String(50), default="PRODUCTO")
    descripcion = Column(Text, default="")

    tenant = relationship("Tenant", back_populates="categories")
    products = relationship("Product", back_populates="category")


# ─── Productos / Stock ─────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    codigo = Column(String(50), default="")
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text, default="")
    precio_compra = Column(Numeric(12, 2), default=0)
    precio_venta = Column(Numeric(12, 2), default=0)
    stock_actual = Column(Numeric(12, 2), default=0)
    stock_minimo = Column(Numeric(12, 2), default=0)
    unidad_medida = Column(String(20), default="unidad")
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="products")
    category = relationship("Category", back_populates="products")
    stock_movements = relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")
    sale_items = relationship("SaleItem", back_populates="product")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    tipo = Column(SAEnum(TipoMovimientoStock), nullable=False)
    cantidad = Column(Numeric(12, 2), nullable=False)
    stock_resultante = Column(Numeric(12, 2), nullable=False)
    motivo = Column(String(200), default="")
    referencia_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="stock_movements")


# ─── Ventas ────────────────────────────────────────────────

class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    comprobante = Column(SAEnum(TipoComprobante), default=TipoComprobante.TICKET)
    numero_comprobante = Column(String(50), default="")
    fecha = Column(Date, default=date.today)
    subtotal = Column(Numeric(12, 2), default=0)
    descuento = Column(Numeric(12, 2), default=0)
    iva = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), default=0)
    forma_pago = Column(String(50), default="EFECTIVO")
    observaciones = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="sales")
    client = relationship("Client", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    descripcion = Column(String(300), nullable=False)
    cantidad = Column(Numeric(12, 2), nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")


# ─── Flujo de Caja ─────────────────────────────────────────

class CashFlow(Base):
    __tablename__ = "cash_flow"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    fecha = Column(Date, default=date.today)
    tipo = Column(SAEnum(MovimientoTipo), nullable=False)
    categoria = Column(String(100), default="")
    descripcion = Column(String(300), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
    forma_pago = Column(String(50), default="EFECTIVO")
    referencia_id = Column(Integer, nullable=True)
    referencia_tipo = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="cash_flow")


# ─── Costos / Gastos ───────────────────────────────────────

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    fecha = Column(Date, default=date.today)
    categoria = Column(String(100), nullable=False)
    descripcion = Column(String(300), nullable=False)
    proveedor = Column(String(200), default="")
    monto = Column(Numeric(12, 2), nullable=False)
    iva = Column(Numeric(12, 2), default=0)
    monto_total = Column(Numeric(12, 2), nullable=False)
    forma_pago = Column(String(50), default="EFECTIVO")
    comprobante = Column(String(100), default="")
    periodicidad = Column(String(50), default="UNICO")
    notas = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="expenses")


# ─── Tiendanube (Integración) ──────────────────────────────

class TiendanubeConfig(Base):
    __tablename__ = "tiendanube_config"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    store_id = Column(String(20), nullable=False)
    access_token = Column(String(500), nullable=False)
    client_id = Column(String(100), default="")
    client_secret = Column(String(200), default="")
    store_name = Column(String(200), default="")
    store_email = Column(String(200), default="")
    activo = Column(Boolean, default=True)
    ultima_sincronizacion = Column(DateTime, nullable=True)
    auto_sync = Column(Boolean, default=False)
    sync_interval_minutos = Column(Integer, default=60)
    webhook_secret = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", backref="tiendanube_configs")


class TiendanubeSyncLog(Base):
    __tablename__ = "tiendanube_sync_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    tipo = Column(String(50), nullable=False)
    estado = Column(String(20), default="PENDIENTE")
    productos_descargados = Column(Integer, default=0)
    productos_actualizados = Column(Integer, default=0)
    productos_creados = Column(Integer, default=0)
    errores = Column(Text, default="")
    detalle = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class TiendanubeProductMap(Base):
    __tablename__ = "tiendanube_product_map"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    tiendanube_product_id = Column(Integer, nullable=False)
    tiendanube_variant_id = Column(Integer, nullable=True)
    ultima_sincronizacion = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", backref="tiendanube_maps")


# ─── Contabilidad (Partida Doble) ──────────────────────────

class AccountingEntry(Base):
    __tablename__ = "accounting_entries"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    fecha = Column(Date, default=date.today)
    numero_asiento = Column(String(50), default="")
    concepto = Column(String(300), nullable=False)
    debe = Column(Numeric(12, 2), default=0)
    haber = Column(Numeric(12, 2), default=0)
    cuenta_contable = Column(String(200), nullable=False)
    referencia_id = Column(Integer, nullable=True)
    referencia_tipo = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="accounting_entries")
