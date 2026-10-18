import os
import yaml
import jwt
from pathlib import Path
from typing import Any, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="JWT Verifier + Effective Config")

# ---------------------------------------------------------------
# CORS
# ---------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Type"],
)

# ---------------------------------------------------------------
# JWT values
# ---------------------------------------------------------------
ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-7adcqonz.apps.exam.local"

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""


class VerifyRequest(BaseModel):
    token: str


def reject():
    return JSONResponse(status_code=401, content={"valid": False})


# ---------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------
DEFAULTS = {
    "port": 8000,
    "workers": 2,
    "debug": False,
    "log_level": "info",
    "api_key": "",
}


def load_yaml_config(env: str) -> dict:
    """Load config.<env>.yaml from the current directory."""
    path = Path(f"config.{env}.yaml")
    if path.exists():
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
    return {}


def load_dotenv() -> dict:
    """Parse .env file manually (simple key=value)."""
    path = Path(".env")
    result = {}
    if path.exists():
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    result[key] = value
        except Exception:
            pass
    return result


def load_os_env() -> dict:
    """Read OS env vars with APP_ prefix."""
    result = {}
    for key, value in os.environ.items():
        if key.startswith("APP_"):
            config_key = key[4:].lower()  # APP_PORT -> port
            result[config_key] = value
    return result


def coerce_value(key: str, value: Any) -> Any:
    """Apply type coercion based on the default's type."""
    if key not in DEFAULTS:
        return value

    target = DEFAULTS[key]

    if isinstance(target, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    if isinstance(target, int):
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return int(value)

    if isinstance(target, float):
        return float(value)

    if isinstance(target, str):
        return str(value)

    return value


def parse_set_params(request: Request) -> dict:
    """Parse ?set=key=value from query params, supporting multiple set params."""
    result = {}
    set_values = request.query_params.getlist("set")
    for item in set_values:
        if "=" in item:
            key, _, value = item.partition("=")
            result[key.strip()] = value.strip()
    return result


def mask_api_key(value: str) -> str:
    """Mask api_key: keep first 4 chars, mask the rest."""
    if not value:
        return "****"
    if len(value) <= 4:
        return "****"
    return value[:4] + "****"


# ---------------------------------------------------------------
# POST /verify
# ---------------------------------------------------------------
@app.post("/verify")
async def verify(payload: VerifyRequest):
    token = payload.token.strip()
    if not token:
        return reject()

    try:
        claims = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["exp", "iss", "aud"]},
        )
    except Exception:
        return reject()

    aud_claim = claims.get("aud", "")
    if isinstance(aud_claim, list):
        aud_claim = aud_claim[0] if aud_claim else ""

    return {
        "valid": True,
        "email": claims.get("email", ""),
        "sub": claims.get("sub", ""),
        "aud": aud_claim,
    }


# ---------------------------------------------------------------
# GET /effective-config
# ---------------------------------------------------------------
@app.get("/effective-config")
async def effective_config(request: Request):
    # Determine environment (default to "dev")
    env = os.environ.get("APP_ENV", "dev")

    # Merge layers: defaults → config.<env>.yaml → .env → OS env → set params
    merged = dict(DEFAULTS)
    merged.update(load_yaml_config(env))
    merged.update(load_dotenv())
    merged.update(load_os_env())
    merged.update(parse_set_params(request))

    # Apply type coercion
    result = {}
    for key in DEFAULTS:
        if key in merged:
            try:
                result[key] = coerce_value(key, merged[key])
            except (ValueError, TypeError):
                result[key] = DEFAULTS[key]

    # Mask api_key in response
    if "api_key" in result:
        result["api_key"] = mask_api_key(result["api_key"])

    return result


# ---------------------------------------------------------------
# GET / — health
# ---------------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ok"}
