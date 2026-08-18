from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..cache_invalidate import invalidate_profile
from ..cache_keys import USER_ME
from ..db import get_db
from ..models import User
from ..page_cache import cache_get, cache_set

router = APIRouter(prefix="/api/users", tags=["users"])


def serialize_user(user: User) -> dict:
    return {
        "username": user.username,
        "nickname": user.nickname or user.username,
        "avatar": user.avatar or "",
        "bio": user.bio or "",
        "isGuest": user.username.startswith("888-"),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    key = USER_ME.format(username=user.username)
    cached = cache_get(key)
    if isinstance(cached, dict):
        return cached
    payload = serialize_user(user)
    cache_set(key, payload)
    return payload


class ProfileIn(BaseModel):
    nickname: str = ""
    bio: str = ""


@router.post("/me")
def update_me(payload: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.nickname.strip():
        user.nickname = payload.nickname.strip()[:50]
    user.bio = (payload.bio or "").strip()[:200]
    db.add(user)
    db.commit()
    db.refresh(user)
    invalidate_profile(user.username)
    return serialize_user(user)
