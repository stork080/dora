import jwt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any

app = FastAPI(title="JWT Verifier")

# ---------------------------------------------------------------
# CORS — required so the browser grader can call /verify
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
# Assigned values
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
# Endpoint
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


@app.get("/")
async def root():
    return {"status": "ok"}
