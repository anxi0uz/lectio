from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from lectio.api.dependencies import (
    EmbedderDep,
    LLMDep,
    RerankerDep,
    SessionDep,
)
from lectio.modules.qa.schemas import AnswerResponse, QuestionRequest
from lectio.modules.qa.service import (
    answer_question,
    retrieve_context,
    stream_answer,
)

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


@router.post(
    "/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def ask_stream_endpoint(
    payload: QuestionRequest,
    db: SessionDep,
    embedder: EmbedderDep,
    reranker: RerankerDep,
    llm: LLMDep,
) -> StreamingResponse:
    """Same answer as POST /qa, streamed as server-sent events.

    Events: `sources` (list of search hits), `delta` ({text}) many times,
    then `done` or `error` ({detail, code}).
    """
    # Retrieval runs here, while the request's database session is open; the
    # stream itself only talks to the language model.
    hits = await retrieve_context(db, embedder, reranker, payload)

    return StreamingResponse(
        stream_answer(llm, payload, hits),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
