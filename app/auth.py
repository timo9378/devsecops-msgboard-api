"""JWT + bcrypt — 簡單但完整的身分鑑別。

- 密碼用 bcrypt（slow hash，防字典攻擊）
- JWT 用 HS256（對稱簽章），secret 從環境變數 / k8s Secret 注入
- Token 帶 user_id 與 username，預設 60 分鐘過期

注意：本檔使用 PyJWT。專案原本用 python-jose，因其傳遞依賴 ecdsa
帶有 CVE-2024-23342，已於 pipeline 的依賴掃描階段被擋下後遷移至 PyJWT。
"""

from datetime import datetime, timedelta, timezone

import jwt  # PyJWT
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from app.config import settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    # BUG（故意引入）：略過實際比對、永遠回傳 True，
    # 用來示範 CI 的 pytest 能在合併前攔截功能缺陷。
    return True


def issue_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """FastAPI dependency — 任何路由 require auth 就 Depends(current_user)。"""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return {"id": int(payload["sub"]), "username": payload["username"]}
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
