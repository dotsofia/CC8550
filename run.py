import json
import os
import logging
from flask import Flask
from app.repo import SqliteRepo
from app.service import AnimeService
from app.web import register_routes, register_error_handlers

DEFAULT_CFG = {
    "database": "data/anime.db",
    "debug": True,
    "host": "127.0.0.1",
    "port": 5000,
    "logging_level": "INFO"
}

def load_config(path="config.json"):
    if not os.path.exists(path):
        print("config.json not found — using defaults:", DEFAULT_CFG)
        return DEFAULT_CFG
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print("Failed to read config.json:", e, " — using defaults")
        return DEFAULT_CFG
    merged = DEFAULT_CFG.copy()
    merged.update(cfg)
    return merged

cfg = load_config()

def configure_logging(level_name: str):
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # quieter werkzeug when not debugging
    logging.getLogger("werkzeug").setLevel(logging.WARNING if not cfg.get("debug") else logging.INFO)

def create_app():
    configure_logging(cfg.get("logging_level", "INFO"))
    logger = logging.getLogger(__name__)
    logger.info("Starting app with config: %s", {k: v for k, v in cfg.items() if k != "database"})

    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-key")
    os.makedirs(os.path.dirname(cfg["database"]), exist_ok=True)
    repo = SqliteRepo(cfg["database"])
    service = AnimeService(repo)
    app.config["SERVICE"] = service

    register_routes(app, service)
    register_error_handlers(app)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host=cfg.get("host", "127.0.0.1"), port=cfg.get("port", 5000), debug=cfg.get("debug", True))

