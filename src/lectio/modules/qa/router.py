from fastapi import APIRouter

from lectio.api.dependencies import (
    EmbedderDep,
    LLMDep,
    RerankerDep,
    SessionDep,
)
from lectio.modules.qa.schemas import AnswerResponse, QuestionRequest
from lectio.modules.qa.service import answer_question

router = APIRouter(
    prefix="/qa",
    tags=["Q&A"],
)


@router.post(
    "",
    response_model=AnswerResponse,
)
async def ask_endpoint(
    payload: QuestionRequest,
    db: SessionDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    llm: LLMDep,
) -> AnswerResponse:
    """Answer a question from lecture transcripts, citing the fragments used."""
    return await answer_question(
        db,
        embedder,
        reranker,
        llm,
        payload,
    )
