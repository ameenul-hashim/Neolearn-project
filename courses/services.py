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
    - admin direct deletion
    - teacher deletion requests

The caller (Teacher/Admin view) is responsible for those.
"""


# ============================================================
# DJANGO IMPORTS
# ============================================================

from django.db import transaction
from django.db.models import F


# ============================================================
# CURRENT MODEL IMPORTS
#
# IMPORTANT:
# Course Builder models are still inside teachers.models.
# We are intentionally NOT moving models in this step.
# ============================================================

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
    actor,
    chapter_name,
    chapter_description,
    status,
):
    """
    Create a new Course Chapter.

    The caller must already have verified that the actor is
    allowed to modify this batch/subject.

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
            updated_by=actor,
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
    actor,
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
    actor,
    video_name,
    video_description,
    video_file,
):
    """
    Create/upload a video.

    File validation belongs to forms.py.

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
            updated_by=actor,
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
    actor,
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
    actor,
    pdf_name,
    pdf_description,
    pdf_file,
    pdf_thumbnail=None,
):
    """
    Create/upload a PDF note.

    Validation of the PDF and thumbnail belongs in forms.py.
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
            updated_by=actor,
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
    actor,
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
    actor,
    quiz_name,
    quiz_description,
    attempt_limit,
    questions,
):
    """
    Create a complete quiz atomically.

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
            updated_by=actor,
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
    actor,
    quiz_name,
    quiz_description,
    attempt_limit,
):
    """
    Update quiz basic information.

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

        quiz.save()

        # ----------------------------------------------------
        # NAME LOG
        # ----------------------------------------------------

        if old_name != quiz_name:

            QuizChangeLog.objects.create(
                quiz=quiz,
                changed_by=actor,
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
    actor,
    question_text,
    marks,
    options,
    correct_option,
):
    """
    Add a question to an existing quiz.

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

        quiz.save(
            update_fields=[
                "updated_by",
                "updated_at",
            ]
        )

        QuizChangeLog.objects.create(
            quiz=quiz,
            changed_by=actor,
            action="question_created",
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
    actor,
    question_text,
    marks,
    options,
    correct_option,
):
    """
    Update an existing quiz question and its four options.
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

        quiz.save(
            update_fields=[
                "updated_by",
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
    actor,
):
    """
    Delete a quiz question.

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

        quiz.save(
            update_fields=[
                "updated_by",
                "updated_at",
            ]
        )

        QuizChangeLog.objects.create(
            quiz=quiz,
            changed_by=actor,
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
# END OF SERVICES
# ============================================================