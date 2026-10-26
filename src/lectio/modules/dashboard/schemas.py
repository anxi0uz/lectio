from pydantic import BaseModel

from lectio.modules.bookmarks.schemas import BookmarkResponse
from lectio.modules.progress.schemas import ContinueWatchingItem, ProgressResponse
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
    is_enrolled_in_course: bool
    can_manage: bool
    bookmarks: list[BookmarkResponse]
