from lectio.core.exceptions import NotFoundError


class CourseNotFoundError(NotFoundError):
    default_detail = "Course not found"
