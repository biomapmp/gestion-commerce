import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta


COLORS = {
    "primary": "#2563EB",
    "secondary": "#10B981",
    "danger": "#EF4444",
    "warning": "#F59E0B",
    "purple": "#8B5CF6",
    "pink": "#EC4899",
    "gray": "#6B7280",
}


def ventas_diarias_chart(
    df: pd.DataFrame, titulo: str = "Ventas Diarias"
) -> go.Figure:
    fig = go.Figure()

    if df.empty:
        fig.add_annotation(
            text="Sin datos para el período seleccionado",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        fig.update_layout(
            title=titulo,
            height=350,
            template="plotly_white",
        )
        return fig

    fig.add_trace(
        go.Bar(
            x=df["fecha"],
            y=df["total"],
            name="Ventas",
            marker_color=COLORS["primary"],
            text=df["total"].apply(lambda x: f"${x:,.0f}"),
            textposition="outside",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["fecha"],
            y=df["total"],
            mode="lines+markers",
            name="Tendencia",
            line=dict(color=COLORS["secondary"], width=2),
            marker=dict(size=6),
        )
    )

    fig.update_layout(
        title=titulo,
        xaxis_title="Fecha",
        yaxis_title="Total ($)",
        height=350,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def grafico_torta(df: pd.DataFrame, valores: str, nombres: str, titulo: str) -> go.Figure:
    fig = px.pie(
        df,
        values=valores,
        names=nombres,
        title=titulo,
        hole=0.4,
        color_discrete_sequence=[
            COLORS["primary"],
            COLORS["secondary"],
            COLORS["warning"],
            COLORS["danger"],
            COLORS["purple"],
            COLORS["pink"],
        ],
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=350, template="plotly_white")
    return fig


def flujo_caja_chart(
    ingresos: list, egresos: list, fechas: list, titulo: str = "Flujo de Caja"
) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=fechas,
            y=ingresos,
            name="Ingresos",
            marker_color=COLORS["secondary"],
        )
    )
    fig.add_trace(
        go.Bar(
            x=fechas,
            y=egresos,
            name="Egresos",
            marker_color=COLORS["danger"],
        )
    )

    fig.update_layout(
        title=titulo,
        barmode="group",
        height=350,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def indicador_kpi(valor: float, titulo: str, fmt: str = "${:,.0f}", delta: float | None = None):
    fig = go.Figure(
        go.Indicator(
            mode="number" + ("" if delta is None else "+delta"),
            value=valor,
            title={"text": titulo},
            number={"prefix": "$ " if "$" in fmt else "", "suffix": ""},
            delta={"reference": delta, "valueformat": ".0f"} if delta else None,
        )
    )
    fig.update_layout(height=150, template="plotly_white")
    return fig


def stock_bajo_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if df.empty:
        fig.add_annotation(
            text="Todo en stock suficiente",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
        )
        fig.update_layout(height=300, template="plotly_white")
        return fig

    fig.add_trace(
        go.Bar(
            x=df["nombre"],
            y=df["stock_actual"],
            name="Stock Actual",
            marker_color=COLORS["warning"],
        )
    )
    fig.add_trace(
        go.Bar(
            x=df["nombre"],
            y=df["stock_minimo"],
            name="Stock Mínimo",
            marker_color=COLORS["danger"],
        )
    )

    fig.update_layout(
        title="Productos con Stock Bajo",
        barmode="group",
        height=300,
        template="plotly_white",
    )
    return fig
