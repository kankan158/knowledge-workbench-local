from typing import Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class DocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    source: Optional[str] = Field(default=None, max_length=500)


class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    source: Optional[str] = None
    score: Optional[float] = None


class UploadResponse(BaseModel):
    filename: str
    title: str
    chunks: int
    documents: list


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)
    search_type: str = Field(default="hybrid")
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    folder_filter: Optional[str] = Field(default=None, max_length=500)
    history: list[ChatMessage] = Field(default_factory=list)
    selected_document_ids: list[str] = Field(default_factory=list)
    api_key: Optional[str] = Field(default=None, max_length=5000)


class WorkspaceStateResponse(BaseModel):
    folders: list = Field(default_factory=list)
    tags: list = Field(default_factory=list)
    docMeta: dict = Field(default_factory=dict)


class WorkspaceStatePatch(BaseModel):
    folders: Optional[list] = None
    tags: Optional[list] = None
    docMeta: Optional[dict] = None


class AskResponse(BaseModel):
    answer: str
    sources: list
