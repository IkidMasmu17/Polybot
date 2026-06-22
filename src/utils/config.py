"""Configuration management — loads config.yaml and .env."""
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Config:
    """Singleton configuration manager combining YAML + environment variables."""

    _instance = None

    def __init__(self):
        if Config._instance is not None:
            raise RuntimeError("Use Config.get() instead of Config()")
        self._data: dict[str, Any] = {}
        self._load()

    @classmethod
    def get(cls) -> "Config":
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance._data = {}
            cls._instance._load()
        return cls._instance

    def _load(self):
        # Load .env (lowest priority — shell env wins)
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)

        # Load config.yaml
        config_path = PROJECT_ROOT / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

        # Override with environment variables for certain keys
        self._data.setdefault("telegram", {})
        owner_id = os.getenv("TELEGRAM_OWNER_ID")
        if owner_id:
            self._data["telegram"]["allowed_user_ids"] = [int(owner_id)]

        self._data.setdefault("database", {})
        db_path = os.getenv("DATABASE_PATH")
        if db_path:
            self._data["database"]["path"] = db_path

    # ---- Convenience accessors ----

    @property
    def scanner(self) -> dict:
        return self._data.get("scanner", {})

    @property
    def wallet_tracker(self) -> dict:
        return self._data.get("wallet_tracker", {})

    @property
    def scalping(self) -> dict:
        return self._data.get("scalping", {})

    @property
    def risk(self) -> dict:
        return self._data.get("risk", {})

    @property
    def copy_trade(self) -> dict:
        return self._data.get("copy_trade", {})

    @property
    def telegram(self) -> dict:
        return self._data.get("telegram", {})

    @property
    def logging_config(self) -> dict:
        return self._data.get("logging", {})

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def get_tier_config(self) -> dict:
        tier_name = self._data.get("wallet_tracker", {}).get("tier", "STANDAR")
        tiers = self._data.get("wallet_tracker", {}).get("tiers", {})
        return tiers.get(tier_name, tiers.get("STANDAR", {}))

    def get_sizing_config(self) -> dict:
        return self._data.get("scalping", {}).get("sizing", {})

    def get_drawdown_steps(self) -> list:
        return self._data.get("risk", {}).get("drawdown_reduction", {}).get("steps", [])

    @property
    def data(self) -> dict:
        return self._data


# Module-level convenience
def get_config() -> Config:
    return Config.get()
