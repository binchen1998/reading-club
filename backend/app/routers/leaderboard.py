from urllib.parse import unquote

from fastapi import APIRouter, Header, Query

from ..leaderboard_worker import (
    get_cached_honor,
    get_cached_rise,
    get_cached_talent,
    my_rank_from_entries,
    week_range_cn,
)

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


def _username_from_header(x_username: str | None) -> str:
    return unquote(x_username or "").strip()[:50]


@router.get("")
def talent_leaderboard(
    limit: int = Query(50, ge=1, le=200),
    x_username: str | None = Header(None, alias="X-Username"),
):
    cached = get_cached_talent()
    if cached is None:
        result = {"entries": [], "cached": False}
    else:
        entries, updated_at = cached
        result = {"entries": entries[:limit], "cached": True, "cachedAt": updated_at}
    username = _username_from_header(x_username)
    if username:
        result["myRank"] = my_rank_from_entries(result["entries"], username)
    return result


@router.get("/honor")
def honor_leaderboard(
    limit: int = Query(50, ge=1, le=200),
    x_username: str | None = Header(None, alias="X-Username"),
):
    cached = get_cached_honor()
    if cached is None:
        result = {"entries": [], "cached": False}
    else:
        entries, updated_at = cached
        result = {"entries": entries[:limit], "cached": True, "cachedAt": updated_at}
    username = _username_from_header(x_username)
    if username:
        result["myRank"] = my_rank_from_entries(result["entries"], username)
    return result


@router.get("/rise")
def rise_leaderboard(
    limit: int = Query(50, ge=1, le=200),
    x_username: str | None = Header(None, alias="X-Username"),
):
    cached = get_cached_rise()
    if cached is None:
        result = {"entries": [], "weekLabel": week_range_cn()[2], "cached": False}
    else:
        payload, updated_at = cached
        result = {
            "entries": (payload.get("entries") or [])[:limit],
            "weekLabel": payload.get("weekLabel") or week_range_cn()[2],
            "cached": True,
            "cachedAt": updated_at,
        }
    username = _username_from_header(x_username)
    if username:
        result["myRank"] = my_rank_from_entries(result["entries"], username)
    return result
