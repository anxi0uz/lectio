from lectio.core.exceptions import DomainError, NotFoundError


class BookmarkNotFoundError(NotFoundError):
    default_detail = "Bookmark not found"


class BookmarkOutOfRangeError(DomainError):
    default_detail = "Bookmark is past the end of the lecture"
