from pydantic import BaseModel, Field


class CommentIn(BaseModel):
    content: str = Field(default="", max_length=500)
    parent_id: int | None = None


class WallMessageIn(BaseModel):
    content: str = Field(default="", max_length=500)
    parent_id: int | None = None
