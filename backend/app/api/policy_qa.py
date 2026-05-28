from fastapi import APIRouter, Request
from ..models.schemas import PolicyQARequest, PolicyQAResponse
from ..services.policy_qa import answer_question

router = APIRouter()


@router.post("/policy-qa", response_model=PolicyQAResponse)
def policy_qa(payload: PolicyQARequest, request: Request):
    result = answer_question(
        question=payload.question,
        pinecone_index=request.app.state.pinecone_index,
        anthropic_client=request.app.state.anthropic_client,
    )
    return PolicyQAResponse(**result)
