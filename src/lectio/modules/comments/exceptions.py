from lectio.core.exceptions import DomainError, NotFoundError


class CommentNotFoundError(NotFoundError):
    default_detail = "Comment not found"


class CommentOutOfRangeError(DomainError):
    default_detail = "Comment time is past the end of the lecture"
