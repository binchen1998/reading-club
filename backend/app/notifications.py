from __future__ import annotations

from sqlalchemy.orm import Session

from .cache_invalidate import invalidate_notif_list
from .display_name import leaderboard_display_name
from .models import Notification, User
from .notif_cache import invalidate_unread_count


def create_notification(
    db: Session,
    *,
    username: str,
    type: str,
    actor_username: str | None = None,
    ref_id: int | None = None,
    message: str = "",
) -> Notification | None:
    recipient = (username or "").strip()
    if not recipient:
        return None
    if actor_username and recipient == actor_username:
        return None
    text = (message or "").strip()
    if not text and actor_username:
        actor = db.get(User, actor_username)
        actor_name = leaderboard_display_name(actor, actor_username)
        mapping = {
            "follow": f"{actor_name} 关注了你",
            "comment": f"{actor_name} 评论了你的朗读",
            "wall_message": f"{actor_name} 在你的留言板留言",
            "like": f"{actor_name} 赞了你的朗读",
        }
        text = mapping.get(type, f"{actor_name} 发来一条消息")
    row = Notification(
        username=recipient,
        type=type,
        actor_username=actor_username,
        ref_id=ref_id,
        message=text[:500],
        is_read=False,
    )
    db.add(row)
    invalidate_unread_count(recipient)
    invalidate_notif_list(recipient)
    return row
