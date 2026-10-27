from lectio.core.exceptions import ConflictError


class QuizNotReadyError(ConflictError):
    default_detail = "Quiz can be generated only for a processed lecture"
    code = "lecture_not_ready"
