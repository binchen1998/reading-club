import base64
import hashlib
import hmac
import json
import time
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import ADMIN_PASSWORD, ADMIN_USERNAME, JWT_SECRET
from .db import get_db
from .models import User


def sanitize_username(raw: str) -> str:
    return unquote(raw or "").strip()[:50]


def is_guest(username: str) -> bool:
    return (username or "").startswith("888-")


def get_or_create_user(db: Session, username: str) -> User:
    user = db.get(User, username)
    if user is not None:
        return user
    user = User(username=username, nickname=username)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        user = db.get(User, username)
        if user is None:
            raise
        return user


def get_current_user(
    x_username: str | None = Header(None, alias="X-Username"),
    db: Session = Depends(get_db),
) -> User:
    username = sanitize_username(x_username or "")
    if not username:
        raise HTTPException(status_code=401, detail="缺少用户身份（X-Username）")
    return get_or_create_user(db, username)


def assert_user_not_muted(user: User) -> None:
    if user is not None and bool(getattr(user, "is_muted", False)):
        raise HTTPException(status_code=403, detail="账号已被禁言")


def check_admin_credentials(username: str, password: str) -> bool:
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def create_admin_token() -> str:
    payload = _b64(json.dumps({"sub": "admin", "exp": int(time.time()) + 365 * 86400}).encode())
    sig = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_admin_token(token: str) -> bool:
    try:
        payload, sig = token.split(".", 1)
        expect = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return False
        data = json.loads(base64.urlsafe_b64decode(payload + "=="))
        return data.get("sub") == "admin" and int(data.get("exp") or 0) > time.time()
    except Exception:
        return False


def require_admin(authorization: str | None = Header(None)) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要管理员权限")
    if not verify_admin_token(authorization[7:]):
        raise HTTPException(status_code=401, detail="管理员令牌无效或已过期")
    return True


def get_optional_user(
    x_username: str | None = Header(None, alias="X-Username"),
    db: Session = Depends(get_db),
) -> User | None:
    username = sanitize_username(x_username or "")
    if not username:
        return None
    return get_or_create_user(db, username)
