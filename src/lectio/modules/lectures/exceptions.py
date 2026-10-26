from fastapi import status

from lectio.core.exceptions import ConflictError, DomainError, NotFoundError


class LectureNotFoundError(NotFoundError):
    default_detail = "Lecture not found"


class LectureNotReadyError(ConflictError):
    default_detail = "Lecture is still being processed"


class LectureBusyError(ConflictError):
    default_detail = "Lecture is already being processed"


class VideoNotAvailableError(NotFoundError):
    default_detail = "Video file is not available yet"


class UnsupportedMediaError(DomainError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = "Unsupported file type"


class FileTooLargeError(DomainError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    default_detail = "File is too large"
