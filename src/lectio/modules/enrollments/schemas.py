from datetime import datetime

from lectio.modules.courses.schemas import CourseResponse


class EnrolledCourseResponse(CourseResponse):
    enrolled_at: datetime
    completed_lectures: int
    # Share of the course's lectures watched to the end, from 0 to 1.
    progress: float
