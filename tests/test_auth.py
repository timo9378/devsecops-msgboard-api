"""自動化測試 — 針對 auth.py 的純函式（不依賴 DB）。

涵蓋：
  1. 密碼 bcrypt 雜湊後可被正確驗證
  2. 錯誤密碼會被拒絕（這條是 demo「故意改壞程式 → 測試沒過」的目標）
  3. 簽出的 JWT 能用同一把 secret 解回正確的 claims
"""

import jwt  # PyJWT
import pytest

from app.auth import hash_password, verify_password, issue_token
from app.config import settings


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-pw")
    assert hashed != "s3cret-pw"          # 不能是明文
    assert verify_password("s3cret-pw", hashed) is True


def test_wrong_password_rejected():
    hashed = hash_password("correct-horse")
    assert verify_password("wrong-password", hashed) is False


def test_issue_token_roundtrip():
    token = issue_token(42, "alice")
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    assert payload["sub"] == "42"
    assert payload["username"] == "alice"
    assert "exp" in payload


def test_tampered_token_rejected():
    token = issue_token(1, "bob")
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token + "tamper", settings.jwt_secret,
                   algorithms=[settings.jwt_algorithm])
