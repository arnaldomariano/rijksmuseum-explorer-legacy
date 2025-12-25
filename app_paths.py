# app_paths.py
from pathlib import Path

# ============================================================
# 📌 NEXT STEPS (keep this block)
# ============================================================
# 1) Renomear archive → experiments (opcional, impacto baixo)
# 2) Criar pasta data/ e mover JSONs
# 3) Centralizar caminhos aqui no app_paths.py
# 4) Atualizar imports de paths em app.py / My_Selection / PDF_Setup
# 5) Revisar estratégia de API key (secrets/env)
# 6) Depois: refino visual e PDF catálogo v1
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

# ============================================================
# Analytics (local, anonymous)
# ============================================================
ANALYTICS_DIR = DATA_DIR / "analytics"
ANALYTICS_EVENTS_FILE = ANALYTICS_DIR / "analytics_events.json"

# guarantee directories exist (safe)
ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

# Arquivos de persistência local
FAV_FILE = DATA_DIR / "favorites.json"
NOTES_FILE = DATA_DIR / "notes.json"
PDF_META_FILE = DATA_DIR / "pdf_meta.json"

# Assets
HERO_IMAGE_PATH = ASSETS_DIR / "rijks_header.jpg"

# Analytics paths
ANALYTICS_DIR = DATA_DIR / "analytics"
ANALYTICS_FILE = ANALYTICS_DIR / "analytics_events.jsonl"
ANALYTICS_CONFIG_FILE = ANALYTICS_DIR / "analytics_config.json"