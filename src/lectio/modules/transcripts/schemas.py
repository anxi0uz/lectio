from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    start_seconds: float
    end_seconds: float
    text: str
