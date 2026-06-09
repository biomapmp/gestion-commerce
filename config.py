import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "GestionCommerce"
APP_ICON = "🏪"
ADMIN_EMAIL = "admin@gestioncommerce.com"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/gestioncommerce.db")

SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-en-produccion-secret-key-2024")

ARCA_ENABLED = os.getenv("ARCA_ENABLED", "false").lower() == "true"
ARCA_API_KEY = os.getenv("ARCA_API_KEY", "")
ARCA_ENDPOINT = os.getenv("ARCA_ENDPOINT", "https://api.arca.afip.gob.ar/v1")
