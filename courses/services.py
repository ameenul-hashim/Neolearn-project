# courses/services.py

"""
============================================================
NEOLEARN COURSE BUILDER SERVICES
============================================================

This module contains SHARED Course Builder business logic.

Used by:
    - Teacher Course Builder
    - Admin Course Builder

Current model location:
    teachers.models

Later:
    These Course Builder models can be moved to courses.models
    without changing the overall service architecture.

RESPONSIBILITIES
----------------
This file handles:

    Chapter
        - create
        - update
        - automatic ordering
        - timeline logging

    Video
        - create/upload
        - update
        - automatic ordering
        - reorder
        - timeline logging

    PDF
        - create/upload
        - update
        - automatic ordering
        - reorder
        - timeline logging

    Quiz
        - create
        - update
        - create questions/options
        - update questions/options
        - delete quiz question
        - timeline logging

    Deletion
        - teacher deletion requests (chapter/video/pdf/quiz)
        - admin direct deletion
        - admin approve/reject of teacher deletion requests
        - deletion audit records

    Timeline
        - chapter logs
        - video logs
        - PDF logs
        - quiz logs

NOT handled here
----------------
    - login
    - authentication
    - teacher permission
    - admin permission
    - teacher batch/subject access
    - request/response
    - redirect
    - render
    - Django messages
    - template/session popup state

The caller (Teacher/Admin view) is responsible for those.
"""


# ============================================================
# DJANGO IMPORTS
# ============================================================

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from teachers.models import (
    CourseChapter,
    ChapterChangeLog,

    ChapterVideo,
    VideoChangeLog,

    ChapterPDF,
    PDFChangeLog,

    ChapterQuiz,
    QuizQuestion,
    QuizOption,
    QuizChangeLog,

    DeletionAudit,
)


# ============================================================
# COMMON CONSTANTS
# ============================================================

MAX_QUIZ_QUESTIONS = 100
MAX_ATTEMPT_LIMIT = 100

MAX_CHAPTER_NAME_LENGTH = 255
MAX_CHAPTER_DESCRIPTION_LENGTH = 255

MAX_VIDEO_NAME_LENGTH = 255
MAX_VIDEO_DESCRIPTION_LENGTH = 5000

MAX_PDF_NAME_LENGTH = 255
MAX_PDF_DESCRIPTION_LENGTH = 5000

MAX_QUIZ_NAME_LENGTH = 255
MAX_QUIZ_DESCRIPTION_LENGTH = 5000

MAX_QUESTION_LENGTH = 10000
MAX_OPTION_LENGTH = 500

MAX_MARKS = 1000


# ============================================================
# GENERIC INTERNAL HELPERS
# ============================================================

def _clean_string(value):
    """
    Convert a value to a safely stripped string.

    Validation itself belongs in forms.py.

    This helper is only used to normalize values that have
    already passed form validation.
    """

    if value is None:
        return ""

    return str(value).strip()


def _get_first_name(actor, fallback="User"):
    """
    Return the actor's first name for timeline/display purposes.

    Actor is normally a Teacher instance.
    """

    full_name = (
        getattr(
            actor,
            "full_name",
            "",
        )
        or ""
    ).strip()

    if full_name:
        return full_name.split()[0]

    return fallback


def _get_full_name(actor, fallback="User"):
    """
    Return the actor's complete display name.
    """

    full_name = (
        getattr(
            actor,
            "full_name",
            "",
        )
        or ""
    ).strip()

    return full_name or fallback


# ============================================================
# CHAPTER ORDERING
# ============================================================

def get_next_chapter_order(
    batch,
    subject,
):
    """
    Return the next chapter order for a batch + subject.

    Example:

        Existing:
            1
            2
            3

        Result:
            4

    Empty subject:

        Result:
            1

    Deleted chapters are ignored.
    """

    last_chapter = (
        CourseChapter.objects
        .filter(
            batch=batch,
            subject=subject,
            is_deleted=False,
        )
        .order_by(
            "-chapter_order",
            "-id",
        )
        .first()
    )

    if last_chapter is None:
        return 1

    return (
        last_chapter.chapter_order + 1
    )


def _normalize_chapter_orders(
    batch,
    subject,
):
    """
    Normalize active chapter orders to:

        1, 2, 3, 4, ...

    This helper is intended to be called inside a transaction.
    """

    chapters = list(
        CourseChapter.objects
        .select_for_update()
        .filter(
            batch=batch,
            subject=subject,
            is_deleted=False,
        )
        .order_by(
            "chapter_order",
            "id",
        )
    )

    changed = []

    for index, chapter in enumerate(
        chapters,
        start=1,
    ):

        if chapter.chapter_order != index:

            chapter.chapter_order = index
            changed.append(chapter)

    if changed:

        CourseChapter.objects.bulk_update(
            changed,
            ["chapter_order"],
        )

    return chapters


# ============================================================
# CHAPTER — CREATE
# ============================================================

def create_chapter(
    *,
    batch,
    subject,
    actor=None,
    admin_actor=None,
    chapter_name,
    chapter_description,
    status,
):
    """
    Create a new Course Chapter.

    The caller must already have verified that the actor is
    allowed to modify this batch/subject.

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.

    Form validation must already have happened in forms.py.

    Returns:
        CourseChapter instance
    """

    chapter_name = _clean_string(
        chapter_name
    )

    chapter_description = _clean_string(
        chapter_description
    )

    status = _clean_string(
        status
    ).lower()

    with transaction.atomic():

        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        duplicate = (
            CourseChapter.objects
            .filter(
                batch=batch,
                subject=subject,
                chapter_name__iexact=chapter_name,
                is_deleted=False,
            )
            .exists()
        )

        if duplicate:

            raise ValueError(
                "A chapter with this name already exists in this subject."
            )

        # ----------------------------------------------------
        # AUTOMATIC ORDER
        # ----------------------------------------------------

        chapter_order = get_next_chapter_order(
            batch=batch,
            subject=subject,
        )

        # ----------------------------------------------------
        # CREATE
        # ----------------------------------------------------

        chapter = CourseChapter.objects.create(
            batch=batch,
            subject=subject,
            created_by=actor,
            created_by_admin=admin_actor,
            updated_by=actor,
            updated_by_admin=admin_actor,
            chapter_name=chapter_name,
            chapter_description=chapter_description,
            chapter_order=chapter_order,
            status=status,
        )

        # ----------------------------------------------------
        # TIMELINE
        # ----------------------------------------------------

        ChapterChangeLog.objects.create(
            chapter=chapter,
            changed_by=actor,
            changed_by_admin=admin_actor,
            action="created",
            field_name="chapter",
            old_value="",
            new_value=(
                f"Name: {chapter_name}; "
                f"Description: {chapter_description}; "
                f"Order: {chapter_order}; "
                f"Status: {status}"
            ),
            change_summary=(
                f'Chapter "{chapter_name}" was created '
                f"as Chapter {chapter_order}."
            ),
        )

    return chapter


# ============================================================
# CHAPTER — UPDATE
# ============================================================

def update_chapter(
    *,
    chapter,
    actor=None,
    admin_actor=None,
    chapter_name,
    chapter_description,
    chapter_order,
    status,
):
    """
    Update an existing chapter.

    Handles:

        - name
        - description
        - status
        - chapter ordering
        - timeline entries

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.

    Returns:
        CourseChapter instance
    """

    chapter_name = _clean_string(
        chapter_name
    )

    chapter_description = _clean_string(
        chapter_description
    )

    status = _clean_string(
        status
    ).lower()

    try:

        new_order = int(
            chapter_order
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "Chapter order must be a valid whole number."
        )

    if new_order <= 0:

        raise ValueError(
            "Chapter order must be greater than zero."
        )

    with transaction.atomic():

        # ----------------------------------------------------
        # LOCK CHAPTERS
        # ----------------------------------------------------

        chapters = list(
            CourseChapter.objects
            .select_for_update()
            .filter(
                batch=chapter.batch,
                subject=chapter.subject,
                is_deleted=False,
            )
            .order_by(
                "chapter_order",
                "id",
            )
        )

        if not chapters:

            raise ValueError(
                "No active chapters are available."
            )

        if new_order > len(chapters):

            raise ValueError(
                (
                    "Chapter order cannot be greater than "
                    f"the current number of chapters ({len(chapters)})."
                )
            )

        # ----------------------------------------------------
        # DUPLICATE NAME
        # ----------------------------------------------------

        duplicate = (
            CourseChapter.objects
            .filter(
                batch=chapter.batch,
                subject=chapter.subject,
                chapter_name__iexact=chapter_name,
                is_deleted=False,
            )
            .exclude(
                id=chapter.id,
            )
            .exists()
        )

        if duplicate:

            raise ValueError(
                "Another chapter with this name already exists."
            )

        # ----------------------------------------------------
        # OLD VALUES
        # ----------------------------------------------------

        old_name = (
            chapter.chapter_name
            or ""
        )

        old_description = (
            chapter.chapter_description
            or ""
        )

        old_order = chapter.chapter_order

        old_status = (
            chapter.status
            or ""
        )

        # ----------------------------------------------------
        # BUILD NEW ORDER
        # ----------------------------------------------------

        ordered = [
            item
            for item in chapters
            if item.id != chapter.id
        ]

        ordered.insert(
            new_order - 1,
            chapter,
        )

        # ----------------------------------------------------
        # TEMPORARY ORDER
        #
        # Avoid unique/order collisions if a constraint exists.
        # ----------------------------------------------------

        temporary_start = (
            len(ordered) + 1000
        )

        for position, item in enumerate(
            ordered,
            start=1,
        ):

            item.chapter_order = (
                temporary_start + position
            )

        CourseChapter.objects.bulk_update(
            ordered,
            ["chapter_order"],
        )

        # ----------------------------------------------------
        # FINAL ORDER
        # ----------------------------------------------------

        for position, item in enumerate(
            ordered,
            start=1,
        ):

            item.chapter_order = position

        # ----------------------------------------------------
        # UPDATE EDITED CHAPTER
        # ----------------------------------------------------

        chapter.chapter_name = (
            chapter_name
        )

        chapter.chapter_description = (
            chapter_description
        )

        chapter.chapter_order = (
            new_order
        )

        chapter.status = (
            status
        )

        chapter.updated_by = (
            actor
        )

        chapter.updated_by_admin = (
            admin_actor
        )

        chapter.save()

        # ----------------------------------------------------
        # UPDATE OTHER CHAPTER ORDERS
        # ----------------------------------------------------

        other_chapters = [
            item
            for item in ordered
            if item.id != chapter.id
        ]

        if other_chapters:

            CourseChapter.objects.bulk_update(
                other_chapters,
                ["chapter_order"],
            )

        # ----------------------------------------------------
        # TIMELINE — NAME
        # ----------------------------------------------------

        if old_name != chapter_name:

            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="updated",
                field_name="chapter_name",
                old_value=old_name,
                new_value=chapter_name,
                change_summary=(
                    "Chapter name was updated."
                ),
            )

        # ----------------------------------------------------
        # TIMELINE — DESCRIPTION
        # ----------------------------------------------------

        if old_description != chapter_description:

            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="updated",
                field_name="chapter_description",
                old_value=old_description,
                new_value=chapter_description,
                change_summary=(
                    "Chapter description was updated."
                ),
            )

        # ----------------------------------------------------
        # TIMELINE — ORDER
        # ----------------------------------------------------

        if old_order != new_order:

            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="order_changed",
                field_name="chapter_order",
                old_value=str(old_order),
                new_value=str(new_order),
                change_summary=(
                    f"Chapter order changed from "
                    f"{old_order} to {new_order}."
                ),
            )

        # ----------------------------------------------------
        # TIMELINE — STATUS
        # ----------------------------------------------------

        if old_status != status:

            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="status_changed",
                field_name="status",
                old_value=old_status,
                new_value=status,
                change_summary=(
                    f"Chapter status changed from "
                    f"{old_status} to {status}."
                ),
            )

    return chapter


# ============================================================
# VIDEO ORDERING
# ============================================================

def get_next_video_order(
    chapter,
):
    """
    Return the next active video order.
    """

    last_video = (
        ChapterVideo.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .order_by(
            "-video_order",
            "-id",
        )
        .first()
    )

    if last_video is None:
        return 1

    return (
        last_video.video_order + 1
    )


def normalize_video_orders(
    chapter,
):
    """
    Normalize active video order:

        1, 2, 3, 4, ...

    Returns the active videos.
    """

    videos = list(
        ChapterVideo.objects
        .select_for_update()
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .order_by(
            "video_order",
            "id",
        )
    )

    changed = []

    for index, video in enumerate(
        videos,
        start=1,
    ):

        if video.video_order != index:

            video.video_order = index
            changed.append(video)

    if changed:

        ChapterVideo.objects.bulk_update(
            changed,
            ["video_order"],
        )

    return videos


# ============================================================
# VIDEO — CREATE
# ============================================================

def create_video(
    *,
    chapter,
    actor=None,
    admin_actor=None,
    video_name,
    video_description,
    video_file,
):
    """
    Create/upload a video.

    File validation belongs to forms.py.

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.

    This service only performs the actual business operation.
    """

    video_name = _clean_string(
        video_name
    )

    video_description = _clean_string(
        video_description
    )

    with transaction.atomic():

        # ----------------------------------------------------
        # DUPLICATE
        # ----------------------------------------------------

        duplicate = (
            ChapterVideo.objects
            .filter(
                chapter=chapter,
                video_name__iexact=video_name,
                is_deleted=False,
            )
            .exists()
        )

        if duplicate:

            raise ValueError(
                "A video with this name already exists in this chapter."
            )

        # ----------------------------------------------------
        # ORDER
        # ----------------------------------------------------

        video_order = get_next_video_order(
            chapter
        )

        # ----------------------------------------------------
        # CREATE
        # ----------------------------------------------------

        video = ChapterVideo.objects.create(
            chapter=chapter,
            video_name=video_name,
            video_description=video_description,
            video_file=video_file,
            video_order=video_order,
            created_by=actor,
            created_by_admin=admin_actor,
            updated_by=actor,
            updated_by_admin=admin_actor,
            delete_requested=False,
            delete_status="pending",
            is_deleted=False,
        )

        # ----------------------------------------------------
        # TIMELINE
        # ----------------------------------------------------

        file_name = (
            getattr(
                video_file,
                "name",
                "",
            )
            or ""
        )

        VideoChangeLog.objects.create(
            video=video,
            changed_by=actor,
            changed_by_admin=admin_actor,
            action="created",
            field_name="video",
            old_value="",
            new_value=(
                f"Name: {video.video_name}; "
                f"Description: {video.video_description}; "
                f"Order: {video.video_order}; "
                f"File: {file_name}"
            ),
            change_summary=(
                f'Video "{video.video_name}" was created '
                f"at order {video.video_order}."
            ),
        )

    return video


# ============================================================
# VIDEO — UPDATE
# ============================================================

def update_video(
    *,
    video,
    actor=None,
    admin_actor=None,
    video_name,
    video_description,
    video_order,
    replacement_file=None,
):
    """
    Update an existing video.

    Handles:

        - name
        - description
        - order
        - optional file replacement
        - timeline

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.

    Returns:
        ChapterVideo
    """

    video_name = _clean_string(
        video_name
    )

    video_description = _clean_string(
        video_description
    )

    try:

        new_order = int(
            video_order
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "Video order must be a valid number."
        )

    if new_order <= 0:

        raise ValueError(
            "Video order must be greater than zero."
        )

    with transaction.atomic():

        # ----------------------------------------------------
        # LOCK VIDEOS
        # ----------------------------------------------------

        videos = list(
            ChapterVideo.objects
            .select_for_update()
            .filter(
                chapter=video.chapter,
                is_deleted=False,
            )
            .order_by(
                "video_order",
                "id",
            )
        )

        locked_video = next(
            (
                item
                for item in videos
                if item.id == video.id
            ),
            None,
        )

        if locked_video is None:

            raise ValueError(
                "The selected video no longer exists."
            )

        if new_order > len(videos):

            raise ValueError(
                (
                    f"Video order must be between "
                    f"1 and {len(videos)}."
                )
            )

        # ----------------------------------------------------
        # DUPLICATE NAME
        # ----------------------------------------------------

        duplicate = (
            ChapterVideo.objects
            .filter(
                chapter=video.chapter,
                video_name__iexact=video_name,
                is_deleted=False,
            )
            .exclude(
                id=video.id,
            )
            .exists()
        )

        if duplicate:

            raise ValueError(
                "A video with this name already exists in this chapter."
            )

        # ----------------------------------------------------
        # OLD VALUES
        # ----------------------------------------------------

        old_name = (
            locked_video.video_name
            or ""
        )

        old_description = (
            locked_video.video_description
            or ""
        )

        old_order = (
            locked_video.video_order
        )

        old_file_name = (
            getattr(
                locked_video.video_file,
                "name",
                "",
            )
            or ""
        )

        # ----------------------------------------------------
        # REORDER
        # ----------------------------------------------------

        ordered = [
            item
            for item in videos
            if item.id != locked_video.id
        ]

        ordered.insert(
            new_order - 1,
            locked_video,
        )

        for position, item in enumerate(
            ordered,
            start=1,
        ):

            item.video_order = position

        # ----------------------------------------------------
        # UPDATE TARGET
        # ----------------------------------------------------

        locked_video.video_name = (
            video_name
        )

        locked_video.video_description = (
            video_description
        )

        locked_video.video_order = (
            new_order
        )

        locked_video.updated_by = (
            actor
        )

        locked_video.updated_by_admin = (
            admin_actor
        )

        if replacement_file is not None:

            locked_video.video_file = (
                replacement_file
            )

        # ----------------------------------------------------
        # SAVE TARGET
        # ----------------------------------------------------

        locked_video.save()

        # ----------------------------------------------------
        # SAVE OTHER REORDERED VIDEOS
        # ----------------------------------------------------

        others = [
            item
            for item in ordered
            if item.id != locked_video.id
        ]

        if others:

            for item in others:

                item.updated_by = actor
                item.updated_by_admin = admin_actor

            ChapterVideo.objects.bulk_update(
                others,
                [
                    "video_order",
                    "updated_by",
                    "updated_at",
                ],
            )

        # ----------------------------------------------------
        # NAME LOG
        # ----------------------------------------------------

        if old_name != video_name:

            VideoChangeLog.objects.create(
                video=locked_video,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="name_changed",
                field_name="video_name",
                old_value=old_name,
                new_value=video_name,
                change_summary=(
                    "Video name was updated."
                ),
            )

        # ----------------------------------------------------
        # DESCRIPTION LOG
        # ----------------------------------------------------

        if old_description != video_description:

            VideoChangeLog.objects.create(
                video=locked_video,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="description_changed",
                field_name="video_description",
                old_value=old_description,
                new_value=video_description,
                change_summary=(
                    "Video description was updated."
                ),
            )

        # ----------------------------------------------------
        # ORDER LOG
        # ----------------------------------------------------

        if old_order != new_order:

            VideoChangeLog.objects.create(
                video=locked_video,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="order_changed",
                field_name="video_order",
                old_value=str(old_order),
                new_value=str(new_order),
                change_summary=(
                    f"Video order changed from "
                    f"{old_order} to {new_order}."
                ),
            )

        # ----------------------------------------------------
        # FILE LOG
        # ----------------------------------------------------

        if replacement_file is not None:

            new_file_name = (
                getattr(
                    replacement_file,
                    "name",
                    "",
                )
                or ""
            )

            VideoChangeLog.objects.create(
                video=locked_video,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="file_changed",
                field_name="video_file",
                old_value=(
                    old_file_name
                    or "Previous MP4 file"
                ),
                new_value=(
                    new_file_name
                    or "New MP4 file"
                ),
                change_summary=(
                    "Video file was replaced."
                ),
            )

        # ----------------------------------------------------
        # FINAL NORMALIZATION
        # ----------------------------------------------------

        normalize_video_orders(
            video.chapter
        )

    return locked_video


# ============================================================
# PDF ORDERING
# ============================================================

def get_next_pdf_order(
    chapter,
):
    """
    Return the next active PDF order.
    """

    last_pdf = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .order_by(
            "-pdf_order",
            "-id",
        )
        .first()
    )

    if last_pdf is None:
        return 1

    return (
        last_pdf.pdf_order + 1
    )


def normalize_pdf_orders(
    chapter,
):
    """
    Normalize active PDF order:

        1, 2, 3, 4, ...

    Returns:
        (pdfs, changed)
    """

    pdfs = list(
        ChapterPDF.objects
        .select_for_update()
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .order_by(
            "pdf_order",
            "id",
        )
    )

    changed = []

    for index, pdf in enumerate(
        pdfs,
        start=1,
    ):

        if pdf.pdf_order != index:

            old_order = (
                pdf.pdf_order
            )

            pdf.pdf_order = index

            changed.append(
                (
                    pdf,
                    old_order,
                    index,
                )
            )

    for pdf, _, _ in changed:

        pdf.save(
            update_fields=[
                "pdf_order",
                "updated_at",
            ]
        )

    return pdfs, changed


# ============================================================
# PDF — CREATE
# ============================================================

def create_pdf(
    *,
    chapter,
    actor=None,
    admin_actor=None,
    pdf_name,
    pdf_description,
    pdf_file,
    pdf_thumbnail=None,
):
    """
    Create/upload a PDF note.

    Validation of the PDF and thumbnail belongs in forms.py.

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.
    """

    pdf_name = _clean_string(
        pdf_name
    )

    pdf_description = _clean_string(
        pdf_description
    )

    with transaction.atomic():

        # ----------------------------------------------------
        # DUPLICATE
        # ----------------------------------------------------

        duplicate = (
            ChapterPDF.objects
            .filter(
                chapter=chapter,
                pdf_name__iexact=pdf_name,
                is_deleted=False,
            )
            .exists()
        )

        if duplicate:

            raise ValueError(
                "A PDF with this name already exists in this chapter."
            )

        # ----------------------------------------------------
        # ORDER
        # ----------------------------------------------------

        pdf_order = get_next_pdf_order(
            chapter
        )

        # ----------------------------------------------------
        # CREATE
        # ----------------------------------------------------

        pdf = ChapterPDF.objects.create(
            chapter=chapter,
            pdf_name=pdf_name,
            pdf_description=pdf_description,
            pdf_file=pdf_file,
            pdf_thumbnail=pdf_thumbnail,
            pdf_order=pdf_order,
            created_by=actor,
            created_by_admin=admin_actor,
            updated_by=actor,
            updated_by_admin=admin_actor,
            delete_requested=False,
            delete_requested_by=None,
            delete_requested_at=None,
            delete_reason="",
            delete_status="pending",
            is_deleted=False,
        )

        # ----------------------------------------------------
        # TIMELINE
        # ----------------------------------------------------

        file_name = (
            getattr(
                pdf_file,
                "name",
                "",
            )
            or ""
        )

        thumbnail_name = (
            getattr(
                pdf_thumbnail,
                "name",
                "",
            )
            or "Default NeoLearn thumbnail"
        )

        PDFChangeLog.objects.create(
            pdf=pdf,
            changed_by=actor,
            changed_by_admin=admin_actor,
            action="created",
            field_name="pdf",
            old_value="",
            new_value=(
                f"Name: {pdf.pdf_name}; "
                f"Description: {pdf.pdf_description}; "
                f"Order: {pdf.pdf_order}; "
                f"File: {file_name}; "
                f"Thumbnail: {thumbnail_name}"
            ),
            change_summary=(
                f'PDF "{pdf.pdf_name}" was created '
                f"at order {pdf.pdf_order}."
            ),
        )

    return pdf


# ============================================================
# PDF — UPDATE
# ============================================================

def update_pdf(
    *,
    pdf,
    actor=None,
    admin_actor=None,
    pdf_name,
    pdf_description,
    pdf_order,
    replacement_file=None,
    replacement_thumbnail=None,
):
    """
    Update an existing PDF.

    Handles:

        - name
        - description
        - order
        - PDF replacement
        - thumbnail replacement
        - timeline

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.
    """

    pdf_name = _clean_string(
        pdf_name
    )

    pdf_description = _clean_string(
        pdf_description
    )

    try:

        new_order = int(
            pdf_order
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "PDF order must be a valid number."
        )

    if new_order <= 0:

        raise ValueError(
            "PDF order must be greater than zero."
        )

    with transaction.atomic():

        # ----------------------------------------------------
        # LOCK PDFs
        # ----------------------------------------------------

        pdfs = list(
            ChapterPDF.objects
            .select_for_update()
            .filter(
                chapter=pdf.chapter,
                is_deleted=False,
            )
            .order_by(
                "pdf_order",
                "id",
            )
        )

        locked_pdf = next(
            (
                item
                for item in pdfs
                if item.id == pdf.id
            ),
            None,
        )

        if locked_pdf is None:

            raise ValueError(
                "The selected PDF no longer exists."
            )

        if new_order > len(pdfs):

            raise ValueError(
                (
                    f"PDF order must be between "
                    f"1 and {len(pdfs)}."
                )
            )

        # ----------------------------------------------------
        # DUPLICATE
        # ----------------------------------------------------

        duplicate = (
            ChapterPDF.objects
            .filter(
                chapter=pdf.chapter,
                pdf_name__iexact=pdf_name,
                is_deleted=False,
            )
            .exclude(
                id=pdf.id,
            )
            .exists()
        )

        if duplicate:

            raise ValueError(
                "A PDF with this name already exists in this chapter."
            )

        # ----------------------------------------------------
        # OLD VALUES
        # ----------------------------------------------------

        old_name = (
            locked_pdf.pdf_name
            or ""
        )

        old_description = (
            locked_pdf.pdf_description
            or ""
        )

        old_file_name = (
            getattr(
                locked_pdf.pdf_file,
                "name",
                "",
            )
            or ""
        )

        old_thumbnail_name = ""

        if locked_pdf.pdf_thumbnail:

            old_thumbnail_name = (
                str(
                    getattr(
                        locked_pdf.pdf_thumbnail,
                        "name",
                        "",
                    )
                    or ""
                )
            )

        # ----------------------------------------------------
        # ORIGINAL ORDERS
        # ----------------------------------------------------

        original_orders = {
            item.id: item.pdf_order
            for item in pdfs
        }

        # ----------------------------------------------------
        # REORDER
        # ----------------------------------------------------

        ordered = [
            item
            for item in pdfs
            if item.id != locked_pdf.id
        ]

        ordered.insert(
            new_order - 1,
            locked_pdf,
        )

        for position, item in enumerate(
            ordered,
            start=1,
        ):

            item.pdf_order = position

        # ----------------------------------------------------
        # UPDATE TARGET
        # ----------------------------------------------------

        locked_pdf.pdf_name = (
            pdf_name
        )

        locked_pdf.pdf_description = (
            pdf_description
        )

        locked_pdf.pdf_order = (
            new_order
        )

        locked_pdf.updated_by = (
            actor
        )

        locked_pdf.updated_by_admin = (
            admin_actor
        )

        if replacement_file is not None:

            locked_pdf.pdf_file = (
                replacement_file
            )

        if replacement_thumbnail is not None:

            locked_pdf.pdf_thumbnail = (
                replacement_thumbnail
            )

        locked_pdf.save()

        # ----------------------------------------------------
        # UPDATE OTHER PDF ORDERS
        # ----------------------------------------------------

        other_pdfs = [
            item
            for item in ordered
            if item.id != locked_pdf.id
        ]

        for item in other_pdfs:

            item.updated_by = actor
            item.updated_by_admin = admin_actor

        if other_pdfs:

            ChapterPDF.objects.bulk_update(
                other_pdfs,
                [
                    "pdf_order",
                    "updated_by",
                    "updated_at",
                ],
            )

        # ----------------------------------------------------
        # NAME LOG
        # ----------------------------------------------------

        if old_name != pdf_name:

            PDFChangeLog.objects.create(
                pdf=locked_pdf,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="name_changed",
                field_name="pdf_name",
                old_value=old_name,
                new_value=pdf_name,
                change_summary=(
                    "PDF notes name was updated."
                ),
            )

        # ----------------------------------------------------
        # DESCRIPTION LOG
        # ----------------------------------------------------

        if old_description != pdf_description:

            PDFChangeLog.objects.create(
                pdf=locked_pdf,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="description_changed",
                field_name="pdf_description",
                old_value=old_description,
                new_value=pdf_description,
                change_summary=(
                    "PDF notes description was updated."
                ),
            )

        # ----------------------------------------------------
        # ORDER LOGS
        # ----------------------------------------------------

        for item in ordered:

            old_order = (
                original_orders[item.id]
            )

            new_item_order = (
                item.pdf_order
            )

            if old_order != new_item_order:

                PDFChangeLog.objects.create(
                    pdf=item,
                    changed_by=actor,
                    changed_by_admin=admin_actor,
                    action="order_changed",
                    field_name="pdf_order",
                    old_value=str(
                        old_order
                    ),
                    new_value=str(
                        new_item_order
                    ),
                    change_summary=(
                        f'PDF "{item.pdf_name}" order '
                        f"changed from {old_order} "
                        f"to {new_item_order}."
                    ),
                )

        # ----------------------------------------------------
        # FILE LOG
        # ----------------------------------------------------

        if replacement_file is not None:

            new_file_name = (
                getattr(
                    replacement_file,
                    "name",
                    "",
                )
                or ""
            )

            PDFChangeLog.objects.create(
                pdf=locked_pdf,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="file_changed",
                field_name="pdf_file",
                old_value=(
                    old_file_name
                    or "Previous PDF file"
                ),
                new_value=(
                    new_file_name
                    or "New PDF file"
                ),
                change_summary=(
                    "PDF file was replaced."
                ),
            )

        # ----------------------------------------------------
        # THUMBNAIL LOG
        # ----------------------------------------------------

        if replacement_thumbnail is not None:

            new_thumbnail_name = (
                getattr(
                    replacement_thumbnail,
                    "name",
                    "",
                )
                or ""
            )

            PDFChangeLog.objects.create(
                pdf=locked_pdf,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="thumbnail_changed",
                field_name="pdf_thumbnail",
                old_value=(
                    old_thumbnail_name
                    or "Default NeoLearn thumbnail"
                ),
                new_value=(
                    new_thumbnail_name
                    or "New PDF thumbnail"
                ),
                change_summary=(
                    "PDF thumbnail was replaced."
                ),
            )

        # ----------------------------------------------------
        # FINAL NORMALIZATION
        # ----------------------------------------------------

        normalize_pdf_orders(
            pdf.chapter
        )

    return locked_pdf


# ============================================================
# QUIZ — CREATE
# ============================================================

def create_quiz(
    *,
    chapter,
    actor=None,
    admin_actor=None,
    quiz_name,
    quiz_description,
    attempt_limit,
    questions,
):
    """
    Create a complete quiz atomically.

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.

    Expected question structure:

        [
            {
                "question_text": "...",
                "marks": 5,
                "options": {
                    "A": "...",
                    "B": "...",
                    "C": "...",
                    "D": "...",
                },
                "correct_option": "A",
            },
        ]

    Form validation belongs in forms.py.

    This service performs the database operation and timeline
    creation.
    """

    quiz_name = _clean_string(
        quiz_name
    )

    quiz_description = _clean_string(
        quiz_description
    )

    try:

        attempt_limit = int(
            attempt_limit
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "Attempt limit must be a whole number."
        )

    # --------------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------------

    questions = list(
        questions or []
    )

    if not questions:

        raise ValueError(
            "A quiz must contain at least one question."
        )

    if len(questions) > MAX_QUIZ_QUESTIONS:

        raise ValueError(
            (
                "A quiz cannot contain more than "
                f"{MAX_QUIZ_QUESTIONS} questions."
            )
        )

    with transaction.atomic():

        # ----------------------------------------------------
        # DUPLICATE QUIZ
        # ----------------------------------------------------

        duplicate = (
            ChapterQuiz.objects
            .filter(
                chapter=chapter,
                quiz_name__iexact=quiz_name,
                is_deleted=False,
            )
            .exists()
        )

        if duplicate:

            raise ValueError(
                "A quiz with this name already exists in this chapter."
            )

        # ----------------------------------------------------
        # CREATE QUIZ
        # ----------------------------------------------------

        quiz = ChapterQuiz.objects.create(
            chapter=chapter,
            quiz_name=quiz_name,
            quiz_description=quiz_description,
            attempt_limit=attempt_limit,
            created_by=actor,
            created_by_admin=admin_actor,
            updated_by=actor,
            updated_by_admin=admin_actor,
            delete_requested=False,
            delete_requested_by=None,
            delete_requested_at=None,
            delete_reason="",
            delete_status="pending",
            is_deleted=False,
        )

        total_marks = 0

        # ----------------------------------------------------
        # QUESTIONS + OPTIONS
        # ----------------------------------------------------

        for question_data in questions:

            question_text = _clean_string(
                question_data.get(
                    "question_text"
                )
            )

            marks = int(
                question_data.get(
                    "marks"
                )
            )

            options = (
                question_data.get(
                    "options"
                )
                or {}
            )

            correct_option = _clean_string(
                question_data.get(
                    "correct_option"
                )
            ).upper()

            question = QuizQuestion.objects.create(
                quiz=quiz,
                question_text=question_text,
                marks=marks,
            )

            total_marks += marks

            for label in (
                "A",
                "B",
                "C",
                "D",
            ):

                option_text = _clean_string(
                    options.get(
                        label,
                        "",
                    )
                )

                QuizOption.objects.create(
                    question=question,
                    option_label=label,
                    option_text=option_text,
                    is_correct=(
                        label == correct_option
                    ),
                )

        # ----------------------------------------------------
        # QUIZ TIMELINE
        # ----------------------------------------------------

        QuizChangeLog.objects.create(
            quiz=quiz,
            changed_by=actor,
            changed_by_admin=admin_actor,
            action="created",
            field_name="quiz",
            old_value="",
            new_value=(
                f"Name: {quiz.quiz_name}; "
                f"Description: {quiz.quiz_description}; "
                f"Attempt Limit: {quiz.attempt_limit}; "
                f"Questions: {len(questions)}; "
                f"Total Marks: {total_marks}"
            ),
            change_summary=(
                f'Quiz "{quiz.quiz_name}" was created '
                f"with {len(questions)} "
                f"question"
                f'{"s" if len(questions) != 1 else ""}.'
            ),
        )

    return quiz


# ============================================================
# QUIZ — UPDATE BASIC INFORMATION
# ============================================================

def update_quiz(
    *,
    quiz,
    actor=None,
    admin_actor=None,
    quiz_name,
    quiz_description,
    attempt_limit,
):
    """
    Update quiz basic information.

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.

    Handles:

        - name
        - description
        - attempt limit
        - timeline
    """

    quiz_name = _clean_string(
        quiz_name
    )

    quiz_description = _clean_string(
        quiz_description
    )

    try:

        new_attempt_limit = int(
            attempt_limit
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "Attempt limit must be a whole number."
        )

    with transaction.atomic():

        # ----------------------------------------------------
        # DUPLICATE
        # ----------------------------------------------------

        duplicate = (
            ChapterQuiz.objects
            .filter(
                chapter=quiz.chapter,
                quiz_name__iexact=quiz_name,
                is_deleted=False,
            )
            .exclude(
                id=quiz.id,
            )
            .exists()
        )

        if duplicate:

            raise ValueError(
                "Another quiz with this name already exists."
            )

        # ----------------------------------------------------
        # OLD VALUES
        # ----------------------------------------------------

        old_name = (
            quiz.quiz_name
            or ""
        )

        old_description = (
            quiz.quiz_description
            or ""
        )

        old_attempt_limit = (
            quiz.attempt_limit
        )

        # ----------------------------------------------------
        # UPDATE
        # ----------------------------------------------------

        quiz.quiz_name = (
            quiz_name
        )

        quiz.quiz_description = (
            quiz_description
        )

        quiz.attempt_limit = (
            new_attempt_limit
        )

        quiz.updated_by = (
            actor
        )

        quiz.updated_by_admin = (
            admin_actor
        )

        quiz.save()

        # ----------------------------------------------------
        # NAME LOG
        # ----------------------------------------------------

        if old_name != quiz_name:

            QuizChangeLog.objects.create(
                quiz=quiz,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="name_changed",
                field_name="quiz_name",
                old_value=old_name,
                new_value=quiz_name,
                change_summary=(
                    "Quiz name was updated."
                ),
            )

        # ----------------------------------------------------
        # DESCRIPTION LOG
        # ----------------------------------------------------

        if old_description != quiz_description:

            QuizChangeLog.objects.create(
                quiz=quiz,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="description_changed",
                field_name="quiz_description",
                old_value=old_description,
                new_value=quiz_description,
                change_summary=(
                    "Quiz description was updated."
                ),
            )

        # ----------------------------------------------------
        # ATTEMPT LIMIT LOG
        # ----------------------------------------------------

        if old_attempt_limit != new_attempt_limit:

            QuizChangeLog.objects.create(
                quiz=quiz,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="attempt_limit_changed",
                field_name="attempt_limit",
                old_value=str(
                    old_attempt_limit
                ),
                new_value=str(
                    new_attempt_limit
                ),
                change_summary=(
                    f"Attempt limit changed from "
                    f"{old_attempt_limit} to "
                    f"{new_attempt_limit}."
                ),
            )

    return quiz


# ============================================================
# QUIZ QUESTION — CREATE
# ============================================================

def create_quiz_question(
    *,
    quiz,
    actor=None,
    admin_actor=None,
    question_text,
    marks,
    options,
    correct_option,
):
    """
    Add a question to an existing quiz.

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.

    This operation is useful for the future Admin/Teacher
    edit workspace.

    options example:

        {
            "A": "Answer A",
            "B": "Answer B",
            "C": "Answer C",
            "D": "Answer D",
        }
    """

    question_text = _clean_string(
        question_text
    )

    correct_option = _clean_string(
        correct_option
    ).upper()

    try:

        marks = int(
            marks
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "Question marks must be a whole number."
        )

    options = options or {}

    with transaction.atomic():

        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text=question_text,
            marks=marks,
        )

        for label in (
            "A",
            "B",
            "C",
            "D",
        ):

            option_text = _clean_string(
                options.get(
                    label,
                    "",
                )
            )

            QuizOption.objects.create(
                question=question,
                option_label=label,
                option_text=option_text,
                is_correct=(
                    label == correct_option
                ),
            )

        quiz.updated_by = actor

        quiz.updated_by_admin = admin_actor

        quiz.save(
            update_fields=[
                "updated_by",
                "updated_by_admin",
                "updated_at",
            ]
        )

        QuizChangeLog.objects.create(
            quiz=quiz,
            changed_by=actor,
            changed_by_admin=admin_actor,
            action="question_added",
            field_name="question",
            old_value="",
            new_value=question_text,
            change_summary=(
                f"Question {question.id} was added."
            ),
        )

    return question


# ============================================================
# QUIZ QUESTION — UPDATE
# ============================================================

def update_quiz_question(
    *,
    question,
    actor=None,
    admin_actor=None,
    question_text,
    marks,
    options,
    correct_option,
):
    """
    Update an existing quiz question and its four options.

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.
    """

    question_text = _clean_string(
        question_text
    )

    correct_option = _clean_string(
        correct_option
    ).upper()

    try:

        marks = int(
            marks
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "Question marks must be a whole number."
        )

    options = options or {}

    with transaction.atomic():

        # ----------------------------------------------------
        # OLD VALUES
        # ----------------------------------------------------

        old_question_text = (
            question.question_text
        )

        old_marks = (
            question.marks
        )

        old_options = {
            option.option_label: (
                option.option_text,
                option.is_correct,
            )
            for option in question.options.all()
        }

        # ----------------------------------------------------
        # QUESTION
        # ----------------------------------------------------

        question.question_text = (
            question_text
        )

        question.marks = (
            marks
        )

        question.save()

        # ----------------------------------------------------
        # EXISTING OPTIONS
        # ----------------------------------------------------

        current_options = {
            option.option_label: option
            for option in question.options.all()
        }

        for label in (
            "A",
            "B",
            "C",
            "D",
        ):

            option_text = _clean_string(
                options.get(
                    label,
                    "",
                )
            )

            option = current_options.get(
                label
            )

            if option is None:

                QuizOption.objects.create(
                    question=question,
                    option_label=label,
                    option_text=option_text,
                    is_correct=(
                        label == correct_option
                    ),
                )

            else:

                option.option_text = (
                    option_text
                )

                option.is_correct = (
                    label == correct_option
                )

                option.save()

        # ----------------------------------------------------
        # UPDATE QUIZ ACTOR
        # ----------------------------------------------------

        quiz = question.quiz

        quiz.updated_by = actor

        quiz.updated_by_admin = admin_actor

        quiz.save(
            update_fields=[
                "updated_by",
                "updated_by_admin",
                "updated_at",
            ]
        )

        # ----------------------------------------------------
        # QUESTION TEXT LOG
        # ----------------------------------------------------

        if old_question_text != question_text:

            QuizChangeLog.objects.create(
                quiz=quiz,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="question_updated",
                field_name="question_text",
                old_value=old_question_text,
                new_value=question_text,
                change_summary=(
                    f"Question {question.id} text was updated."
                ),
            )

        # ----------------------------------------------------
        # MARKS LOG
        # ----------------------------------------------------

        if old_marks != marks:

            QuizChangeLog.objects.create(
                quiz=quiz,
                changed_by=actor,
                changed_by_admin=admin_actor,
                action="question_updated",
                field_name="marks",
                old_value=str(
                    old_marks
                ),
                new_value=str(
                    marks
                ),
                change_summary=(
                    f"Question {question.id} marks were updated."
                ),
            )

        # ----------------------------------------------------
        # OPTION LOGS
        # ----------------------------------------------------

        for label in (
            "A",
            "B",
            "C",
            "D",
        ):

            new_value = _clean_string(
                options.get(
                    label,
                    "",
                )
            )

            old_value, old_correct = (
                old_options.get(
                    label,
                    (
                        "",
                        False,
                    ),
                )
            )

            new_correct = (
                label == correct_option
            )

            if old_value != new_value:

                QuizChangeLog.objects.create(
                    quiz=quiz,
                    changed_by=actor,
                    changed_by_admin=admin_actor,
                    action="option_changed",
                    field_name=f"option_{label}",
                    old_value=old_value,
                    new_value=new_value,
                    change_summary=(
                        f"Option {label} of question "
                        f"{question.id} was updated."
                    ),
                )

            if old_correct != new_correct:

                QuizChangeLog.objects.create(
                    quiz=quiz,
                    changed_by=actor,
                    changed_by_admin=admin_actor,
                    action="correct_answer_changed",
                    field_name=(
                        f"option_{label}_correct"
                    ),
                    old_value=str(
                        old_correct
                    ),
                    new_value=str(
                        new_correct
                    ),
                    change_summary=(
                        f"Correct-answer selection for "
                        f"option {label} of question "
                        f"{question.id} changed."
                    ),
                )

    return question


# ============================================================
# QUIZ QUESTION — DELETE
# ============================================================

def delete_quiz_question(
    *,
    question,
    actor=None,
    admin_actor=None,
):
    """
    Delete a quiz question.

    Exactly one of ``actor`` (Teacher) or ``admin_actor`` (User)
    must be provided so the correct actor fields are recorded.

    IMPORTANT:

    This is deletion of a question INSIDE an existing quiz.

    It is different from deleting the entire Quiz content.

    Whole Quiz deletion permissions remain outside this service.
    """

    quiz = question.quiz

    question_id = (
        question.id
    )

    question_snapshot = (
        question.question_text
    )

    with transaction.atomic():

        question.delete()

        quiz.updated_by = actor

        quiz.updated_by_admin = admin_actor

        quiz.save(
            update_fields=[
                "updated_by",
                "updated_by_admin",
                "updated_at",
            ]
        )

        QuizChangeLog.objects.create(
            quiz=quiz,
            changed_by=actor,
            changed_by_admin=admin_actor,
            action="question_deleted",
            field_name="question",
            old_value=question_snapshot,
            new_value="",
            change_summary=(
                f"Question {question_id} was deleted."
            ),
        )

    return quiz


# ============================================================
# TIMELINE QUERY HELPERS
# ============================================================

def get_chapter_timeline(
    chapter,
):
    """
    Return chapter timeline entries in newest-first order.
    """

    return (
        ChapterChangeLog.objects
        .filter(
            chapter=chapter,
        )
        .select_related(
            "changed_by",
        )
        .order_by(
            "-changed_at",
            "-id",
        )
    )


def get_video_timeline(
    video,
):
    """
    Return video timeline entries in newest-first order.
    """

    return (
        VideoChangeLog.objects
        .filter(
            video=video,
        )
        .select_related(
            "changed_by",
        )
        .order_by(
            "-changed_at",
            "-id",
        )
    )


def get_pdf_timeline(
    pdf,
):
    """
    Return PDF timeline entries in newest-first order.
    """

    return (
        PDFChangeLog.objects
        .filter(
            pdf=pdf,
        )
        .select_related(
            "changed_by",
        )
        .order_by(
            "-changed_at",
            "-id",
        )
    )


def get_quiz_timeline(
    quiz,
):
    """
    Return quiz timeline entries in newest-first order.
    """

    return (
        QuizChangeLog.objects
        .filter(
            quiz=quiz,
        )
        .select_related(
            "changed_by",
        )
        .order_by(
            "-changed_at",
            "-id",
        )
    )


# ============================================================
# TIMELINE DISPLAY HELPERS
# ============================================================

def build_timeline_entry(
    log,
):
    """
    Convert a timeline model instance into a template-friendly
    dictionary.

    This keeps repeated timeline formatting out of Admin and
    Teacher views.
    """

    actor = getattr(
        log,
        "changed_by",
        None,
    )

    admin_actor = getattr(
        log,
        "changed_by_admin",
        None,
    )

    if admin_actor is not None:

        full_name = (
            admin_actor.get_full_name().strip()
            or getattr(
                admin_actor,
                "username",
                "",
            )
            or getattr(
                admin_actor,
                "email",
                "",
            )
            or "Admin"
        )

        first_name = (
            full_name.split()[0]
            if full_name
            else "Admin"
        )

    else:

        full_name = _get_full_name(
            actor,
            fallback="User",
        )

        first_name = _get_first_name(
            actor,
            fallback="User",
        )

    action_display = ""

    try:

        action_display = (
            log.get_action_display()
        )

    except (
        AttributeError,
    ):

        action_display = (
            getattr(
                log,
                "action",
                "",
            )
            or ""
        )

    return {
        "id": log.id,
        "actor_name": first_name,
        "actor_full_name": full_name,
        "action": action_display,
        "action_key": getattr(
            log,
            "action",
            "",
        ),
        "field_name": getattr(
            log,
            "field_name",
            "",
        ),
        "old_value": getattr(
            log,
            "old_value",
            "",
        ),
        "new_value": getattr(
            log,
            "new_value",
            "",
        ),
        "summary": getattr(
            log,
            "change_summary",
            "",
        ),
        "changed_at": getattr(
            log,
            "changed_at",
            None,
        ),
    }


def get_chapter_timeline_entries(
    chapter,
):
    """
    Return chapter timeline already formatted for templates.
    """

    logs = get_chapter_timeline(
        chapter
    )

    return [
        build_timeline_entry(log)
        for log in logs
    ]


def get_video_timeline_entries(
    video,
):
    """
    Return video timeline already formatted for templates.
    """

    logs = get_video_timeline(
        video
    )

    return [
        build_timeline_entry(log)
        for log in logs
    ]


def get_pdf_timeline_entries(
    pdf,
):
    """
    Return PDF timeline already formatted for templates.
    """

    logs = get_pdf_timeline(
        pdf
    )

    return [
        build_timeline_entry(log)
        for log in logs
    ]


def get_quiz_timeline_entries(
    quiz,
):
    """
    Return quiz timeline already formatted for templates.
    """

    logs = get_quiz_timeline(
        quiz
    )

    return [
        build_timeline_entry(log)
        for log in logs
    ]


# ============================================================
# CONTENT COUNTS
# ============================================================

def get_chapter_content_counts(
    chapter,
):
    """
    Return common Course Builder content counts.

    Useful for both Teacher and Admin dashboards.
    """

    video_count = (
        ChapterVideo.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .count()
    )

    pdf_count = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .count()
    )

    quiz_count = (
        ChapterQuiz.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .count()
    )

    return {
        "video_count": video_count,
        "pdf_count": pdf_count,
        "quiz_count": quiz_count,
    }


# ============================================================
# CHAPTER CONTENT QUERY HELPERS
# ============================================================

def get_chapter_videos(
    chapter,
):
    """
    Return active videos for a chapter.
    """

    return (
        ChapterVideo.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .select_related(
            "created_by",
            "updated_by",
        )
        .prefetch_related(
            "change_logs__changed_by",
        )
        .order_by(
            "video_order",
            "id",
        )
    )


def get_chapter_pdfs(
    chapter,
):
    """
    Return active PDFs for a chapter.
    """

    return (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .select_related(
            "created_by",
            "updated_by",
        )
        .prefetch_related(
            "change_logs__changed_by",
        )
        .order_by(
            "pdf_order",
            "id",
        )
    )


def get_chapter_quizzes(
    chapter,
):
    """
    Return active quizzes for a chapter.
    """

    return (
        ChapterQuiz.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .select_related(
            "created_by",
            "updated_by",
        )
        .prefetch_related(
            "questions__options",
            "change_logs__changed_by",
        )
        .order_by(
            "id",
        )
    )


# ============================================================
# QUIZ DETAIL QUERY
# ============================================================

def get_quiz_with_questions(
    quiz,
):
    """
    Load a quiz together with its questions and options.

    This is useful for the Admin and Teacher edit pages.
    """

    return (
        ChapterQuiz.objects
        .filter(
            id=quiz.id,
            is_deleted=False,
        )
        .select_related(
            "created_by",
            "updated_by",
        )
        .prefetch_related(
            "questions__options",
            "change_logs__changed_by",
        )
        .first()
    )


# ============================================================
# CHAPTER DETAIL QUERY
# ============================================================

def get_chapter_with_content(
    chapter,
):
    """
    Load a chapter with its Course Builder content.

    This is a common query helper for Admin and Teacher views.
    """

    return (
        CourseChapter.objects
        .filter(
            id=chapter.id,
            is_deleted=False,
        )
        .select_related(
            "batch",
            "subject",
            "created_by",
            "updated_by",
        )
        .prefetch_related(
            "change_logs__changed_by",
        )
        .first()
    )


# ============================================================
# DELETION DOMAIN
#
# Shared deletion business logic used by both Teacher and Admin.
#
# Role behaviour stays different at the view layer:
#     - Teacher calls request_delete_* (creates a pending request)
#     - Admin calls direct_delete_* (immediate delete) or
#       approve_delete_request / reject_delete_request
#
# All audit/history/storage logic is centralized here.
# ============================================================

def _delete_storage_file(field):
    """
    Safely delete a storage file field without saving the model.
    """

    try:
        if field:
            field.delete(save=False)
    except Exception as exc:
        print("Storage cleanup warning:", exc)


def _teacher_actor_name(teacher):
    if not teacher:
        return "Teacher"
    return (
        getattr(teacher, "full_name", "")
        or getattr(getattr(teacher, "user", None), "username", "")
        or getattr(teacher, "email", "")
        or "Teacher"
    )


def _admin_actor_name(user):
    if not user:
        return "Admin"
    return (
        user.get_full_name().strip()
        or getattr(user, "username", "")
        or getattr(user, "email", "")
        or "Admin"
    )


def _content_snapshot(content_type, obj):
    """
    Build a JSON-serializable snapshot of content for a DeletionAudit.
    """

    if content_type == "chapter":
        return {
            "id": obj.id,
            "name": obj.chapter_name,
            "description": obj.chapter_description,
            "order": obj.chapter_order,
            "status": obj.status,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "created_by": _teacher_actor_name(obj.created_by) if obj.created_by else (_admin_actor_name(obj.created_by_admin) if obj.created_by_admin else "Unknown"),
        }
    if content_type == "video":
        return {
            "id": obj.id,
            "name": obj.video_name,
            "description": obj.video_description,
            "order": obj.video_order,
            "file_name": getattr(obj.video_file, "name", "") or "",
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "created_by": _teacher_actor_name(obj.created_by) if obj.created_by else (_admin_actor_name(obj.created_by_admin) if obj.created_by_admin else "Unknown"),
        }
    if content_type == "pdf":
        return {
            "id": obj.id,
            "name": obj.pdf_name,
            "description": obj.pdf_description,
            "order": obj.pdf_order,
            "file_name": getattr(obj.pdf_file, "name", "") or "",
            "thumbnail_name": getattr(obj.pdf_thumbnail, "name", "") or "",
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "created_by": _teacher_actor_name(obj.created_by) if obj.created_by else (_admin_actor_name(obj.created_by_admin) if obj.created_by_admin else "Unknown"),
        }
    if content_type == "quiz":
        questions = []
        for question in obj.questions.all():
            questions.append({
                "id": question.id,
                "text": question.question_text,
                "marks": question.marks,
                "options": [
                    {
                        "label": option.option_label,
                        "text": option.option_text,
                        "is_correct": option.is_correct,
                    }
                    for option in question.options.all()
                ],
            })
        return {
            "id": obj.id,
            "name": obj.quiz_name,
            "description": obj.quiz_description,
            "attempt_limit": obj.attempt_limit,
            "questions": questions,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "created_by": _teacher_actor_name(obj.created_by) if obj.created_by else (_admin_actor_name(obj.created_by_admin) if obj.created_by_admin else "Unknown"),
        }
    return {}


def _audit_base(content_type, obj, subject, batch):
    creator_teacher = getattr(obj, "created_by", None)
    creator_admin = getattr(obj, "created_by_admin", None)
    return {
        "content_type": content_type,
        "object_id": obj.id,
        "content_name": (
            getattr(obj, "chapter_name", None)
            or getattr(obj, "video_name", None)
            or getattr(obj, "pdf_name", None)
            or getattr(obj, "quiz_name", None)
            or f"{content_type.title()} #{obj.id}"
        ),
        "batch_name": getattr(batch, "batch_name", "") or "",
        "subject_name": getattr(subject, "subject_name", "") or "",
        "chapter_name": getattr(getattr(obj, "chapter", None), "chapter_name", "") or (
            obj.chapter_name if content_type == "chapter" else ""
        ),
        "created_by_teacher": creator_teacher,
        "created_by_admin": creator_admin,
        "created_at_original": getattr(obj, "created_at", None),
        "snapshot": _content_snapshot(content_type, obj),
    }


def _make_pending_audit(content_type, obj, subject, batch):
    requested_by = getattr(obj, "delete_requested_by", None)
    reason = getattr(obj, "delete_reason", "") or ""
    if not requested_by or not getattr(obj, "delete_requested", False) or getattr(obj, "delete_status", "") != "pending":
        return None

    audit = DeletionAudit.objects.filter(
        content_type=content_type,
        object_id=obj.id,
        status="pending",
    ).order_by("-id").first()

    defaults = _audit_base(content_type, obj, subject, batch)
    defaults.update({
        "delete_requested_by_teacher": requested_by,
        "delete_requested_at": getattr(obj, "delete_requested_at", None),
        "delete_request_reason": reason,
        "status": "pending",
    })

    if audit:
        changed = False
        for key, value in defaults.items():
            if key not in {"content_type", "object_id"} and getattr(audit, key) != value:
                setattr(audit, key, value)
                changed = True
        if changed:
            audit.save()
        return audit

    return DeletionAudit.objects.create(**defaults)


def sync_pending_deletion_audits(subject):
    """
    Create/update pending DeletionAudit records for every content
    item in a subject that currently has a pending teacher deletion
    request.
    """

    batch = subject.batch
    audits = []

    chapters = CourseChapter.objects.filter(
        batch=batch, subject=subject, is_deleted=False,
    ).select_related("created_by", "created_by_admin", "delete_requested_by")
    for obj in chapters:
        if obj.delete_requested and obj.delete_status == "pending":
            audit = _make_pending_audit("chapter", obj, subject, batch)
            if audit:
                audits.append(audit)

        videos = obj.videos.filter(is_deleted=False, delete_requested=True, delete_status="pending").select_related("created_by", "created_by_admin", "delete_requested_by")
        for child in videos:
            audit = _make_pending_audit("video", child, subject, batch)
            if audit:
                audits.append(audit)

        pdfs = obj.pdfs.filter(is_deleted=False, delete_requested=True, delete_status="pending").select_related("created_by", "created_by_admin", "delete_requested_by")
        for child in pdfs:
            audit = _make_pending_audit("pdf", child, subject, batch)
            if audit:
                audits.append(audit)

        quizzes = obj.quizzes.filter(is_deleted=False, delete_requested=True, delete_status="pending").select_related("created_by", "created_by_admin", "delete_requested_by").prefetch_related("questions__options")
        for child in quizzes:
            audit = _make_pending_audit("quiz", child, subject, batch)
            if audit:
                audits.append(audit)

    return audits


def _finalize_audit(audit, admin_user, method, admin_reason="", admin_response="", decision=""):
    audit.deleted_by_admin = admin_user
    audit.decision_by_admin = admin_user
    audit.decision_at = timezone.now()
    audit.deletion_method = method
    audit.admin_delete_reason = admin_reason or ""
    audit.admin_response = admin_response or ""
    if decision:
        audit.admin_decision = decision
    audit.status = "deleted"
    audit.deleted_at = timezone.now()
    audit.save()


def _delete_one_content(content_type, obj, subject, batch, admin_user, reason, method="admin_direct", audit=None, admin_response=""):
    if audit is None:
        audit_data = _audit_base(content_type, obj, subject, batch)
        audit = DeletionAudit.objects.create(
            **audit_data,
            deleted_by_admin=admin_user,
            decision_by_admin=admin_user,
            deletion_method=method,
            admin_delete_reason=reason,
            admin_response=admin_response,
            status="deleted",
            deleted_at=timezone.now(),
        )
    else:
        _finalize_audit(audit, admin_user, method, reason, admin_response, "approved" if method == "teacher_request_approved" else "")

    # Save the audit before the actual delete because change logs are
    # CASCADE-linked to the content and must not be the source of history.
    if content_type == "video":
        _delete_storage_file(obj.video_file)
    elif content_type == "pdf":
        _delete_storage_file(obj.pdf_file)
        _delete_storage_file(obj.pdf_thumbnail)

    obj.delete()
    return audit


def _get_admin_subject_by_names(subject_name, batch_name):
    if not subject_name:
        return None
    from admins.models import Subject
    return Subject.objects.select_related("batch").filter(subject_name=subject_name, batch__batch_name=batch_name).first()


def _get_admin_subject_from_object(obj, content_type):
    chapter = obj if content_type == "chapter" else getattr(obj, "chapter", None)
    if chapter:
        from admins.models import Subject
        return Subject.objects.select_related("batch").get(id=chapter.subject_id)
    return None


def _approve_audit(audit, admin_user):
    content_type = audit.content_type
    try:
        if content_type == "chapter":
            obj = CourseChapter.objects.get(id=audit.object_id, is_deleted=False)
        elif content_type == "video":
            obj = ChapterVideo.objects.select_related("chapter").get(id=audit.object_id, is_deleted=False)
        elif content_type == "pdf":
            obj = ChapterPDF.objects.select_related("chapter").get(id=audit.object_id, is_deleted=False)
        elif content_type == "quiz":
            obj = ChapterQuiz.objects.prefetch_related("questions__options").get(id=audit.object_id, is_deleted=False)
        else:
            return False, "Unknown content type."
    except Exception:
        audit.status = "approved"
        audit.admin_decision = "approved"
        audit.decision_by_admin = admin_user
        audit.decision_at = timezone.now()
        audit.admin_response = "The requested content was already removed or is no longer available."
        audit.deleted_at = timezone.now()
        audit.deletion_method = "teacher_request_approved"
        audit.save()
        return False, "The requested content no longer exists."

    subject = _get_admin_subject_by_names(audit.subject_name, audit.batch_name)
    if subject is None:
        subject = _get_admin_subject_from_object(obj, content_type)
    batch = subject.batch

    reason = audit.delete_request_reason or "Teacher requested deletion."

    # If a chapter is approved, preserve separate audits for every child
    # because the common audit page must be able to filter Chapter/Video/PDF/Quiz.
    if content_type == "chapter":
        children = list(obj.videos.filter(is_deleted=False).select_related("created_by", "created_by_admin"))
        children += list(obj.pdfs.filter(is_deleted=False).select_related("created_by", "created_by_admin"))
        children += list(obj.quizzes.filter(is_deleted=False).select_related("created_by", "created_by_admin").prefetch_related("questions__options"))
        for child in children:
            child_type = "video" if isinstance(child, ChapterVideo) else "pdf" if isinstance(child, ChapterPDF) else "quiz"
            child_audit = DeletionAudit.objects.filter(content_type=child_type, object_id=child.id, status="pending").order_by("-id").first()
            _delete_one_content(child_type, child, subject, batch, admin_user, reason, "teacher_request_approved", child_audit, "Teacher deletion request approved by Admin.")

    _delete_one_content(content_type, obj, subject, batch, admin_user, reason, "teacher_request_approved", audit, "Teacher deletion request approved by Admin.")
    return True, "Deletion request approved and content deleted successfully."


def request_delete(content_type, obj, actor, delete_reason):
    """
    Create a pending teacher deletion request for a content item.

    ``content_type`` is one of "chapter", "video", "pdf", "quiz".

    Returns the updated object.
    """

    obj.delete_requested = True
    obj.delete_requested_by = actor
    obj.delete_requested_at = timezone.now()
    obj.delete_reason = delete_reason or ""
    obj.delete_status = "pending"
    obj.updated_by = actor
    obj.updated_by_admin = None
    obj.save()

    if content_type == "chapter":
        ChapterChangeLog.objects.create(
            chapter=obj,
            changed_by=actor,
            action="delete_requested",
            field_name="chapter",
            old_value="",
            new_value=delete_reason or "",
            change_summary=f'Deletion requested for chapter "{obj.chapter_name}".',
        )
    elif content_type == "video":
        VideoChangeLog.objects.create(
            video=obj,
            changed_by=actor,
            action="delete_requested",
            field_name="video",
            old_value="",
            new_value=delete_reason or "",
            change_summary=f'Deletion requested for video "{obj.video_name}".',
        )
    elif content_type == "pdf":
        PDFChangeLog.objects.create(
            pdf=obj,
            changed_by=actor,
            action="delete_requested",
            field_name="pdf",
            old_value="",
            new_value=delete_reason or "",
            change_summary=f'Deletion requested for PDF "{obj.pdf_name}".',
        )
    elif content_type == "quiz":
        QuizChangeLog.objects.create(
            quiz=obj,
            changed_by=actor,
            action="delete_requested",
            field_name="quiz",
            old_value="",
            new_value=delete_reason or "",
            change_summary=f'Deletion requested for quiz "{obj.quiz_name}".',
        )

    return obj


def withdraw_delete_request(content_type, obj, actor):
    """
    Teacher withdraws a pending deletion request before Admin decides.

    Clears the pending flags on the content object, removes the pending
    DeletionAudit, and records the withdrawal in the content timeline.
    """

    if not getattr(obj, "delete_requested", False) or getattr(obj, "delete_status", "") != "pending":
        return False, "There is no pending deletion request to withdraw."

    with transaction.atomic():
        obj.delete_requested = False
        obj.delete_requested_by = None
        obj.delete_requested_at = None
        obj.delete_reason = ""
        obj.delete_status = "pending"
        obj.updated_by = actor
        obj.updated_by_admin = None
        obj.save()

        DeletionAudit.objects.filter(
            content_type=content_type,
            object_id=obj.id,
            status="pending",
        ).delete()

        if content_type == "chapter":
            ChapterChangeLog.objects.create(
                chapter=obj,
                changed_by=actor,
                action="delete_request_withdrawn",
                field_name="chapter",
                old_value="pending",
                new_value="",
                change_summary=f'Deletion request withdrawn for chapter "{obj.chapter_name}".',
            )
        elif content_type == "video":
            VideoChangeLog.objects.create(
                video=obj,
                changed_by=actor,
                action="delete_request_withdrawn",
                field_name="video",
                old_value="pending",
                new_value="",
                change_summary=f'Deletion request withdrawn for video "{obj.video_name}".',
            )
        elif content_type == "pdf":
            PDFChangeLog.objects.create(
                pdf=obj,
                changed_by=actor,
                action="delete_request_withdrawn",
                field_name="pdf",
                old_value="pending",
                new_value="",
                change_summary=f'Deletion request withdrawn for PDF "{obj.pdf_name}".',
            )
        elif content_type == "quiz":
            QuizChangeLog.objects.create(
                quiz=obj,
                changed_by=actor,
                action="delete_request_withdrawn",
                field_name="quiz",
                old_value="pending",
                new_value="",
                change_summary=f'Deletion request withdrawn for quiz "{obj.quiz_name}".',
            )

    return True, "Deletion request withdrawn successfully."


def edit_delete_request(content_type, obj, actor, new_reason):
    """
    Teacher edits the reason of a pending deletion request.

    Updates the pending flags, the pending DeletionAudit reason, and
    records the edit in the content timeline.
    """

    if not getattr(obj, "delete_requested", False) or getattr(obj, "delete_status", "") != "pending":
        return False, "There is no pending deletion request to edit."

    new_reason = (new_reason or "").strip()

    with transaction.atomic():
        obj.delete_reason = new_reason
        obj.updated_by = actor
        obj.updated_by_admin = None
        obj.save()

        DeletionAudit.objects.filter(
            content_type=content_type,
            object_id=obj.id,
            status="pending",
        ).update(delete_request_reason=new_reason)

        if content_type == "chapter":
            ChapterChangeLog.objects.create(
                chapter=obj,
                changed_by=actor,
                action="delete_request_edited",
                field_name="chapter",
                old_value="",
                new_value=new_reason,
                change_summary=f'Deletion request reason updated for chapter "{obj.chapter_name}".',
            )
        elif content_type == "video":
            VideoChangeLog.objects.create(
                video=obj,
                changed_by=actor,
                action="delete_request_edited",
                field_name="video",
                old_value="",
                new_value=new_reason,
                change_summary=f'Deletion request reason updated for video "{obj.video_name}".',
            )
        elif content_type == "pdf":
            PDFChangeLog.objects.create(
                pdf=obj,
                changed_by=actor,
                action="delete_request_edited",
                field_name="pdf",
                old_value="",
                new_value=new_reason,
                change_summary=f'Deletion request reason updated for PDF "{obj.pdf_name}".',
            )
        elif content_type == "quiz":
            QuizChangeLog.objects.create(
                quiz=obj,
                changed_by=actor,
                action="delete_request_edited",
                field_name="quiz",
                old_value="",
                new_value=new_reason,
                change_summary=f'Deletion request reason updated for quiz "{obj.quiz_name}".',
            )

    return True, "Deletion request reason updated successfully."


def direct_delete(content_type, obj, subject, batch, admin_user, reason):
    """
    Admin direct delete of a content item, recording a DeletionAudit.
    """

    return _delete_one_content(
        content_type,
        obj,
        subject,
        batch,
        admin_user,
        reason,
        method="admin_direct",
    )


def approve_delete_request(audit, admin_user, admin_response=""):
    """
    Admin approves a pending teacher deletion request.
    """

    result = _approve_audit(audit, admin_user)
    if admin_response:
        # The audit survives even if the content was deleted.
        DeletionAudit.objects.filter(id=audit.id).update(admin_response=admin_response)
    return result


def reject_delete_request(audit, admin_user, admin_response=""):
    """
    Admin rejects a pending teacher deletion request.

    Clears the pending flags on the content object and records the
    rejection in the audit and the content timeline.
    """

    content_type = audit.content_type
    try:
        if content_type == "chapter":
            obj = CourseChapter.objects.get(id=audit.object_id, is_deleted=False)
        elif content_type == "video":
            obj = ChapterVideo.objects.get(id=audit.object_id, is_deleted=False)
        elif content_type == "pdf":
            obj = ChapterPDF.objects.get(id=audit.object_id, is_deleted=False)
        elif content_type == "quiz":
            obj = ChapterQuiz.objects.get(id=audit.object_id, is_deleted=False)
        else:
            return False, "Unknown content type."
    except Exception:
        return False, "The requested content no longer exists."

    with transaction.atomic():
        obj.delete_requested = False
        obj.delete_status = "rejected"
        obj.save()

        if content_type == "chapter":
            ChapterChangeLog.objects.create(
                chapter=obj,
                changed_by_admin=admin_user,
                action="delete_rejected",
                field_name="chapter",
                old_value="pending",
                new_value="rejected",
                change_summary=f'Deletion request rejected for chapter "{obj.chapter_name}".',
            )
        elif content_type == "video":
            VideoChangeLog.objects.create(
                video=obj,
                changed_by_admin=admin_user,
                action="delete_rejected",
                field_name="video",
                old_value="pending",
                new_value="rejected",
                change_summary=f'Deletion request rejected for video "{obj.video_name}".',
            )
        elif content_type == "pdf":
            PDFChangeLog.objects.create(
                pdf=obj,
                changed_by_admin=admin_user,
                action="delete_rejected",
                field_name="pdf",
                old_value="pending",
                new_value="rejected",
                change_summary=f'Deletion request rejected for PDF "{obj.pdf_name}".',
            )
        elif content_type == "quiz":
            QuizChangeLog.objects.create(
                quiz=obj,
                changed_by_admin=admin_user,
                action="delete_rejected",
                field_name="quiz",
                old_value="pending",
                new_value="rejected",
                change_summary=f'Deletion request rejected for quiz "{obj.quiz_name}".',
            )

        audit.admin_decision = "rejected"
        audit.status = "rejected"
        audit.decision_by_admin = admin_user
        audit.decision_at = timezone.now()
        audit.admin_response = admin_response or ""
        audit.save()

    return True, "Deletion request rejected."


# ============================================================
# END OF SERVICES
# ============================================================