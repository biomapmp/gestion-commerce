from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
import pandas as pd


def formato_moneda(valor: Decimal | float | int | None, moneda: str = "ARS") -> str:
    if valor is None:
        valor = 0
    return f"$ {float(valor):,.2f}"


def formato_fecha(fecha: date | datetime | None) -> str:
    if fecha is None:
        return ""
    if isinstance(fecha, datetime):
        return fecha.strftime("%d/%m/%Y %H:%M")
    return fecha.strftime("%d/%m/%Y")


def formato_fecha_corta(fecha: date | None) -> str:
    if fecha is None:
        return ""
    return fecha.strftime("%d/%m/%Y")


def parse_decimal(valor: Any) -> Decimal:
    try:
        return Decimal(str(valor))
    except (ValueError, TypeError):
        return Decimal("0")


def calcular_iva(monto: Decimal, tasa: Decimal = Decimal("0.21")) -> Decimal:
    return (monto * tasa).quantize(Decimal("0.01"))


def generar_numero_comprobante(tipo: str, numero: int) -> str:
    return f"{tipo}-{numero:08d}"


def today() -> date:
    return date.today()


def primer_dia_mes() -> date:
    hoy = today()
    return date(hoy.year, hoy.month, 1)


def ultimo_dia_mes() -> date:
    hoy = today()
    if hoy.month == 12:
        return date(hoy.year, 12, 31)
    return date(hoy.year, hoy.month + 1, 1) - timedelta(days=1)


DIAS_SEMANA = [
    "Lunes", "Martes", "Miércoles", "Jueves",
    "Viernes", "Sábado", "Domingo",
]

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def obtener_metricas_dashboard(session, tenant_id: int, fecha_desde, fecha_hasta):
    from database.models import Sale, CashFlow, Expense, Product, Client

    ventas = (
        session.query(Sale)
        .filter(
            Sale.tenant_id == tenant_id,
            Sale.fecha.between(fecha_desde, fecha_hasta),
        )
        .all()
    )

    total_ventas = sum(float(v.total) for v in ventas)
    cantidad_ventas = len(ventas)

    flujo = (
        session.query(CashFlow)
        .filter(
            CashFlow.tenant_id == tenant_id,
            CashFlow.fecha.between(fecha_desde, fecha_hasta),
        )
        .all()
    )
    ingresos = sum(float(f.monto) for f in flujo if f.tipo.value == "INGRESO")
    egresos = sum(float(f.monto) for f in flujo if f.tipo.value == "EGRESO")

    gastos = (
        session.query(Expense)
        .filter(
            Expense.tenant_id == tenant_id,
            Expense.fecha.between(fecha_desde, fecha_hasta),
        )
        .all()
    )
    total_gastos = sum(float(g.monto_total) for g in gastos)

    total_productos = (
        session.query(Product).filter(Product.tenant_id == tenant_id).count()
    )
    total_clientes = (
        session.query(Client).filter(Client.tenant_id == tenant_id).count()
    )

    productos_bajo_stock = (
        session.query(Product)
        .filter(
            Product.tenant_id == tenant_id,
            Product.activo == True,
            Product.stock_actual <= Product.stock_minimo,
        )
        .count()
    )

    ventas_df = pd.DataFrame(
        [
            {
                "fecha": v.fecha,
                "total": float(v.total),
                "comprobante": v.comprobante.value if v.comprobante else "",
                "cliente": v.client.nombre if v.client else "Consumidor Final",
            }
            for v in ventas
        ]
    )

    if not ventas_df.empty:
        ventas_diarias = (
            ventas_df.groupby("fecha")["total"]
            .agg(["sum", "count"])
            .reset_index()
        )
        ventas_diarias.columns = ["fecha", "total", "cantidad"]
    else:
        ventas_diarias = pd.DataFrame(columns=["fecha", "total", "cantidad"])

    return {
        "total_ventas": total_ventas,
        "cantidad_ventas": cantidad_ventas,
        "ingresos": ingresos,
        "egresos": egresos,
        "saldo_neto": ingresos - egresos,
        "total_gastos": total_gastos,
        "total_productos": total_productos,
        "total_clientes": total_clientes,
        "productos_bajo_stock": productos_bajo_stock,
        "ventas_diarias": ventas_diarias,
        "margen_bruto": total_ventas - total_gastos if total_ventas else 0,
    }
