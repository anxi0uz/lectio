from uuid import UUID

from lectio.core.exceptions import PermissionDeniedError
from lectio.models import User
from lectio.models.enums import UserRole
from lectio.modules.auth.exceptions import TeacherRequiredError


def ensure_can_manage(
    owner_id: UUID | None,
    user: User,
) -> None:
    """Teachers manage their own content; content without an owner (seeded
    from the CLI) is shared by all teachers."""
    if user.role != UserRole.TEACHER:
        raise TeacherRequiredError

    if owner_id is not None and owner_id != user.id:
        raise PermissionDeniedError("Only the owner can change it")
