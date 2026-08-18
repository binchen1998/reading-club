from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..gen_jobs import get_job, iter_job_sse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}/events")
def job_events(job_id: str):
    if not get_job(job_id):
        raise HTTPException(404, "任务不存在")
    return StreamingResponse(
        iter_job_sse(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
