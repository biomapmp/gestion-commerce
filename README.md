---
title: GestionCommerce
emoji: 🏪
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.40.0
app_file: app.py
pinned: false
license: mit
---

# 🏪 GestionCommerce

Plataforma de gestión integral para comercios.

## 🚀 Características

- **📊 Dashboard**: Panel con KPIs, gráficos de ventas diarias, flujo de caja y stock bajo
- **👥 Clientes**: Gestión completa de cartera de clientes
- **📦 Stock**: Control de inventario, categorías y movimientos
- **🧾 Ventas**: Registro de ventas, múltiples formas de pago, reportes diarios
- **💰 Flujo de Caja**: Control de ingresos y egresos
- **💸 Costos**: Gestión de gastos y costos operativos
- **📒 Contabilidad**: Sistema de partida doble con libro diario
- **📡 ARCA**: Integración con facturación electrónica (ex AFIP)
- **🏢 Multi-tenant**: Soporte para múltiples comercios

## 🛠️ Tecnologías

- **Frontend/Backend**: [Streamlit](https://streamlit.io/)
- **Base de Datos**: SQLite (SQLAlchemy ORM)
- **Gráficos**: Plotly
- **Despliegue**: Hugging Face Spaces

## 🚀 Despliegue en Hugging Face Spaces

1. Crear un Space en https://huggingface.co/new-space
2. Seleccionar SDK: **Streamlit**
3. Subir estos archivos o conectar el repositorio
4. El Space se configura automáticamente

### Variables de Entorno (opcional)

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | URL de base de datos | `sqlite:///data/gestioncommerce.db` |
| `SECRET_KEY` | Clave secreta para sesiones | (auto-generada) |
| `ARCA_ENABLED` | Habilitar integración ARCA | `false` |
| `ARCA_API_KEY` | API Key de ARCA | - |
| `ARCA_ENDPOINT` | Endpoint de ARCA | `https://api.arca.afip.gob.ar/v1` |

## 🧪 Credenciales Demo

- **Email**: admin@demo.com
- **Password**: admin123

## 📝 Licencia

MIT
