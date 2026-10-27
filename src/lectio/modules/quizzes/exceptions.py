from lectio.core.exceptions import ConflictError, DomainError


class QuizNotReadyError(ConflictError):
    default_detail = "Quiz can be generated only for a processed lecture"
    code = "lecture_not_ready"


class QuizMissingError(ConflictError):
    default_detail = "The lecture has no quiz yet"
    code = "quiz_missing"


class QuizAnswersMismatchError(DomainError):
    default_detail = "Answers do not match the quiz questions"
    code = "quiz_answers_mismatch"
