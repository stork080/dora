import os
from pathlib import Path
from typing import List

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# Your assigned OS-level layer (used if not set in Vercel dashboard)
os.environ.setdefault("APP_PORT", "8688")
os.environ.setdefault("APP_DEBUG", "true")

APP_ENV = os.environ.get("APP_ENV", "development")
BASE = Path(__file__).parent

DEFAULTS = {"port": 8000, "workers": 1, "debug": False,
            "log_level": "info", "api_key": "default-secret-000"}

YAML_FALLBACK = {"port": 8250, "api_key": "key-re8mwl5lc0"}
DOTENV_FALLBACK = "APP_DEBUG=false\nAPP_LOG_LEVEL=info\n"

ALIASES = {"num_workers": "workers"}
TRUE = {"true", "1", "yes", "on"}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


def norm_key(k: str) -> str:
    k = k.strip().lower()
    if k.startswith("app_"):
        k = k[4:]
    return ALIASES.get(k, k)


def coerce(key, val):
    if key in ("port", "workers"):
        return int(str(val).strip())
    if key == "debug":
        return str(val).strip().lower() in TRUE
    return str(val)


def load_yaml():
    p = BASE / f"config.{APP_ENV}.yaml"
    try:
        import yaml
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    except Exception:
        pass
    return YAML_FALLBACK


def load_dotenv():
    p = BASE / ".env"
    text = p.read_text() if p.exists() else DOTENV_FALLBACK
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[norm_key(k)] = v.strip().strip('"').strip("'")
    return out


def load_os_env():
    out = {}
    for k, v in os.environ.items():
        if k.startswith("APP_") and k != "APP_ENV":
            out[norm_key(k)] = v
    return out


@app.get("/effective-config")
def effective_config(set: List[str] = Query(default=[])):
    merged = dict(DEFAULTS)
    for layer in (load_yaml(), load_dotenv(), load_os_env()):
        for k, v in layer.items():
            merged[norm_key(str(k))] = v

    for item in set:
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        merged[norm_key(k)] = v

    result = {}
    for k, v in merged.items():
        try:
            result[k] = coerce(k, v)
        except (ValueError, TypeError):
            result[k] = coerce(k, DEFAULTS.get(k, 0)) if k in ("port", "workers") else v
    result["api_key"] = "****"
    return result
