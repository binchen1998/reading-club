import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..gen_jobs import job_payload, submit_job
from ..lesson_worker import start_lesson_worker
from ..models import User

router = APIRouter(prefix="/api/teaching", tags=["teaching"])


class ChatMessageIn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatIn(BaseModel):
    book_title: str = ""
    current_page_number: int | None = None
    current_english: str = ""
    current_script: str = ""
    student_text: str = Field(..., min_length=1, max_length=2000)
    messages: list[ChatMessageIn] = Field(default_factory=list)


@router.post("/chat")
def teaching_chat(payload: ChatIn, user: User = Depends(get_current_user)):
    del user
    start_lesson_worker()
    job = submit_job(
        "chat",
        f"chat:{uuid.uuid4().hex}",
        {
            "book_title": payload.book_title,
            "student_text": payload.student_text,
            "current_page": payload.current_page_number,
            "current_english": payload.current_english,
            "current_script": payload.current_script,
            "messages": [item.model_dump() for item in payload.messages],
        },
        priority=0,
    )
    return job_payload(job)
