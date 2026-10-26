from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, Float, ForeignKey, Index, Integer, Text, Uuid
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lectio.db.base import Base

if TYPE_CHECKING:
    from lectio.models.lecture import Lecture

# BGE-M3 dense vectors. Changing the embedding model to one with another
# size needs a migration and a reindex.
EMBEDDING_DIM = 1024

TEXT_SEARCH_CONFIG = "russian"


class Chunk(Base):
    """Several consecutive segments; the unit of search."""

    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "ix_chunks_lecture_position",
            "lecture_id",
            "position",
            unique=True,
        ),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_chunks_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    lecture_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "lectures.id",
            ondelete="CASCADE",
        ),
    )

    position: Mapped[int] = mapped_column(
        Integer,
    )

    start_seconds: Mapped[float] = mapped_column(
        Float,
    )

    end_seconds: Mapped[float] = mapped_column(
        Float,
    )

    text: Mapped[str] = mapped_column(
        Text,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIM),
    )

    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            f"to_tsvector('{TEXT_SEARCH_CONFIG}', text)",
            persisted=True,
        ),
    )

    lecture: Mapped["Lecture"] = relationship(
        back_populates="chunks",
        lazy="raise",
    )
