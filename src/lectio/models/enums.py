from enum import StrEnum


class LectureStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    INDEXING = "indexing"
    SUMMARIZING = "summarizing"
    READY = "ready"
    FAILED = "failed"


class SourceType(StrEnum):
    UPLOAD = "upload"
    URL = "url"


# Statuses after which the transcript and search index exist.
SEARCHABLE_STATUSES = frozenset(
    {
        LectureStatus.SUMMARIZING,
        LectureStatus.READY,
    }
)

IN_PROGRESS_STATUSES = frozenset(
    {
        LectureStatus.PENDING,
        LectureStatus.DOWNLOADING,
        LectureStatus.EXTRACTING_AUDIO,
        LectureStatus.TRANSCRIBING,
        LectureStatus.INDEXING,
        LectureStatus.SUMMARIZING,
    }
)
