from pydantic import BaseModel

from lectio.modules.bookmarks.schemas import BookmarkResponse
from lectio.modules.progress.schemas import ContinueWatchingItem, ProgressResponse
from lectio.modules.quizzes.schemas import QuizAttemptResponse
from lectio.modules.search.history import RecentSearch


class DashboardResponse(BaseModel):
    enrolled_courses: int
    lectures_completed: int
    lectures_in_progress: int
    watched_seconds: float
    favorites: int
    bookmarks: int
    # Teachers only: how many lectures they uploaded.
    lectures_uploaded: int | None
    continue_watching: list[ContinueWatchingItem]
    recent_searches: list[RecentSearch]


class LectureStateResponse(BaseModel):
    """Everything about one lecture that depends on who is watching."""

    progress: ProgressResponse
    is_favorite: bool
    is_liked: bool
    is_enrolled_in_course: bool
    can_manage: bool
    bookmarks: list[BookmarkResponse]
    quiz_attempt: QuizAttemptResponse | None


class LectureStatsResponse(BaseModel):
    """Aggregate engagement; public, nothing in it identifies a user."""

    viewers: int
    completed: int
    # Mean share of the lecture viewers got to; None without viewers.
    average_watched_share: float | None
    likes: int
    comments: int
    favorites: int
    bookmarks: int
    quiz_attempts: int
    # Share of right answers over all attempts.
    quiz_average_share: float | None
