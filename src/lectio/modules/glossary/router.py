from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from lectio.api.dependencies import SessionDep
from lectio.modules.glossary.schemas import GlossaryEntry
from lectio.modules.glossary.service import get_glossary

router = APIRouter(
    prefix="/glossary",
    tags=["Glossary"],
)


@router.get(
    "",
    response_model=list[GlossaryEntry],
)
async def glossary_endpoint(
    db: SessionDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    course_id: UUID | None = None,
) -> list[GlossaryEntry]:
    """Key terms of every lecture, alphabetical, each with its lectures."""
    return await get_glossary(db, q, course_id)
