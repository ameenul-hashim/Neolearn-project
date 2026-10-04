from django.db import transaction

from .models import (
    CourseChapter,
    ChapterChangeLog,
)

from .helpers import get_next_order


# ============================================================
# CHAPTER SERVICES
# ============================================================

@transaction.atomic
def create_chapter(
    *,
    batch,
    subject,
    chapter_name,
    chapter_description="",
    status="draft",
    teacher=None,
    admin_user=None,
):
    """
    Create a new course chapter.

    Can be used by both:
        - Admin
        - Teacher

    The caller is responsible for checking permission/access.
    This service handles the actual chapter creation and
    timeline record.
    """

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    chapter_name = (chapter_name or "").strip()
    chapter_description = (chapter_description or "").strip()

    if not chapter_name:
        raise ValueError("Chapter name is required.")

    if teacher is not None and admin_user is not None:
        raise ValueError(
            "A chapter cannot have both a teacher and an admin creator."
        )

    if teacher is None and admin_user is None:
        raise ValueError(
            "A chapter must have either a teacher or an admin creator."
        )

    # --------------------------------------------------------
    # Get next chapter order automatically
    # --------------------------------------------------------

    chapter_order = get_next_order(
        CourseChapter.objects.filter(
            batch=batch,
            subject=subject,
        ),
        order_field="chapter_order",
        deleted_field="is_deleted",
    )

    # --------------------------------------------------------
    # Create chapter
    # --------------------------------------------------------

    chapter = CourseChapter.objects.create(
        batch=batch,
        subject=subject,
        chapter_name=chapter_name,
        chapter_description=chapter_description,
        chapter_order=chapter_order,
        status=status,
        created_by=teacher,
        created_by_admin=admin_user,
    )

    # --------------------------------------------------------
    # Create timeline entry
    # --------------------------------------------------------

    ChapterChangeLog.objects.create(
        chapter=chapter,
        action="created",
        changed_by=teacher,
        changed_by_admin=admin_user,
        field_name="chapter_name",
        old_value="",
        new_value=chapter_name,
        change_summary="Chapter created.",
    )

    return chapter