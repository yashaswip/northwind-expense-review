from fastapi import APIRouter

from app.config import settings
from app.schemas import HealthResponse, PolicyChatRequest, PolicyChatResponse
from app.services.policy_chat import policy_chat
from app.services.policy_index import policy_index

router = APIRouter(tags=["policy"])


@router.get("/api/health", response_model=HealthResponse)
def health():
    try:
        count = policy_index.ensure_indexed()
    except Exception:
        count = policy_index.chunk_count
    return HealthResponse(
        status="ok",
        policies_indexed=count,
        openai_configured=bool(settings.openai_api_key),
    )


@router.post("/api/policy/ask", response_model=PolicyChatResponse)
def ask_policy(payload: PolicyChatRequest):
    return policy_chat.ask(payload.question)


@router.post("/api/policy/reindex")
def reindex_policies():
    policies_dir = settings.resolve_path(settings.policies_dir)
    count = policy_index.ingest_directory(policies_dir)
    return {"chunks_indexed": count}
