# =========================================================
# NEOLEARNER — SHARED TIMELINE WRITER
#
# One place to write Course Builder change logs.
#
# Used by BOTH Admin panel and Teacher panel so the same
# action produces the same timeline entry regardless of
# who performed it.
#
# Rules:
#   - Exactly one actor per entry: teacher OR admin.
#   - Never both, never none.
#   - Every create / edit / order / status change calls
#     one of these helpers.
# =========================================================

from .models import (
    CourseChapter,
    ChapterVideo,
    ChapterPDF,
    ChapterQuiz,
    ChapterChangeLog,
    VideoChangeLog,
    PDFChangeLog,
    QuizChangeLog,
)


# =========================================================
# CONTENT TYPE → CHANGE LOG MODEL MAP
# =========================================================

CHANGE_LOG_MODEL_MAP = {
    "chapter": ChapterChangeLog,
    "video": VideoChangeLog,
    "pdf": PDFChangeLog,
    "quiz": QuizChangeLog,
}


# =========================================================
# INTERNAL — VALIDATE ACTOR
# =========================================================

def _validate_actor(teacher, admin_user):
    """
    Exactly one of teacher / admin_user must be provided.
    """

    if teacher is not None and admin_user is not None:
        raise ValueError(
            "A timeline entry cannot have both a teacher and "
            "an admin as the actor."
        )

    if teacher is None and admin_user is None:
        raise ValueError(
            "A timeline entry must have either a teacher or "
            "an admin as the actor."
        )


# =========================================================
# INTERNAL — BUILD ACTOR KWARGS
# =========================================================

def _actor_kwargs(teacher=None, admin_user=None):
    """
    Return the standard actor kwargs for a change log entry.
    """

    return {
        "changed_by": teacher,
        "changed_by_admin": admin_user,
    }


# =========================================================
# GENERIC WRITER
# =========================================================

def log_change(
    *,
    content_type,
    content_instance,
    action,
    teacher=None,
    admin_user=None,
    field_name="",
    old_value="",
    new_value="",
    change_summary="",
):
    """
    Write one timeline entry for any Course Builder content.

    content_type:
        "chapter" | "video" | "pdf" | "quiz"

    content_instance:
        The model instance (CourseChapter / ChapterVideo /
        ChapterPDF / ChapterQuiz).

    action:
        Must match the ACTION_CHOICES of the matching
        changelog model.

    teacher / admin_user:
        Exactly one must be provided.

    Returns:
        The created change log instance.
    """

    _validate_actor(teacher, admin_user)

    change_log_model = CHANGE_LOG_MODEL_MAP.get(content_type)

    if change_log_model is None:
        raise ValueError(
            f"Unknown content type: {content_type!r}"
        )

    # The FK field name on the changelog model matches the
    # content type (chapter / video / pdf / quiz).
    fk_kwargs = {content_type: content_instance}

    return change_log_model.objects.create(
        action=action,
        field_name=field_name or "",
        old_value="" if old_value is None else str(old_value),
        new_value="" if new_value is None else str(new_value),
        change_summary=change_summary or "",
        **fk_kwargs,
        **_actor_kwargs(teacher, admin_user),
    )


# =========================================================
# CONVENIENCE WRAPPERS — one per content type
# =========================================================
# These keep call sites short and self-documenting.
# =========================================================


def log_chapter_change(
    chapter,
    *,
    action,
    teacher=None,
    admin_user=None,
    field_name="",
    old_value="",
    new_value="",
    change_summary="",
):
    return log_change(
        content_type="chapter",
        content_instance=chapter,
        action=action,
        teacher=teacher,
        admin_user=admin_user,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=change_summary,
    )


def log_video_change(
    video,
    *,
    action,
    teacher=None,
    admin_user=None,
    field_name="",
    old_value="",
    new_value="",
    change_summary="",
):
    return log_change(
        content_type="video",
        content_instance=video,
        action=action,
        teacher=teacher,
        admin_user=admin_user,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=change_summary,
    )


def log_pdf_change(
    pdf,
    *,
    action,
    teacher=None,
    admin_user=None,
    field_name="",
    old_value="",
    new_value="",
    change_summary="",
):
    return log_change(
        content_type="pdf",
        content_instance=pdf,
        action=action,
        teacher=teacher,
        admin_user=admin_user,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=change_summary,
    )


def log_quiz_change(
    quiz,
    *,
    action,
    teacher=None,
    admin_user=None,
    field_name="",
    old_value="",
    new_value="",
    change_summary="",
):
    return log_change(
        content_type="quiz",
        content_instance=quiz,
        action=action,
        teacher=teacher,
        admin_user=admin_user,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        change_summary=change_summary,
    )


# =========================================================
# DIFF HELPER — LOG EVERY CHANGED FIELD AUTOMATICALLY
# =========================================================

def log_instance_diff(
    *,
    content_type,
    instance,
    before: dict,
    after: dict,
    action,
    teacher=None,
    admin_user=None,
    summary_prefix="",
    skip_fields=None,
):
    """
    Compare `before` and `after` dicts and log one timeline
    entry per changed field.

    Typical usage in an edit view:

        before = model_to_dict(chapter)
        # ... apply changes, save ...
        after = model_to_dict(chapter)
        log_instance_diff(
            content_type="chapter",
            instance=chapter,
            before=before,
            after=after,
            action="updated",
            teacher=teacher,
        )

    skip_fields:
        Iterable of field names to ignore
        (e.g. "updated_at", "updated_by").
    """

    if skip_fields:
        skip_fields = set(skip_fields)
    else:
        skip_fields = set()

    for field_name, old_value in before.items():

        if field_name in skip_fields:
            continue

        new_value = after.get(field_name)

        if old_value == new_value:
            continue

        log_change(
            content_type=content_type,
            content_instance=instance,
            action=action,
            teacher=teacher,
            admin_user=admin_user,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_summary=(
                f"{summary_prefix}{field_name} changed."
                if summary_prefix
                else f"{field_name} changed."
            ),
        )