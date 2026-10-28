from typing import TYPE_CHECKING

from fastapi import status

from lectio.core.exceptions import ConflictError, DomainError, NotFoundError

if TYPE_CHECKING:
    from lectio.models import Lecture


class LectureNotFoundError(NotFoundError):
    default_detail = "Lecture not found"


class LectureNotReadyError(ConflictError):
    default_detail = "Lecture is still being processed"


class LectureBusyError(ConflictError):
    default_detail = "Lecture is already being processed"


class DuplicateLectureError(ConflictError):
    default_detail = "This video has already been added"
    code = "lecture_duplicate"

    def __init__(self, existing: "Lecture") -> None:
        super().__init__(
            extra={
                "lecture_id": str(existing.id),
                "title": existing.title,
            },
        )
        self.lecture_id = existing.id


class VideoNotAvailableError(NotFoundError):
    default_detail = "Video file is not available yet"


class ThumbnailNotAvailableError(NotFoundError):
    default_detail = "Lecture has no video frame to show"


class UnsupportedMediaError(DomainError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = "Unsupported file type"
    code = "media_unsupported_format"


class FileTooLargeError(DomainError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    default_detail = "File is too large"
    code = "media_too_large"


class InvalidMediaError(DomainError):
    """The file or page was accepted but its content cannot be a lecture."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    default_detail = "Media cannot be processed"


class UnreadableMediaError(InvalidMediaError):
    default_detail = "File is damaged or is not a media file"
    code = "media_unreadable"


class NoAudioError(InvalidMediaError):
    default_detail = "File has no audio track"
    code = "media_no_audio"


class MediaTooLongError(InvalidMediaError):
    default_detail = "Recording is longer than allowed"
    code = "media_too_long"


class UrlUnavailableError(InvalidMediaError):
    default_detail = "No downloadable video at this URL"
    code = "url_unavailable"


class LiveStreamError(InvalidMediaError):
    default_detail = "Live streams cannot be imported"
    code = "url_live_stream"
