from __future__ import annotations
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
import traceback
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .rag import DeepSeekRAG
from .schemas import (
    AskRequest,
    AskResponse,
    DocumentIn,
    SearchResult,
    UploadResponse,
    WorkspaceStatePatch,
    WorkspaceStateResponse,
)
from .store import KnowledgeStore, StoredDocument
from .workspace_state import WorkspaceStateStore

ROOT_DIR = Path(__file__).resolve().parents[2]
STORE_DIR = ROOT_DIR / "data" / "chroma"
STORE = KnowledgeStore(STORE_DIR)
WORKSPACE_STATE = WorkspaceStateStore(ROOT_DIR / "data" / "workspace_state.json")
RAG = DeepSeekRAG()

DEMO_DOCUMENTS = [
    StoredDocument(
        id="intro-local-first",
        title="Local-first architecture",
        content="This app keeps documents on your machine, performs local search, and exposes a small API for the Vue UI.",
        source="seed://architecture",
    ),
    StoredDocument(
        id="intro-rag",
        title="RAG pipeline",
        content="The retrieval flow is document ingestion, chunking, embedding, vector search, and answer assembly with citations.",
        source="seed://pipeline",
    ),
    StoredDocument(
        id="intro-vue",
        title="Vue frontend",
        content="The frontend shows a search bar, a document panel, and a concise answer card so the project feels like a real product.",
        source="seed://frontend",
    ),
]

app = FastAPI(title="Knowledge Workbench", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    # Allow local frontend hosts across dynamic Vite dev/preview ports (e.g. 5173/5174/4173).
    allow_origins=["http://127.0.0.1", "http://localhost"],
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORE.seed(DEMO_DOCUMENTS)


def _dedupe_documents_by_group(items: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for item in items:
        title = str(item.get("title") or "Untitled")
        base_title = title
        if "[" in title and title.endswith("]"):
            base_title = title.rsplit("[", 1)[0].strip()
        key = f"{str(item.get('source') or '')}||{base_title}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "documents": STORE.count()}


@app.get("/documents", response_model=list[SearchResult])
def list_documents() -> list[SearchResult]:
    items = STORE.list_all()
    return [SearchResult(**item) for item in items]


@app.delete("/documents/{document_id}")
def delete_document(document_id: str) -> dict[str, str]:
    STORE.delete_document(document_id)
    return {"status": "ok", "deleted": document_id}


@app.get("/workspace/state", response_model=WorkspaceStateResponse)
def get_workspace_state() -> WorkspaceStateResponse:
    return WorkspaceStateResponse(**WORKSPACE_STATE.read_state())


@app.patch("/workspace/state", response_model=WorkspaceStateResponse)
def patch_workspace_state(payload: WorkspaceStatePatch) -> WorkspaceStateResponse:
    updated = WORKSPACE_STATE.update_state(payload.dict(exclude_none=True))
    return WorkspaceStateResponse(**updated)


@app.post("/documents", response_model=SearchResult)
def add_document(document: DocumentIn) -> SearchResult:
    new_document = StoredDocument(
        id=str(uuid4()),
        title=document.title,
        content=document.content,
        source=document.source,
    )
    STORE.upsert(new_document)
    return SearchResult(
        id=new_document.id,
        title=new_document.title,
        content=new_document.content,
        source=new_document.source,
        score=1.0,
    )


@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    source: Optional[str] = Form(default=None),
    chunk_size: int = Form(default=1200),
    overlap: int = Form(default=150),
) -> UploadResponse:
    try:
        raw_content = await file.read()
        if not raw_content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        if chunk_size < 1:
            raise HTTPException(status_code=400, detail="chunk_size must be at least 1.")
        if overlap < 0:
            raise HTTPException(status_code=400, detail="overlap must be non-negative.")
        if overlap >= chunk_size:
            raise HTTPException(status_code=400, detail="overlap must be smaller than chunk_size.")

        try:
            content = STORE.extract_text_from_file(raw_content, file.filename or "document")
        except (ValueError, ImportError) as e:
            raise HTTPException(status_code=400, detail=str(e))

        if not content.strip():
            raise HTTPException(status_code=400, detail="No text could be extracted from the file.")

        file_title = (title or Path(file.filename or "uploaded-document").stem).strip() or "uploaded-document"
        stored_documents = STORE.ingest_text(
            base_id=uuid4().hex,
            title=file_title,
            content=content,
            source=source or f"file://{file.filename or file_title}",
            chunk_size=chunk_size,
            overlap=overlap,
        )
        return UploadResponse(
            filename=file.filename or file_title,
            title=file_title,
            chunks=len(stored_documents),
            documents=[
                SearchResult(
                    id=document.id,
                    title=document.title,
                    content=document.content,
                    source=document.source,
                    score=1.0,
                )
                for document in stored_documents
            ],
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/search", response_model=list[SearchResult])
def search(
    q: str,
    top_k: int = 5,
    min_score: float = 0.05,
    search_type: str = "hybrid",
    alpha: float = 0.5,
    folder_filter: Optional[str] = None,
    folder: Optional[str] = None,
) -> list[SearchResult]:
    effective_folder_filter = folder_filter or folder
    items = STORE.search(
        q,
        top_k=top_k,
        min_score=min_score,
        include_full=False,
        search_type=search_type,
        alpha=alpha,
        folder_filter=effective_folder_filter,
    )
    return [SearchResult(**item) for item in items]


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    if payload.selected_document_ids:
        selected_documents = STORE.get_documents_by_ids(payload.selected_document_ids)
    else:
        selected_documents = []

    # For synthesis we want the full chunk content; use a low threshold but keep preview filtering in search API
    matches = selected_documents or STORE.search(
        payload.question,
        top_k=payload.top_k,
        min_score=0.0,
        include_full=True,
        search_type=payload.search_type,
        alpha=payload.alpha,
        folder_filter=payload.folder_filter,
    )
    matches = _dedupe_documents_by_group(matches)
    if not matches:
        return AskResponse(
            answer="No relevant documents were found yet. Add documents to your knowledge base first.",
            sources=[],
        )

    answer = RAG.generate_answer(
        payload.question,
        matches,
        history=[message.dict() for message in payload.history],
        api_key=payload.api_key,
    )
    return AskResponse(
        answer=answer,
        sources=[SearchResult(**item) for item in matches],
    )
