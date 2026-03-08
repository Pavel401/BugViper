from pydantic import BaseModel


class Source(BaseModel):
    path: str
    line_number: int | None = None
    name: str | None = None
    type: str | None = None  # "function" | "class" | "variable" | "file" | etc.


class AskRequest(BaseModel):
    question: str
    repo_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[Source] = []
