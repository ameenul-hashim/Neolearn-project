from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import cloudinary.uploader

from admins.models import Batch, Subject
from teachers.models import Teacher, TeacherSubject

from .models import (
    CourseChapter,
    ChapterChangeLog,
    ChapterVideo,
    VideoChangeLog,
    ChapterPDF,
    PDFChangeLog,
    ChapterQuiz,
    QuizChangeLog,
    DeletionAudit,
)

from .ordering import (
    get_next_order,
    move_item,
    remove_item_and_close_gap,
)

from .timeline import (
    record_chapter_created,
    record_chapter_updated,
    record_chapter_order_changed,
    record_video_created,
    record_video_updated,
    record_video_order_changed,
    record_pdf_created,
    record_pdf_updated,
    record_pdf_order_changed,
    record_quiz_created,
    record_quiz_updated,
    record_quiz_order_changed,
)

# ============================================================
# CONSTANTS
# ============================================================

VALID_STATUS = {
    "draft",
    "published",
}

VALID_CONTENT_TYPES = {
    "chapter",
    "video",
    "pdf",
    "quiz",
}

VALID_BUILDER_VIEWS = {
    "videos",
    "pdfs",
    "quizzes",
    "live",
    "timeline",
    "video_timeline",
    "pdf_timeline",
    "quiz_timeline",
}

# These must exist in your Cloudinary account.
#
# They are shared permanent assets.
# They are NOT deleted when a course item is deleted.

DEFAULT_PDF_THUMBNAIL = (
    "neolearn/defaults/default_pdf_thumbnail"
)

# Upload validation.
MAX_VIDEO_SIZE_MB = 500
MAX_PDF_SIZE_MB = 50
MAX_IMAGE_SIZE_MB = 5


# ============================================================
# COMMON ACTOR / ROLE HELPERS
# ============================================================


def _get_teacher(request):
    """
    Return the Teacher profile belonging to the
    currently authenticated user.

    Never accept teacher ID from POST/GET data.
    """

    if not request.user.is_authenticated:
        return None

    try:
        return request.user.teacher_profile
    except Teacher.DoesNotExist:
        return None


def _is_admin(request):
    """
    Admin access is determined by the authenticated User.

    A browser/HTML form cannot declare itself Admin.
    """

    if not request.user.is_authenticated:
        return False

    return bool(
        request.user.is_staff
        or request.user.is_superuser
    )


def _get_actor(request):
    """
    Resolve the current actor from request.user.

    Possible results:

        Admin:
            {
                "role": "admin",
                "admin": User,
                "teacher": None,
            }

        Teacher:
            {
                "role": "teacher",
                "admin": None,
                "teacher": Teacher,
            }

        Other / anonymous:
            None
    """

    if not request.user.is_authenticated:
        return None

    if _is_admin(request):
        return {
            "role": "admin",
            "admin": request.user,
            "teacher": None,
        }

    teacher = _get_teacher(request)

    if teacher is None:
        return None

    return {
        "role": "teacher",
        "admin": None,
        "teacher": teacher,
    }


def _get_actor_name(actor):
    """
    Snapshot-friendly actor display name.
    """

    if actor["role"] == "admin":

        full_name = (
            actor["admin"]
            .get_full_name()
            .strip()
        )

        if full_name:
            return full_name

        return actor["admin"].get_username()

    teacher = actor["teacher"]

    full_name = (
        getattr(
            teacher,
            "full_name",
            "",
        )
        or ""
    ).strip()

    if full_name:
        return full_name

    user = getattr(
        teacher,
        "user",
        None,
    )

    if user is not None:

        full_name = (
            user
            .get_full_name()
            .strip()
        )

        if full_name:
            return full_name

        return user.get_username()

    return "Teacher"


def _get_actor_role(actor):
    """
    Human-readable role snapshot.
    """

    if actor["role"] == "admin":
        return "Admin"

    return "Teacher"


def _get_creator_fields(actor):
    """
    Set the original creator correctly.
    """

    if actor["role"] == "admin":

        return {
            "created_by_admin": actor["admin"],
            "created_by_teacher": None,
        }

    return {
        "created_by_admin": None,
        "created_by_teacher": actor["teacher"],
    }


def _get_updater_fields(actor):
    """
    Set the latest updater on content.

    Creation is tracked by created_by_*.
    These fields are updated only when an existing object is changed.
    """
    if actor["role"] == "admin":
        return {
            "updated_by_admin": actor["admin"],
            "updated_by_teacher": None,
        }

    return {
        "updated_by_admin": None,
        "updated_by_teacher": actor["teacher"],
    }


def _get_change_actor_fields(actor):
    """
    Timeline actor information.

    IMPORTANT:
    changed_by_name and changed_by_role are snapshots.

    Therefore the timeline still shows who performed the
    action even if the person's current profile changes later.
    """

    actor_name = _get_actor_name(actor)
    actor_role = _get_actor_role(actor)

    if actor["role"] == "admin":

        return {
            "changed_by_admin": actor["admin"],
            "changed_by_teacher": None,
            "changed_by_name": actor_name,
            "changed_by_role": actor_role,
        }

    return {
        "changed_by_admin": None,
        "changed_by_teacher": actor["teacher"],
        "changed_by_name": actor_name,
        "changed_by_role": actor_role,
    }


# ============================================================
# ROLE / ACCESS CONTROL
# ============================================================


def _get_teacher_assignment(
    teacher,
    batch,
    subject,
):
    """
    Teacher must be actively assigned to the exact
    Batch + Subject.

    A teacher assigned to another subject cannot manipulate
    this subject by changing the URL.
    """

    return (
        TeacherSubject.objects
        .filter(
            teacher=teacher,
            batch=batch,
            subject=subject,
            is_active=True,
        )
        .select_related(
            "teacher",
            "batch",
            "subject",
        )
        .first()
    )


def _authorize_builder(
    request,
    batch,
    subject,
):
    """
    Central Course Builder authorization.

    ADMIN:
        Full access.

    TEACHER:
        Only active assignment to this exact
        batch + subject.

    EVERYONE ELSE:
        Denied.
    """

    actor = _get_actor(request)

    if actor is None:
        return None

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if actor["role"] == "admin":
        return actor

    # --------------------------------------------------------
    # TEACHER
    # --------------------------------------------------------

    assignment = _get_teacher_assignment(
        actor["teacher"],
        batch,
        subject,
    )

    if assignment is None:
        return None

    actor["assignment"] = assignment

    return actor


def _authorize_admin(request):
    """
    Admin-only authorization.

    Used for sensitive deletion audit operations.
    """

    actor = _get_actor(request)

    if actor is None:
        return None

    if actor["role"] != "admin":
        return None

    return actor


def _authorize_teacher(
    request,
    batch,
    subject,
):
    """
    Teacher-only authorization.

    Used for teacher deletion requests.
    """

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )

    if actor is None:
        return None

    if actor["role"] != "teacher":
        return None

    return actor


# ============================================================
# COMMON OBJECT LOOKUPS
# ============================================================


def _get_batch_subject(
    batch_id,
    subject_id,
):
    """
    Ensure Subject actually belongs to Batch.
    """

    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    return batch, subject


def _get_chapter(
    batch,
    subject,
    chapter_id,
):
    """
    Ensure chapter belongs to exact Batch + Subject.
    """

    return get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=batch,
        subject=subject,
    )


def _get_content_object(
    batch,
    subject,
    content_type,
    object_id,
    chapter_id=None,
):
    """
    Resolve content safely.

    The chapter/batch/subject relationship is checked
    server-side for every object.
    """

    if content_type == "chapter":

        return get_object_or_404(
            CourseChapter,
            id=object_id,
            batch=batch,
            subject=subject,
        )

    if content_type == "video":

        chapter = get_object_or_404(
            CourseChapter,
            id=chapter_id,
            batch=batch,
            subject=subject,
        )

        return get_object_or_404(
            ChapterVideo,
            id=object_id,
            chapter=chapter,
        )

    if content_type == "pdf":

        chapter = get_object_or_404(
            CourseChapter,
            id=chapter_id,
            batch=batch,
            subject=subject,
        )

        return get_object_or_404(
            ChapterPDF,
            id=object_id,
            chapter=chapter,
        )

    if content_type == "quiz":

        chapter = get_object_or_404(
            CourseChapter,
            id=chapter_id,
            batch=batch,
            subject=subject,
        )

        return get_object_or_404(
            ChapterQuiz,
            id=object_id,
            chapter=chapter,
        )

    return None


# ============================================================
# COMMON REDIRECT
# ============================================================


def _builder_redirect(
    batch,
    subject,
):
    return redirect(
        "courses:course_builder",
        batch_id=batch.id,
        subject_id=subject.id,
    )


def _render_builder_form_error(
    request,
    batch,
    subject,
    actor,
    selected_chapter,
    errors,
    form_data,
    form_error_key,
    form_data_key,
    open_key,
    selected_content="videos",
    open_id=None,
):
    """
    Render the same Course Builder page after a failed POST.

    The submitted values remain available to the HTML form.
    The exact form/modal is marked as open by context.
    No JavaScript is responsible for validation or form data.
    """

    context = _get_builder_context(
        batch=batch,
        subject=subject,
        actor=actor,
        selected_chapter=selected_chapter,
        selected_content=selected_content,
    )

    context[form_error_key] = errors
    context[form_data_key] = form_data
    context[open_key] = True

    if open_id is not None:
        context[f"{open_key}_id"] = open_id

    for error in errors.values():
        messages.error(
            request,
            error,
        )

    return render(
        request,
        _builder_template(actor),
        context,
    )


# ============================================================
# COMMON TEMPLATE
# ============================================================


def _builder_template(actor):
    """
    Return the presentation template for the current
    Course Builder entry point.

    This is NOT permission logic.
    Permission is handled by _authorize_builder().
    Actor role is used here only because Admin and Teacher
    intentionally have separate templates.
    """

    if actor["role"] == "admin":
        return "admins/course_builder/admin_course_builder.html"

    return "teachers/content_builder/course_builder.html"


# ============================================================
# COMMON BUILDER CONTEXT
# ============================================================


def _get_builder_context(
    batch,
    subject,
    actor,
    selected_chapter=None,
    selected_content="videos",
):
    """
    Complete shared Course Builder context.

    Both Admin and Teacher receive the same data structure.
    Their templates remain separate.
    """

    chapters = (
        CourseChapter.objects
        .filter(
            batch=batch,
            subject=subject,
        )
        .select_related(
            "created_by_admin",
            "created_by_teacher",
        )
        .order_by(
            "chapter_order",
            "pk",
        )
    )

    if selected_chapter is None:
        selected_chapter = chapters.first()

    if selected_content not in VALID_BUILDER_VIEWS:
        selected_content = "videos"

    context = {
        "batch": batch,
        "subject": subject,

        "chapters": chapters,
        "chapter_count": chapters.count(),

        "actor": actor,
        "actor_role": actor["role"],
        "actor_name": _get_actor_name(actor),

        "selected_chapter": selected_chapter,
        "selected_content": selected_content,

        "next_chapter_order": get_next_order(
            CourseChapter.objects.filter(
                batch=batch,
                subject=subject,
            ),
            "chapter_order",
        ),

        "videos": [],
        "video_count": 0,

        "pdfs": [],
        "pdf_count": 0,

        "quizzes": [],
        "quiz_count": 0,

        "next_video_order": 1,
        "next_pdf_order": 1,
        "next_quiz_order": 1,

        "chapter_timeline": [],
        "video_timeline": [],
        "pdf_timeline": [],
        "quiz_timeline": [],

        "selected_video": None,
        "selected_pdf": None,
        "selected_quiz": None,
    }

    if selected_chapter is None:
        return context

    videos = (
        ChapterVideo.objects
        .filter(
            chapter=selected_chapter,
        )
        .order_by(
            "video_order",
            "pk",
        )
    )

    pdfs = (
        ChapterPDF.objects
        .filter(
            chapter=selected_chapter,
        )
        .order_by(
            "pdf_order",
            "pk",
        )
    )

    quizzes = (
        ChapterQuiz.objects
        .filter(
            chapter=selected_chapter,
        )
        .order_by(
            "quiz_order",
            "pk",
        )
    )

    context.update(
        {
            "videos": videos,
            "video_count": videos.count(),

            "pdfs": pdfs,
            "pdf_count": pdfs.count(),

            "quizzes": quizzes,
            "quiz_count": quizzes.count(),

            "next_video_order": get_next_order(
                ChapterVideo.objects.filter(
                    chapter=selected_chapter,
                ),
                "video_order",
            ),

            "next_pdf_order": get_next_order(
                ChapterPDF.objects.filter(
                    chapter=selected_chapter,
                ),
                "pdf_order",
            ),

            "next_quiz_order": get_next_order(
                ChapterQuiz.objects.filter(
                    chapter=selected_chapter,
                ),
                "quiz_order",
            ),
        }
    )

    return context


# ============================================================
# TIMELINE HELPERS
# ============================================================


def _log_chapter(
    chapter,
    actor,
    action,
    field_name,
    old_value,
    new_value,
    summary,
):
    ChapterChangeLog.objects.create(
        chapter=chapter,
        **_get_change_actor_fields(actor),
        action=action,
        field_name=field_name,
        old_value=str(old_value),
        new_value=str(new_value),
        change_summary=summary,
    )


def _log_video(
    video,
    actor,
    action,
    field_name,
    old_value,
    new_value,
    summary,
):
    VideoChangeLog.objects.create(
        video=video,
        **_get_change_actor_fields(actor),
        action=action,
        field_name=field_name,
        old_value=str(old_value),
        new_value=str(new_value),
        change_summary=summary,
    )


def _log_pdf(
    pdf,
    actor,
    action,
    field_name,
    old_value,
    new_value,
    summary,
):
    PDFChangeLog.objects.create(
        pdf=pdf,
        **_get_change_actor_fields(actor),
        action=action,
        field_name=field_name,
        old_value=str(old_value),
        new_value=str(new_value),
        change_summary=summary,
    )


def _log_quiz(
    quiz,
    actor,
    action,
    field_name,
    old_value,
    new_value,
    summary,
):
    QuizChangeLog.objects.create(
        quiz=quiz,
        **_get_change_actor_fields(actor),
        action=action,
        field_name=field_name,
        old_value=str(old_value),
        new_value=str(new_value),
        change_summary=summary,
    )


# ============================================================
# CLOUDINARY HELPERS
# ============================================================


def _get_cloudinary_public_id(value):
    """
    Get the Cloudinary public ID from CloudinaryField.
    """

    if not value:
        return ""

    public_id = getattr(
        value,
        "public_id",
        None,
    )

    if public_id:
        return public_id

    value_string = str(value)

    if not value_string:
        return ""

    return value_string


def _is_default_asset(public_id):
    """
    Default thumbnails are shared assets.

    NEVER delete them when content is deleted/replaced.
    """

    if not public_id:
        return False

    return public_id.startswith(
        "neolearn/defaults/"
    )


def _destroy_cloudinary_asset(
    value,
    resource_type,
):
    """
    Delete one Cloudinary asset.

    This is intentionally defensive.
    Cloudinary cleanup failure should not corrupt the
    already-successful database transaction.
    """

    public_id = _get_cloudinary_public_id(
        value
    )

    if not public_id:
        return

    if _is_default_asset(public_id):
        return

    try:
        cloudinary.uploader.destroy(
            public_id,
            resource_type=resource_type,
            type="upload",
            invalidate=True,
        )
    except Exception:
        # Do not make a successful DB operation fail
        # only because remote cleanup failed.
        pass


def _destroy_cloudinary_public_id(
    public_id,
    resource_type,
):
    """
    Delete an already captured public ID.
    """

    if not public_id:
        return

    if _is_default_asset(public_id):
        return

    try:
        cloudinary.uploader.destroy(
            public_id,
            resource_type=resource_type,
            type="upload",
            invalidate=True,
        )
    except Exception:
        pass


def _capture_video_assets(video):
    """
    Capture video Cloudinary assets before deletion/replacement.
    """

    return [
        (
            _get_cloudinary_public_id(
                video.video_file
            ),
            "video",
        ),
    ]


def _capture_pdf_assets(pdf):
    """
    Capture PDF Cloudinary assets before deletion/replacement.
    """

    return [
        (
            _get_cloudinary_public_id(
                pdf.pdf_file
            ),
            "raw",
        ),
        (
            _get_cloudinary_public_id(
                pdf.pdf_thumbnail
            ),
            "image",
        ),
    ]


def _capture_chapter_assets(chapter):
    """
    A chapter may own child videos and PDFs.

    When the chapter is permanently deleted, capture all
    child Cloudinary assets before Django cascades the rows.
    """

    assets = []

    videos = ChapterVideo.objects.filter(
        chapter=chapter,
    )

    pdfs = ChapterPDF.objects.filter(
        chapter=chapter,
    )

    for video in videos:
        assets.extend(
            _capture_video_assets(video)
        )

    for pdf in pdfs:
        assets.extend(
            _capture_pdf_assets(pdf)
        )

    return assets


def _schedule_cloudinary_cleanup(assets):
    """
    Schedule remote cleanup only after the DB transaction
    successfully commits.
    """

    cleaned = set()

    def cleanup():
        for (
            public_id,
            resource_type,
        ) in assets:

            if not public_id:
                continue

            key = (
                public_id,
                resource_type,
            )

            if key in cleaned:
                continue

            cleaned.add(key)

            _destroy_cloudinary_public_id(
                public_id,
                resource_type,
            )

    transaction.on_commit(cleanup)


# ============================================================
# SERVER-SIDE FILE VALIDATION
# ============================================================


def _validate_upload(
    uploaded_file,
    allowed_extensions,
    allowed_mime_types,
    max_size_mb,
):
    """
    Generic server-side upload validation.
    """

    if uploaded_file is None:
        return "File is required."

    filename = (
        uploaded_file.name
        or ""
    ).strip()

    if "." not in filename:
        return "The uploaded file has no valid extension."

    extension = (
        filename
        .rsplit(".", 1)[1]
        .lower()
    )

    if extension not in allowed_extensions:
        return (
            "Invalid file type. "
            "Please upload a supported file."
        )

    content_type = (
        getattr(
            uploaded_file,
            "content_type",
            "",
        )
        or ""
    ).lower()

    if (
        allowed_mime_types
        and content_type
        and content_type not in allowed_mime_types
    ):
        return (
            "Invalid file format."
        )

    max_bytes = (
        max_size_mb
        * 1024
        * 1024
    )

    if uploaded_file.size > max_bytes:
        return (
            f"File size cannot exceed "
            f"{max_size_mb} MB."
        )

    return None


def _validate_video_file(
    uploaded_file,
):
    return _validate_upload(
        uploaded_file=uploaded_file,
        allowed_extensions={
            "mp4",
            "mov",
            "m4v",
            "webm",
        },
        allowed_mime_types={
            "video/mp4",
            "video/quicktime",
            "video/webm",
            "video/x-m4v",
        },
        max_size_mb=MAX_VIDEO_SIZE_MB,
    )


def _validate_pdf_file(
    uploaded_file,
):
    return _validate_upload(
        uploaded_file=uploaded_file,
        allowed_extensions={
            "pdf",
        },
        allowed_mime_types={
            "application/pdf",
        },
        max_size_mb=MAX_PDF_SIZE_MB,
    )


def _validate_image_file(
    uploaded_file,
):
    return _validate_upload(
        uploaded_file=uploaded_file,
        allowed_extensions={
            "jpg",
            "jpeg",
            "png",
            "webp",
        },
        allowed_mime_types={
            "image/jpeg",
            "image/png",
            "image/webp",
        },
        max_size_mb=MAX_IMAGE_SIZE_MB,
    )


# ============================================================
# COURSE BUILDER
# ============================================================


def course_builder_view(
    request,
    batch_id,
    subject_id,
):
    """
    Main Course Builder.

    Shared backend.

    Admin:
        full access.

    Teacher:
        active assignment required.
    """

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )

    if actor is None:

        messages.error(
            request,
            "You do not have permission to access this course builder.",
        )

        return redirect(
            "teacher_login"
        )

    selected_chapter = None

    chapter_id = (
        request.GET.get(
            "chapter"
        )
    )

    if chapter_id:

        try:
            selected_chapter = _get_chapter(
                batch,
                subject,
                int(chapter_id),
            )
        except (
            ValueError,
            TypeError,
        ):
            selected_chapter = None

    selected_content = (
        request.GET.get(
            "view",
            "videos",
        )
        or "videos"
    ).strip().lower()

    context = _get_builder_context(
        batch=batch,
        subject=subject,
        actor=actor,
        selected_chapter=selected_chapter,
        selected_content=selected_content,
    )

    # --------------------------------------------------------
    # CHAPTER TIMELINE
    # --------------------------------------------------------

    if (
        selected_chapter is not None
        and selected_content == "timeline"
    ):

        context["chapter_timeline"] = (
            ChapterChangeLog.objects
            .filter(
                chapter=selected_chapter,
            )
            .select_related(
                "changed_by_admin",
                "changed_by_teacher",
            )
            .order_by(
                "-changed_at",
                "-id",
            )
        )

    # --------------------------------------------------------
    # VIDEO TIMELINE
    # --------------------------------------------------------

    if (
        selected_chapter is not None
        and selected_content == "video_timeline"
    ):

        item_id = request.GET.get(
            "item"
        )

        try:

            selected_video = get_object_or_404(
                ChapterVideo,
                id=int(item_id),
                chapter=selected_chapter,
            )

            context["selected_video"] = (
                selected_video
            )

            context["video_timeline"] = (
                VideoChangeLog.objects
                .filter(
                    video=selected_video,
                )
                .select_related(
                    "changed_by_admin",
                    "changed_by_teacher",
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

        except (
            ValueError,
            TypeError,
        ):
            pass

    # --------------------------------------------------------
    # PDF TIMELINE
    # --------------------------------------------------------

    if (
        selected_chapter is not None
        and selected_content == "pdf_timeline"
    ):

        item_id = request.GET.get(
            "item"
        )

        try:

            selected_pdf = get_object_or_404(
                ChapterPDF,
                id=int(item_id),
                chapter=selected_chapter,
            )

            context["selected_pdf"] = (
                selected_pdf
            )

            context["pdf_timeline"] = (
                PDFChangeLog.objects
                .filter(
                    pdf=selected_pdf,
                )
                .select_related(
                    "changed_by_admin",
                    "changed_by_teacher",
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

        except (
            ValueError,
            TypeError,
        ):
            pass

    # --------------------------------------------------------
    # QUIZ TIMELINE
    # --------------------------------------------------------

    if (
        selected_chapter is not None
        and selected_content == "quiz_timeline"
    ):

        item_id = request.GET.get(
            "item"
        )

        try:

            selected_quiz = get_object_or_404(
                ChapterQuiz,
                id=int(item_id),
                chapter=selected_chapter,
            )

            context["selected_quiz"] = (
                selected_quiz
            )

            context["quiz_timeline"] = (
                QuizChangeLog.objects
                .filter(
                    quiz=selected_quiz,
                )
                .select_related(
                    "changed_by_admin",
                    "changed_by_teacher",
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

        except (
            ValueError,
            TypeError,
        ):
            pass

    return render(
        request,
        _builder_template(actor),
        context,
    )


# ============================================================
# CHAPTER CREATE
# ============================================================


@require_POST
def create_chapter_view(
    request,
    batch_id,
    subject_id,
):
    """
    Admin + assigned Teacher can create chapters.

    Teacher cannot use this view unless actively assigned.
    """

    # --------------------------------------------------------
    # GET BATCH + SUBJECT
    # --------------------------------------------------------

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    # --------------------------------------------------------
    # AUTHORIZE ADMIN / ASSIGNED TEACHER
    # --------------------------------------------------------

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )

    if actor is None:

        messages.error(
            request,
            "You do not have permission to create a chapter.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    # --------------------------------------------------------
    # READ FORM DATA
    # --------------------------------------------------------

    chapter_name = (
        request.POST.get(
            "chapter_name",
            "",
        )
        .strip()
    )

    chapter_description = (
        request.POST.get(
            "chapter_description",
            "",
        )
        .strip()
    )

    status = (
        request.POST.get(
            "status",
            "draft",
        )
        .strip()
        .lower()
        or "draft"
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    errors = {}

    if not chapter_name:

        errors["chapter_name"] = (
            "Please enter the chapter name."
        )

    elif len(chapter_name) > 100:

        errors["chapter_name"] = (
            "Chapter name cannot exceed 100 characters."
        )

    if not chapter_description:

        errors["chapter_description"] = (
            "Please enter the chapter description."
        )

    elif len(chapter_description) > 250:

        errors["chapter_description"] = (
            "Chapter description cannot exceed 250 characters."
        )

    if status not in VALID_STATUS:

        errors["status"] = (
            "Please select a valid chapter status."
        )

    # --------------------------------------------------------
    # DUPLICATE CHAPTER NAME
    # --------------------------------------------------------

    if chapter_name:

        duplicate = (
            CourseChapter.objects
            .filter(
                batch=batch,
                subject=subject,
                chapter_name__iexact=chapter_name,
            )
            .exists()
        )

        if duplicate:

            errors["chapter_name"] = (
                "A chapter with this name already exists."
            )

    # --------------------------------------------------------
    # VALIDATION FAILED
    # --------------------------------------------------------

    if errors:

        return _render_builder_form_error(
            request=request,
            batch=batch,
            subject=subject,
            actor=actor,
            selected_chapter=None,
            errors=errors,
            form_data={
                "chapter_name": chapter_name,
                "chapter_description": chapter_description,
                "status": status,
            },
            form_error_key="chapter_form_errors",
            form_data_key="chapter_form_data",
            open_key="chapter_create_open",
            selected_content=(
                request.POST.get(
                    "builder_view",
                    "videos",
                )
                or "videos"
            ),
        )

    # --------------------------------------------------------
    # CREATE CHAPTER
    # --------------------------------------------------------

    with transaction.atomic():

        queryset = CourseChapter.objects.filter(
            batch=batch,
            subject=subject,
        )

        chapter_order = get_next_order(
            queryset,
            "chapter_order",
        )

        chapter = CourseChapter.objects.create(
            batch=batch,
            subject=subject,
            chapter_name=chapter_name,
            chapter_description=chapter_description,
            chapter_order=chapter_order,
            status=status,
            **_get_creator_fields(actor),
        )

        # ----------------------------------------------------
        # CHAPTER CREATION TIMELINE
        # ----------------------------------------------------

        record_chapter_created(
            chapter=chapter,
            admin=(
                actor["admin"]
                if actor["role"] == "admin"
                else None
            ),
            teacher=(
                actor["teacher"]
                if actor["role"] == "teacher"
                else None
            ),
        )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    messages.success(
        request,
        "Chapter created successfully.",
    )

    # --------------------------------------------------------
    # PRG REDIRECT
    # --------------------------------------------------------

    return _builder_redirect(
        batch,
        subject,
    )
# ============================================================
# CHAPTER EDIT
# ============================================================


# ============================================================
# CHAPTER EDIT
# ============================================================


@require_POST
def edit_chapter_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    """
    Admin + assigned Teacher can edit a chapter.

    All chapter edit fields are submitted through one POST:

        chapter_name
        chapter_description
        status
        chapter_order

    Ordering is handled through the existing
    courses.ordering.move_item() helper.

    Validation, authorization, ordering, saving and
    timeline creation are handled completely server-side.
    """

    # --------------------------------------------------------
    # GET BATCH + SUBJECT
    # --------------------------------------------------------

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    # --------------------------------------------------------
    # AUTHORIZE ADMIN / ASSIGNED TEACHER
    # --------------------------------------------------------

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )

    if actor is None:

        messages.error(
            request,
            "You do not have permission to edit this chapter.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    # --------------------------------------------------------
    # GET EXACT CHAPTER
    # --------------------------------------------------------

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    # --------------------------------------------------------
    # READ FORM DATA
    # --------------------------------------------------------

    chapter_name = (
        request.POST.get(
            "chapter_name",
            "",
        )
        .strip()
    )

    chapter_description = (
        request.POST.get(
            "chapter_description",
            "",
        )
        .strip()
    )

    status = (
        request.POST.get(
            "status",
            "",
        )
        .strip()
        .lower()
    )

    raw_order = (
        request.POST.get(
            "chapter_order",
            "",
        )
        .strip()
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    errors = {}

    # --------------------------------------------------------
    # CHAPTER NAME
    # --------------------------------------------------------

    if not chapter_name:

        errors["chapter_name"] = (
            "Please enter the chapter name."
        )

    elif len(chapter_name) > 100:

        errors["chapter_name"] = (
            "Chapter name cannot exceed 100 characters."
        )

    # --------------------------------------------------------
    # CHAPTER DESCRIPTION
    # --------------------------------------------------------

    if not chapter_description:

        errors["chapter_description"] = (
            "Please enter the chapter description."
        )

    elif len(chapter_description) > 250:

        errors["chapter_description"] = (
            "Chapter description cannot exceed 250 characters."
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if status not in VALID_STATUS:

        errors["status"] = (
            "Please select a valid chapter status."
        )

    # --------------------------------------------------------
    # CHAPTER ORDER
    # --------------------------------------------------------

    new_order = None

    try:

        new_order = int(raw_order)

        if new_order < 1:
            raise ValueError

    except (
        ValueError,
        TypeError,
    ):

        errors["chapter_order"] = (
            "Chapter order must be a valid number."
        )

    # --------------------------------------------------------
    # CHAPTER ORDER MAXIMUM
    # --------------------------------------------------------

    chapter_queryset = CourseChapter.objects.filter(
        batch=batch,
        subject=subject,
    )

    chapter_count = chapter_queryset.count()

    if (
        new_order is not None
        and new_order > chapter_count
    ):

        errors["chapter_order"] = (
            f"Chapter order must be between "
            f"1 and {chapter_count}."
        )

    # --------------------------------------------------------
    # DUPLICATE CHAPTER NAME
    # --------------------------------------------------------

    if chapter_name:

        duplicate = (
            CourseChapter.objects
            .filter(
                batch=batch,
                subject=subject,
                chapter_name__iexact=chapter_name,
            )
            .exclude(
                pk=chapter.pk,
            )
            .exists()
        )

        if duplicate:

            errors["chapter_name"] = (
                "A chapter with this name already exists."
            )

    # --------------------------------------------------------
    # VALIDATION FAILED
    # --------------------------------------------------------

    if errors:

        return _render_builder_form_error(
            request=request,
            batch=batch,
            subject=subject,
            actor=actor,
            selected_chapter=chapter,
            errors=errors,
            form_data={
                "chapter_name": chapter_name,
                "chapter_description": chapter_description,
                "chapter_order": raw_order,
                "status": status,
            },
            form_error_key="chapter_edit_form_errors",
            form_data_key="chapter_edit_form_data",
            open_key="chapter_edit_open",
            selected_content=(
                request.POST.get(
                    "builder_view",
                    "videos",
                )
                or "videos"
            ),
            open_id=chapter.id,
        )

    # --------------------------------------------------------
    # CAPTURE OLD VALUES
    # --------------------------------------------------------

    old_name = chapter.chapter_name

    old_description = (
        chapter.chapter_description
    )

    old_status = chapter.status

    old_order = chapter.chapter_order

    # --------------------------------------------------------
    # BUILD FIELD CHANGES
    # --------------------------------------------------------

    changes = []

    if old_name != chapter_name:

        changes.append(
            (
                "chapter_name",
                old_name,
                chapter_name,
            )
        )

    if old_description != chapter_description:

        changes.append(
            (
                "chapter_description",
                old_description,
                chapter_description,
            )
        )

    if old_status != status:

        changes.append(
            (
                "status",
                old_status,
                status,
            )
        )

    # --------------------------------------------------------
    # UPDATE CHAPTER
    # --------------------------------------------------------

    with transaction.atomic():

        # ----------------------------------------------------
        # ORDER CHANGE
        # ----------------------------------------------------

        if old_order != new_order:

            try:

                move_item(
                    item=chapter,
                    queryset=CourseChapter.objects.filter(
                        batch=batch,
                        subject=subject,
                    ),
                    order_field="chapter_order",
                    new_order=new_order,
                )

            except ValueError as exc:

                errors["chapter_order"] = str(exc)

                return _render_builder_form_error(
                    request=request,
                    batch=batch,
                    subject=subject,
                    actor=actor,
                    selected_chapter=chapter,
                    errors=errors,
                    form_data={
                        "chapter_name": chapter_name,
                        "chapter_description": (
                            chapter_description
                        ),
                        "chapter_order": raw_order,
                        "status": status,
                    },
                    form_error_key="chapter_edit_form_errors",
                    form_data_key="chapter_edit_form_data",
                    open_key="chapter_edit_open",
                    selected_content=(
                        request.POST.get(
                            "builder_view",
                            "videos",
                        )
                        or "videos"
                    ),
                    open_id=chapter.id,
                )

            # ------------------------------------------------
            # ORDER TIMELINE
            # ------------------------------------------------

            record_chapter_order_changed(
                chapter=chapter,
                old_order=old_order,
                new_order=new_order,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

        # ----------------------------------------------------
        # UPDATE NORMAL CHAPTER FIELDS
        # ----------------------------------------------------

        chapter.chapter_name = chapter_name

        chapter.chapter_description = (
            chapter_description
        )

        chapter.status = status

        # ----------------------------------------------------
        # UPDATE LAST MODIFIED ACTOR
        # ----------------------------------------------------

        chapter.updated_by_admin = (
            actor["admin"]
            if actor["role"] == "admin"
            else None
        )

        chapter.updated_by_teacher = (
            actor["teacher"]
            if actor["role"] == "teacher"
            else None
        )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        chapter.save()

        # ----------------------------------------------------
        # FIELD UPDATE TIMELINE
        # ----------------------------------------------------

        for (
            field_name,
            old_value,
            new_value,
        ) in changes:

            record_chapter_updated(
                chapter=chapter,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    messages.success(
        request,
        "Chapter updated successfully.",
    )

    # --------------------------------------------------------
    # PRG REDIRECT
    # --------------------------------------------------------

    return _builder_redirect(
        batch,
        subject,
    )
    
# --------------------------------------------------------
# CHAPTER DETAILS
# ============================================================


def chapter_details_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    """
    Read-only Chapter Details page.

    This is the backend endpoint for the Chapter Details screen.

    ADMIN:
        Full access to the chapter details.

    TEACHER:
        Access only when actively assigned to the exact
        Batch + Subject.

    The page shows:

        - Batch
        - Subject
        - Chapter information
        - Original creator
        - Creator role
        - Created / updated timestamps
        - Video / PDF / Quiz counts
        - Content items belonging to this chapter
        - Complete Chapter Timeline
        - Timeline actor name
        - Timeline actor role
        - Before / After values

    This view does NOT create or modify anything.
    It is intentionally read-only.
    """

    # --------------------------------------------------------
    # GET BATCH + SUBJECT
    # --------------------------------------------------------

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    # --------------------------------------------------------
    # AUTHORIZE ADMIN / ASSIGNED TEACHER
    # --------------------------------------------------------

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )

    if actor is None:
        messages.error(
            request,
            "You do not have permission to view this chapter.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    # --------------------------------------------------------
    # GET EXACT CHAPTER
    # --------------------------------------------------------

    chapter = get_object_or_404(
        CourseChapter.objects.select_related(
            "created_by_admin",
            "created_by_teacher",
            "created_by_teacher__user",
        ),
        id=chapter_id,
        batch=batch,
        subject=subject,
    )

    # --------------------------------------------------------
    # ORIGINAL CREATOR
    # --------------------------------------------------------

    creator_name = "Unknown"
    creator_role = "Unknown"

    if chapter.created_by_admin is not None:
        creator_name = (
            chapter.created_by_admin.get_full_name().strip()
        )

        if not creator_name:
            creator_name = (
                chapter.created_by_admin.get_username()
            )

        creator_role = "Admin"

    elif chapter.created_by_teacher is not None:
        teacher = chapter.created_by_teacher

        creator_name = (
            getattr(
                teacher,
                "full_name",
                "",
            )
            or ""
        ).strip()

        if not creator_name:
            user = getattr(
                teacher,
                "user",
                None,
            )

            if user is not None:
                creator_name = (
                    user.get_full_name().strip()
                )

                if not creator_name:
                    creator_name = (
                        user.get_username()
                    )

        if not creator_name:
            creator_name = "Teacher"

        creator_role = "Teacher"

    # --------------------------------------------------------
    # CONTENT
    # --------------------------------------------------------

    videos = (
        ChapterVideo.objects
        .filter(
            chapter=chapter,
        )
        .order_by(
            "video_order",
            "pk",
        )
    )

    pdfs = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
        )
        .order_by(
            "pdf_order",
            "pk",
        )
    )

    quizzes = (
        ChapterQuiz.objects
        .filter(
            chapter=chapter,
        )
        .order_by(
            "quiz_order",
            "pk",
        )
    )

    # --------------------------------------------------------
    # CHAPTER TIMELINE
    # --------------------------------------------------------

    chapter_timeline = (
        ChapterChangeLog.objects
        .filter(
            chapter=chapter,
        )
        .select_related(
            "changed_by_admin",
            "changed_by_teacher",
            "changed_by_teacher__user",
        )
        .order_by(
            "-changed_at",
            "-id",
        )
    )

    # --------------------------------------------------------
    # LAST CHANGE
    # --------------------------------------------------------

    last_change = (
        chapter_timeline.first()
    )

    # --------------------------------------------------------
    # CURRENT PAGE ACTOR
    # --------------------------------------------------------

    actor_name = _get_actor_name(actor)
    actor_role = _get_actor_role(actor)

    # --------------------------------------------------------
    # RENDER
    # --------------------------------------------------------

    return render(
        request,
        "courses/chapter_details.html",
        {
            "batch": batch,
            "subject": subject,
            "chapter": chapter,

            "creator_name": creator_name,
            "creator_role": creator_role,

            "videos": videos,
            "video_count": videos.count(),

            "pdfs": pdfs,
            "pdf_count": pdfs.count(),

            "quizzes": quizzes,
            "quiz_count": quizzes.count(),

            "chapter_timeline": chapter_timeline,
            "last_change": last_change,

            "actor": actor,
            "actor_name": actor_name,
            "actor_role": actor_role,
        },
    )


# ============================================================
# VIDEO CREATE
# ============================================================


@require_POST
def create_video_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    """
    Admin + assigned Teacher can create a video.

    Video fields:
        - video_name
        - video_description
        - video_file
        - status

    Video order is assigned automatically.

    Video thumbnail is intentionally not used.
    """

    # --------------------------------------------------------
    # GET BATCH + SUBJECT
    # --------------------------------------------------------

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    # --------------------------------------------------------
    # AUTHORIZE ADMIN / ASSIGNED TEACHER
    # --------------------------------------------------------

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )

    if actor is None:

        messages.error(
            request,
            "You do not have permission to create a video.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    # --------------------------------------------------------
    # GET CHAPTER
    # --------------------------------------------------------

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    # --------------------------------------------------------
    # READ FORM DATA
    # --------------------------------------------------------

    video_name = (
        request.POST.get(
            "video_name",
            "",
        )
        .strip()
    )

    video_description = (
        request.POST.get(
            "video_description",
            "",
        )
        .strip()
    )

    status = (
        request.POST.get(
            "status",
            "draft",
        )
        .strip()
        .lower()
        or "draft"
    )

    video_file = request.FILES.get(
        "video_file",
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    errors = {}

    # VIDEO NAME
    if not video_name:

        errors["video_name"] = (
            "Please enter the video name."
        )

    elif len(video_name) > 100:

        errors["video_name"] = (
            "Video name cannot exceed 100 characters."
        )

    # VIDEO DESCRIPTION
    if not video_description:

        errors["video_description"] = (
            "Please enter the video description."
        )

    elif len(video_description) > 250:

        errors["video_description"] = (
            "Video description cannot exceed 250 characters."
        )

    # VIDEO FILE
    if not video_file:

        errors["video_file"] = (
            "Please select a video file."
        )

    else:

        error = _validate_video_file(
            video_file,
        )

        if error:

            errors["video_file"] = error

    # STATUS
    if status not in VALID_STATUS:

        errors["status"] = (
            "Please select a valid video status."
        )

    # DUPLICATE VIDEO NAME
    if video_name:

        duplicate = (
            ChapterVideo.objects
            .filter(
                chapter=chapter,
                video_name__iexact=video_name,
            )
            .exists()
        )

        if duplicate:

            errors["video_name"] = (
                "A video with this name already exists."
            )

    # --------------------------------------------------------
    # VALIDATION FAILED
    # --------------------------------------------------------

    if errors:

        return _render_builder_form_error(
            request=request,
            batch=batch,
            subject=subject,
            actor=actor,
            selected_chapter=chapter,
            errors=errors,
            form_data={
                "video_name": video_name,
                "video_description": video_description,
                "status": status,
            },
            form_error_key="video_form_errors",
            form_data_key="video_form_data",
            open_key="video_create_open",
            selected_content="videos",
        )

    # --------------------------------------------------------
    # CREATE VIDEO
    # --------------------------------------------------------

    with transaction.atomic():

        queryset = ChapterVideo.objects.filter(
            chapter=chapter,
        )

        video_order = get_next_order(
            queryset,
            "video_order",
        )

        video = ChapterVideo.objects.create(
            chapter=chapter,
            video_name=video_name,
            video_description=video_description,
            video_file=video_file,
            video_order=video_order,
            status=status,
            **_get_creator_fields(actor),
        )

        # ----------------------------------------------------
        # VIDEO CREATION TIMELINE
        # ----------------------------------------------------

        record_video_created(
            video=video,
            admin=(
                actor["admin"]
                if actor["role"] == "admin"
                else None
            ),
            teacher=(
                actor["teacher"]
                if actor["role"] == "teacher"
                else None
            ),
        )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    messages.success(
        request,
        "Video created successfully.",
    )

    # --------------------------------------------------------
    # PRG REDIRECT
    # --------------------------------------------------------

    return _builder_redirect(
        batch,
        subject,
    )
# ============================================================
# VIDEO EDIT
# ============================================================


# ============================================================
# VIDEO EDIT
# ============================================================


@require_POST
def edit_video_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    video_id,
):
    """
    Admin + assigned Teacher can edit a video.

    Editable fields:
        - video_name
        - video_description
        - video_file
        - status
        - video_order

    Video thumbnail is intentionally not used.

    Video order is changed through this same Edit form.

    Timeline:
        - One entry for every changed basic field.
        - One separate entry for video file replacement.
        - One separate entry for order change.
    """

    # --------------------------------------------------------
    # GET BATCH + SUBJECT
    # --------------------------------------------------------

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    # --------------------------------------------------------
    # AUTHORIZE ADMIN / ASSIGNED TEACHER
    # --------------------------------------------------------

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )

    if actor is None:

        messages.error(
            request,
            "You do not have permission to edit this video.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    # --------------------------------------------------------
    # GET CHAPTER
    # --------------------------------------------------------

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    # --------------------------------------------------------
    # GET EXACT VIDEO
    # --------------------------------------------------------

    video = get_object_or_404(
        ChapterVideo,
        id=video_id,
        chapter=chapter,
    )

    # --------------------------------------------------------
    # READ FORM DATA
    # --------------------------------------------------------

    video_name = (
        request.POST.get(
            "video_name",
            "",
        )
        .strip()
    )

    video_description = (
        request.POST.get(
            "video_description",
            "",
        )
        .strip()
    )

    status = (
        request.POST.get(
            "status",
            "",
        )
        .strip()
        .lower()
    )

    raw_order = (
        request.POST.get(
            "video_order",
            "",
        )
        .strip()
    )

    new_video_file = request.FILES.get(
        "video_file",
    )

    # --------------------------------------------------------
    # KEEP ORIGINAL VALUES FOR CHANGE DETECTION
    # --------------------------------------------------------

    old_name = video.video_name
    old_description = video.video_description
    old_status = video.status
    old_order = video.video_order
    old_video_file = video.video_file

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    errors = {}

    # --------------------------------------------------------
    # VIDEO NAME
    # --------------------------------------------------------

    if not video_name:

        errors["video_name"] = (
            "Please enter the video name."
        )

    elif len(video_name) > 100:

        errors["video_name"] = (
            "Video name cannot exceed 100 characters."
        )

    # --------------------------------------------------------
    # VIDEO DESCRIPTION
    # --------------------------------------------------------

    if not video_description:

        errors["video_description"] = (
            "Please enter the video description."
        )

    elif len(video_description) > 250:

        errors["video_description"] = (
            "Video description cannot exceed 250 characters."
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if status not in VALID_STATUS:

        errors["status"] = (
            "Please select a valid video status."
        )

    # --------------------------------------------------------
    # VIDEO ORDER
    # --------------------------------------------------------

    new_order = None

    if not raw_order:

        errors["video_order"] = (
            "Please enter the video order."
        )

    else:

        try:

            new_order = int(raw_order)

            if isinstance(
                new_order,
                bool,
            ):
                raise ValueError

        except (
            ValueError,
            TypeError,
        ):

            errors["video_order"] = (
                "Video order must be a valid number."
            )

    # --------------------------------------------------------
    # VALIDATE VIDEO ORDER RANGE
    # --------------------------------------------------------

    if (
        new_order is not None
        and "video_order" not in errors
    ):

        video_queryset = (
            ChapterVideo.objects
            .filter(
                chapter=chapter,
            )
        )

        video_count = video_queryset.count()

        if new_order < 1:

            errors["video_order"] = (
                "Video order must be at least 1."
            )

        elif new_order > video_count:

            errors["video_order"] = (
                f"Video order cannot be greater than "
                f"{video_count}."
            )

    # --------------------------------------------------------
    # OPTIONAL VIDEO FILE
    # --------------------------------------------------------

    if new_video_file:

        error = _validate_video_file(
            new_video_file,
        )

        if error:

            errors["video_file"] = error

    # --------------------------------------------------------
    # DUPLICATE VIDEO NAME
    # --------------------------------------------------------

    if video_name:

        duplicate = (
            ChapterVideo.objects
            .filter(
                chapter=chapter,
                video_name__iexact=video_name,
            )
            .exclude(
                id=video.id,
            )
            .exists()
        )

        if duplicate:

            errors["video_name"] = (
                "A video with this name already exists."
            )

    # --------------------------------------------------------
    # VALIDATION FAILED
    # --------------------------------------------------------

    if errors:

        return _render_builder_form_error(
            request=request,
            batch=batch,
            subject=subject,
            actor=actor,
            selected_chapter=chapter,
            errors=errors,
            form_data={
                "video_name": video_name,
                "video_description": video_description,
                "status": status,
                "video_order": raw_order,
            },
            form_error_key="video_edit_form_errors",
            form_data_key="video_edit_form_data",
            open_key="video_edit_open",
            selected_content="videos",
            open_id=video.id,
        )

    # --------------------------------------------------------
    # DETECT BASIC FIELD CHANGES
    # --------------------------------------------------------

    changes = []

    if old_name != video_name:

        changes.append(
            (
                "video_name",
                old_name,
                video_name,
            )
        )

    if old_description != video_description:

        changes.append(
            (
                "video_description",
                old_description,
                video_description,
            )
        )

    if old_status != status:

        changes.append(
            (
                "status",
                old_status,
                status,
            )
        )

    # --------------------------------------------------------
    # CAPTURE OLD CLOUDINARY VIDEO
    # BEFORE REPLACEMENT
    # --------------------------------------------------------

    old_video_public_id = (
        _get_cloudinary_public_id(
            old_video_file,
        )
        if new_video_file
        else ""
    )

    # --------------------------------------------------------
    # SAVE EVERYTHING IN ONE TRANSACTION
    # --------------------------------------------------------

    with transaction.atomic():

        # ----------------------------------------------------
        # VIDEO ORDER
        # ----------------------------------------------------

        if old_order != new_order:

            move_item(
                item=video,
                queryset=ChapterVideo.objects.filter(
                    chapter=chapter,
                ),
                order_field="video_order",
                new_order=new_order,
            )

            record_video_order_changed(
                video=video,
                old_order=old_order,
                new_order=new_order,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

        # ----------------------------------------------------
        # BASIC VIDEO FIELDS
        # ----------------------------------------------------

        video.video_name = video_name

        video.video_description = (
            video_description
        )

        video.status = status

        # ----------------------------------------------------
        # OPTIONAL VIDEO FILE REPLACEMENT
        # ----------------------------------------------------

        if new_video_file:

            video.video_file = new_video_file

        # ----------------------------------------------------
        # UPDATED BY ADMIN / TEACHER
        # ----------------------------------------------------

        video.updated_by_admin = (
            actor["admin"]
            if actor["role"] == "admin"
            else None
        )

        video.updated_by_teacher = (
            actor["teacher"]
            if actor["role"] == "teacher"
            else None
        )

        # ----------------------------------------------------
        # SAVE VIDEO
        # ----------------------------------------------------

        video.save()

        # ----------------------------------------------------
        # FIELD CHANGE TIMELINE
        # ----------------------------------------------------

        for (
            field_name,
            old_value,
            new_value,
        ) in changes:

            record_video_updated(
                video=video,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

        # ----------------------------------------------------
        # VIDEO FILE CHANGE TIMELINE
        # ----------------------------------------------------

        if new_video_file:

            new_video_public_id = (
                _get_cloudinary_public_id(
                    video.video_file,
                )
            )

            record_video_updated(
                video=video,
                field_name="video_file",
                old_value=old_video_public_id,
                new_value=new_video_public_id,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

            # ------------------------------------------------
            # DELETE OLD CLOUDINARY VIDEO
            # ONLY AFTER DB COMMIT
            # ------------------------------------------------

            _schedule_cloudinary_cleanup(
                [
                    (
                        old_video_public_id,
                        "video",
                    )
                ]
            )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    messages.success(
        request,
        "Video updated successfully.",
    )

    # --------------------------------------------------------
    # PRG REDIRECT
    # --------------------------------------------------------

    return _builder_redirect(
        batch,
        subject,
    )
    
# ===========================================================
# PDF CREATE
# ============================================================


@require_POST
def create_pdf_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    """
    Admin + assigned Teacher can create PDFs.

    PDF itself is stored through Cloudinary raw storage.
    """

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )


    if actor is None:

        messages.error(
            request,
            "You do not have permission to create a PDF.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    fullname = _get_actor_name(actor)
    actor_role = _get_actor_role(actor)

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    pdf_name = (
        request.POST.get(
            "pdf_name",
            "",
        )
        .strip()
    )

    pdf_description = (
        request.POST.get(
            "pdf_description",
            "",
        )
        .strip()
    )

    status = (
        request.POST.get(
            "status",
            "",
        )
        .strip()
        .lower()
    )

    pdf_file = request.FILES.get(
        "pdf_file"
    )

    pdf_thumbnail = request.FILES.get(
        "pdf_thumbnail"
    )

    errors = {}

    if not pdf_name:
        errors["pdf_name"] = (
            "Please enter the PDF name."
        )

    elif len(pdf_name) > 100:
        errors["pdf_name"] = (
            "PDF name cannot exceed 100 characters."
        )

    if not pdf_description:
        errors["pdf_description"] = (
            "Please enter the PDF description."
        )

    elif len(pdf_description) > 250:
        errors["pdf_description"] = (
            "PDF description cannot exceed 250 characters."
        )

    if not pdf_file:
        errors["pdf_file"] = (
            "Please select a PDF file."
        )
    else:

        error = _validate_pdf_file(
            pdf_file
        )

        if error:
            errors["pdf_file"] = error

    if pdf_thumbnail:

        error = _validate_image_file(
            pdf_thumbnail
        )

        if error:
            errors["pdf_thumbnail"] = error

    if status not in VALID_STATUS:
        errors["status"] = (
            "Please select a valid PDF status."
        )

    duplicate = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            pdf_name__iexact=pdf_name,
        )
        .exists()
    )

    if duplicate:
        errors["pdf_name"] = (
            "A PDF with this name already exists."
        )

    if errors:
        return _render_builder_form_error(
            request=request,
            batch=batch,
            subject=subject,
            actor=actor,
            selected_chapter=chapter,
            errors=errors,
            form_data={
                "pdf_name": pdf_name,
                "pdf_description": pdf_description,
                "status": status,
            },
            form_error_key="pdf_form_errors",
            form_data_key="pdf_form_data",
            open_key="pdf_create_open",
            selected_content="pdfs",
        )
    with transaction.atomic():

        queryset = ChapterPDF.objects.filter(
            chapter=chapter,
        )

        pdf_order = get_next_order(
            queryset,
            "pdf_order",
        )

        pdf = ChapterPDF.objects.create(
            chapter=chapter,
            pdf_name=pdf_name,
            pdf_description=pdf_description,
            pdf_file=pdf_file,
            pdf_thumbnail=(
                pdf_thumbnail
                if pdf_thumbnail
                else DEFAULT_PDF_THUMBNAIL
            ),
            pdf_order=pdf_order,
            status=status,
            **_get_creator_fields(actor),
        )

        record_pdf_created(
            pdf=pdf,
            admin=(
                actor["admin"]
                if actor["role"] == "admin"
                else None
            ),
            teacher=(
                actor["teacher"]
                if actor["role"] == "teacher"
                else None
            ),
        )

    messages.success(
        request,
        "PDF created successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
    )


# ============================================================
# PDF EDIT
# ============================================================


@require_POST
def edit_pdf_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    pdf_id,
):
    """
    Admin + assigned Teacher can edit PDF.

    Existing Cloudinary PDF remains when no replacement
    is uploaded.
    """

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )


    if actor is None:

        messages.error(
            request,
            "You do not have permission to edit this PDF.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    fullname = _get_actor_name(actor)
    actor_role = _get_actor_role(actor)

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    pdf = get_object_or_404(
        ChapterPDF,
        id=pdf_id,
        chapter=chapter,
    )

    pdf_name = (
        request.POST.get(
            "pdf_name",
            "",
        )
        .strip()
    )

    pdf_description = (
        request.POST.get(
            "pdf_description",
            "",
        )
        .strip()
    )

    status = (
        request.POST.get(
            "status",
            "",
        )
        .strip()
        .lower()
    )

    raw_order = (
        request.POST.get(
            "pdf_order",
            "",
        )
        .strip()
    )

    new_pdf_file = request.FILES.get(
        "pdf_file"
    )

    new_thumbnail = request.FILES.get(
        "pdf_thumbnail"
    )

    errors = {}

    if not pdf_name:
        errors["pdf_name"] = (
            "Please enter the PDF name."
        )

    elif len(pdf_name) > 100:
        errors["pdf_name"] = (
            "PDF name cannot exceed 100 characters."
        )

    if not pdf_description:
        errors["pdf_description"] = (
            "Please enter the PDF description."
        )

    elif len(pdf_description) > 250:
        errors["pdf_description"] = (
            "PDF description cannot exceed 250 characters."
        )

    if status not in VALID_STATUS:
        errors["status"] = (
            "Please select a valid PDF status."
        )

    try:
        new_order = int(raw_order)

        if new_order < 1:
            raise ValueError

    except (
        ValueError,
        TypeError,
    ):
        errors["pdf_order"] = (
            "PDF order must be a valid number."
        )
        new_order = None

    duplicate = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            pdf_name__iexact=pdf_name,
        )
        .exclude(
            pk=pdf.pk,
        )
        .exists()
    )

    if duplicate:
        errors["pdf_name"] = (
            "A PDF with this name already exists."
        )

    if new_pdf_file:

        error = _validate_pdf_file(
            new_pdf_file
        )

        if error:
            errors["pdf_file"] = error

    if new_thumbnail:

        error = _validate_image_file(
            new_thumbnail
        )

        if error:
            errors["pdf_thumbnail"] = error

    if errors:
        return _render_builder_form_error(
            request=request,
            batch=batch,
            subject=subject,
            actor=actor,
            selected_chapter=chapter,
            errors=errors,
            form_data={
                "pdf_name": pdf_name,
                "pdf_description": pdf_description,
                "pdf_order": raw_order,
                "status": status,
            },
            form_error_key="pdf_edit_form_errors",
            form_data_key="pdf_edit_form_data",
            open_key="pdf_edit_open",
            selected_content="pdfs",
            open_id=pdf.id,
        )
    changes = []

    if pdf.pdf_name != pdf_name:
        changes.append(
            (
                "pdf_name",
                pdf.pdf_name,
                pdf_name,
            )
        )

    if (
        pdf.pdf_description
        != pdf_description
    ):
        changes.append(
            (
                "pdf_description",
                pdf.pdf_description,
                pdf_description,
            )
        )

    if pdf.status != status:
        changes.append(
            (
                "status",
                pdf.status,
                status,
            )
        )

    old_order = pdf.pdf_order

    old_pdf_file = pdf.pdf_file
    old_thumbnail = pdf.pdf_thumbnail

    if new_pdf_file:
        changes.append(
            (
                "pdf_file",
                _get_cloudinary_public_id(old_pdf_file),
                getattr(new_pdf_file, "name", str(new_pdf_file)),
            )
        )

    if new_thumbnail:
        changes.append(
            (
                "pdf_thumbnail",
                _get_cloudinary_public_id(old_thumbnail),
                getattr(new_thumbnail, "name", str(new_thumbnail)),
            )
        )

    with transaction.atomic():

        if old_order != new_order:

            move_item(
                item=pdf,
                queryset=ChapterPDF.objects.filter(
                    chapter=chapter,
                ),
                order_field="pdf_order",
                new_order=new_order,
            )

            record_pdf_order_changed(
                pdf=pdf,
                old_order=old_order,
                new_order=new_order,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

        pdf.pdf_name = pdf_name
        pdf.pdf_description = pdf_description
        pdf.status = status

        if new_pdf_file:
            pdf.pdf_file = new_pdf_file

        if new_thumbnail:
            pdf.pdf_thumbnail = new_thumbnail

        if changes or old_order != new_order:
            updater_fields = _get_updater_fields(actor)
            pdf.updated_by_admin = updater_fields["updated_by_admin"]
            pdf.updated_by_teacher = updater_fields["updated_by_teacher"]
            pdf.save()

        for (
            field_name,
            old_value,
            new_value,
        ) in changes:

            record_pdf_updated(
                pdf=pdf,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

        cleanup_assets = []

        if new_pdf_file:

            cleanup_assets.append(
                (
                    _get_cloudinary_public_id(
                        old_pdf_file
                    ),
                    "raw",
                )
            )

        if new_thumbnail:

            cleanup_assets.append(
                (
                    _get_cloudinary_public_id(
                        old_thumbnail
                    ),
                    "image",
                )
            )

        if cleanup_assets:
            _schedule_cloudinary_cleanup(
                cleanup_assets
            )

    messages.success(
        request,
        "PDF updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
    )


# ============================================================
# QUIZ CREATE
# ============================================================


@require_POST
def create_quiz_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    """
    Admin + assigned Teacher can create quizzes.
    """

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )


    if actor is None:

        messages.error(
            request,
            "You do not have permission to create a quiz.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    fullname = _get_actor_name(actor)
    actor_role = _get_actor_role(actor)

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    quiz_name = (
        request.POST.get(
            "quiz_name",
            "",
        )
        .strip()
    )

    quiz_description = (
        request.POST.get(
            "quiz_description",
            "",
        )
        .strip()
    )

    raw_attempts = (
        request.POST.get(
            "maximum_attempts",
            "",
        )
        .strip()
    )

    status = (
        request.POST.get(
            "status",
            "",
        )
        .strip()
        .lower()
    )

    errors = {}

    if not quiz_name:
        errors["quiz_name"] = (
            "Please enter the quiz name."
        )

    elif len(quiz_name) > 100:
        errors["quiz_name"] = (
            "Quiz name cannot exceed 100 characters."
        )

    if not quiz_description:
        errors["quiz_description"] = (
            "Please enter the quiz description."
        )

    elif len(quiz_description) > 250:
        errors["quiz_description"] = (
            "Quiz description cannot exceed 250 characters."
        )

    try:

        maximum_attempts = int(
            raw_attempts
        )

        if maximum_attempts < 1:
            raise ValueError

    except (
        ValueError,
        TypeError,
    ):

        maximum_attempts = None

        errors["maximum_attempts"] = (
            "Maximum attempts must be at least 1."
        )

    if status not in VALID_STATUS:
        errors["status"] = (
            "Please select a valid quiz status."
        )

    duplicate = (
        ChapterQuiz.objects
        .filter(
            chapter=chapter,
            quiz_name__iexact=quiz_name,
        )
        .exists()
    )

    if duplicate:
        errors["quiz_name"] = (
            "A quiz with this name already exists."
        )

    if errors:
        return _render_builder_form_error(
            request=request,
            batch=batch,
            subject=subject,
            actor=actor,
            selected_chapter=chapter,
            errors=errors,
            form_data={
                "quiz_name": quiz_name,
                "quiz_description": quiz_description,
                "maximum_attempts": raw_attempts,
                "status": status,
            },
            form_error_key="quiz_form_errors",
            form_data_key="quiz_form_data",
            open_key="quiz_create_open",
            selected_content="quizzes",
        )
    with transaction.atomic():

        queryset = ChapterQuiz.objects.filter(
            chapter=chapter,
        )

        quiz_order = get_next_order(
            queryset,
            "quiz_order",
        )

        quiz = ChapterQuiz.objects.create(
            chapter=chapter,
            quiz_name=quiz_name,
            quiz_description=quiz_description,
            quiz_order=quiz_order,
            maximum_attempts=maximum_attempts,
            status=status,
            **_get_creator_fields(actor),
        )

        record_quiz_created(
            quiz=quiz,
            admin=(
                actor["admin"]
                if actor["role"] == "admin"
                else None
            ),
            teacher=(
                actor["teacher"]
                if actor["role"] == "teacher"
                else None
            ),
        )

    messages.success(
        request,
        "Quiz created successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
    )


# ============================================================
# QUIZ EDIT
# ============================================================


@require_POST
def edit_quiz_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    quiz_id,
):
    """
    Admin + assigned Teacher can edit quiz.
    """

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    actor = _authorize_builder(
        request,
        batch,
        subject,
    )


    if actor is None:

        messages.error(
            request,
            "You do not have permission to edit this quiz.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    fullname = _get_actor_name(actor)
    actor_role = _get_actor_role(actor)

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    quiz = get_object_or_404(
        ChapterQuiz,
        id=quiz_id,
        chapter=chapter,
    )

    quiz_name = (
        request.POST.get(
            "quiz_name",
            "",
        )
        .strip()
    )

    quiz_description = (
        request.POST.get(
            "quiz_description",
            "",
        )
        .strip()
    )

    raw_attempts = (
        request.POST.get(
            "maximum_attempts",
            "",
        )
        .strip()
    )

    status = (
        request.POST.get(
            "status",
            "",
        )
        .strip()
        .lower()
    )

    raw_order = (
        request.POST.get(
            "quiz_order",
            "",
        )
        .strip()
    )

    errors = {}

    if not quiz_name:
        errors["quiz_name"] = (
            "Please enter the quiz name."
        )

    elif len(quiz_name) > 100:
        errors["quiz_name"] = (
            "Quiz name cannot exceed 100 characters."
        )

    if not quiz_description:
        errors["quiz_description"] = (
            "Please enter the quiz description."
        )

    elif len(quiz_description) > 250:
        errors["quiz_description"] = (
            "Quiz description cannot exceed 250 characters."
        )

    try:

        maximum_attempts = int(
            raw_attempts
        )

        if maximum_attempts < 1:
            raise ValueError

    except (
        ValueError,
        TypeError,
    ):

        maximum_attempts = None

        errors["maximum_attempts"] = (
            "Maximum attempts must be at least 1."
        )

    if status not in VALID_STATUS:
        errors["status"] = (
            "Please select a valid quiz status."
        )

    try:

        new_order = int(
            raw_order
        )

        if new_order < 1:
            raise ValueError

    except (
        ValueError,
        TypeError,
    ):

        new_order = None

        errors["quiz_order"] = (
            "Quiz order must be a valid number."
        )

    duplicate = (
        ChapterQuiz.objects
        .filter(
            chapter=chapter,
            quiz_name__iexact=quiz_name,
        )
        .exclude(
            pk=quiz.pk,
        )
        .exists()
    )

    if duplicate:
        errors["quiz_name"] = (
            "A quiz with this name already exists."
        )

    if errors:
        return _render_builder_form_error(
            request=request,
            batch=batch,
            subject=subject,
            actor=actor,
            selected_chapter=chapter,
            errors=errors,
            form_data={
                "quiz_name": quiz_name,
                "quiz_description": quiz_description,
                "maximum_attempts": raw_attempts,
                "quiz_order": raw_order,
                "status": status,
            },
            form_error_key="quiz_edit_form_errors",
            form_data_key="quiz_edit_form_data",
            open_key="quiz_edit_open",
            selected_content="quizzes",
            open_id=quiz.id,
        )
    changes = []

    if quiz.quiz_name != quiz_name:
        changes.append(
            (
                "quiz_name",
                quiz.quiz_name,
                quiz_name,
            )
        )

    if (
        quiz.quiz_description
        != quiz_description
    ):
        changes.append(
            (
                "quiz_description",
                quiz.quiz_description,
                quiz_description,
            )
        )

    if (
        quiz.maximum_attempts
        != maximum_attempts
    ):
        changes.append(
            (
                "maximum_attempts",
                quiz.maximum_attempts,
                maximum_attempts,
            )
        )

    if quiz.status != status:
        changes.append(
            (
                "status",
                quiz.status,
                status,
            )
        )

    old_order = quiz.quiz_order

    with transaction.atomic():

        if old_order != new_order:

            move_item(
                item=quiz,
                queryset=ChapterQuiz.objects.filter(
                    chapter=chapter,
                ),
                order_field="quiz_order",
                new_order=new_order,
            )

            record_quiz_order_changed(
                quiz=quiz,
                old_order=old_order,
                new_order=new_order,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

        quiz.quiz_name = quiz_name
        quiz.quiz_description = (
            quiz_description
        )
        quiz.maximum_attempts = (
            maximum_attempts
        )
        quiz.status = status

        if changes or old_order != new_order:
            updater_fields = _get_updater_fields(actor)
            quiz.updated_by_admin = updater_fields["updated_by_admin"]
            quiz.updated_by_teacher = updater_fields["updated_by_teacher"]
            quiz.save()

        for (
            field_name,
            old_value,
            new_value,
        ) in changes:

            record_quiz_updated(
                quiz=quiz,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                admin=(
                    actor["admin"]
                    if actor["role"] == "admin"
                    else None
                ),
                teacher=(
                    actor["teacher"]
                    if actor["role"] == "teacher"
                    else None
                ),
            )

    messages.success(
        request,
        "Quiz updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
    )


# ============================================================
# DELETION AUDIT SNAPSHOT
# ============================================================


def _get_original_creator(obj):
    """
    Capture original creator.
    """

    if getattr(
        obj,
        "created_by_admin_id",
        None,
    ):

        return {
            "admin": obj.created_by_admin,
            "teacher": None,
        }

    if getattr(
        obj,
        "created_by_teacher_id",
        None,
    ):

        return {
            "admin": None,
            "teacher": obj.created_by_teacher,
        }

    return {
        "admin": None,
        "teacher": None,
    }


def _build_deletion_snapshot(
    content_type,
    obj,
):
    """
    Permanent audit snapshot.

    This is metadata about what was deleted.
    It does not try to store the actual Cloudinary file.
    """

    if content_type == "chapter":
        chapter = obj
    else:
        chapter = obj.chapter

    content_name = ""

    if content_type == "chapter":
        content_name = obj.chapter_name

    elif content_type == "video":
        content_name = obj.video_name

    elif content_type == "pdf":
        content_name = obj.pdf_name

    elif content_type == "quiz":
        content_name = obj.quiz_name

    snapshot = {
        "content_type": content_type,
        "object_id": obj.pk,
        "content_name": content_name,

        "batch_name": (
            chapter.batch.batch_name
        ),

        "subject_name": (
            chapter.subject.subject_name
        ),

        "chapter_name": (
            chapter.chapter_name
        ),
    }

    if content_type == "chapter":

        snapshot.update(
            {
                "chapter_description": (
                    obj.chapter_description
                ),
                "chapter_order": (
                    obj.chapter_order
                ),
                "status": obj.status,
            }
        )

    elif content_type == "video":

        snapshot.update(
            {
                "video_description": (
                    obj.video_description
                ),
                "video_order": (
                    obj.video_order
                ),
                "status": obj.status,
                "video_file": (
                    _get_cloudinary_public_id(
                        obj.video_file
                    )
                ),
            }
        )

    elif content_type == "pdf":

        snapshot.update(
            {
                "pdf_description": (
                    obj.pdf_description
                ),
                "pdf_order": (
                    obj.pdf_order
                ),
                "status": obj.status,
                "pdf_file": (
                    _get_cloudinary_public_id(
                        obj.pdf_file
                    )
                ),
                "pdf_thumbnail": (
                    _get_cloudinary_public_id(
                        obj.pdf_thumbnail
                    )
                ),
            }
        )

    elif content_type == "quiz":

        snapshot.update(
            {
                "quiz_description": (
                    obj.quiz_description
                ),
                "quiz_order": (
                    obj.quiz_order
                ),
                "maximum_attempts": (
                    obj.maximum_attempts
                ),
                "status": obj.status,
            }
        )

    return snapshot


def _create_deletion_audit(
    content_type,
    obj,
    status,
    actor,
    request_reason="",
    admin_response="",
    deletion_method="",
):
    """
    Create one permanent deletion audit record.
    """

    creator = _get_original_creator(
        obj
    )

    chapter = (
        obj
        if content_type == "chapter"
        else obj.chapter
    )

    content_name = ""

    if content_type == "chapter":
        content_name = obj.chapter_name

    elif content_type == "video":
        content_name = obj.video_name

    elif content_type == "pdf":
        content_name = obj.pdf_name

    elif content_type == "quiz":
        content_name = obj.quiz_name

    return DeletionAudit.objects.create(
        content_type=content_type,
        object_id=obj.pk,

        content_name=content_name,

        batch_name=(
            chapter.batch.batch_name
        ),

        subject_name=(
            chapter.subject.subject_name
        ),

        chapter_name=(
            chapter.chapter_name
        ),

        created_by_admin=(
            creator["admin"]
        ),

        created_by_teacher=(
            creator["teacher"]
        ),

        original_created_at=(
            obj.created_at
        ),

        requested_by_teacher=(
            actor["teacher"]
            if actor["role"] == "teacher"
            else None
        ),

        requested_at=(
            timezone.now()
            if actor["role"] == "teacher"
            else None
        ),

        request_reason=request_reason,

        deleted_by_admin=(
            actor["admin"]
            if (
                actor["role"] == "admin"
                and status == "deleted"
            )
            else None
        ),

        admin_delete_reason=(
            request_reason
            if (
                actor["role"] == "admin"
                and status == "deleted"
            )
            else ""
        ),

        deletion_method=deletion_method,

        status=status,

        admin_response=admin_response,

        snapshot=_build_deletion_snapshot(
            content_type,
            obj,
        ),
    )


# ============================================================
# TEACHER DELETE REQUEST
# ============================================================


@require_POST
def teacher_request_delete_view(
    request,
    batch_id,
    subject_id,
    content_type,
    object_id,
):
    """
    SENSITIVE OPERATION.

    Teacher CANNOT delete.

    Teacher can ONLY create a pending DeletionAudit.

    Actual deletion can happen only after Admin approval.
    """

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    actor = _authorize_teacher(
        request,
        batch,
        subject,
    )

    if actor is None:

        messages.error(
            request,
            "Only the assigned Teacher can request deletion.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    if content_type not in VALID_CONTENT_TYPES:

        messages.error(
            request,
            "Invalid content type.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    reason = (
        request.POST.get(
            "reason",
            "",
        )
        .strip()
    )

    if not reason:

        messages.error(
            request,
            "Please enter a deletion reason.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    chapter_id = (
        request.POST.get(
            "chapter_id"
        )
    )

    obj = _get_content_object(
        batch=batch,
        subject=subject,
        content_type=content_type,
        object_id=object_id,
        chapter_id=chapter_id,
    )

    if obj is None:

        messages.error(
            request,
            "Invalid content.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    # --------------------------------------------------------
    # PREVENT DUPLICATE PENDING REQUEST
    # --------------------------------------------------------

    pending_exists = (
        DeletionAudit.objects
        .filter(
            content_type=content_type,
            object_id=obj.pk,
            status="pending",
        )
        .exists()
    )

    if pending_exists:

        messages.error(
            request,
            "A deletion request is already pending for this content.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    # --------------------------------------------------------
    # CREATE AUDIT ONLY
    # --------------------------------------------------------

    with transaction.atomic():

        _create_deletion_audit(
            content_type=content_type,
            obj=obj,
            status="pending",
            actor=actor,
            request_reason=reason,
            deletion_method="",
        )

    messages.success(
        request,
        "Deletion request submitted to Admin successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
    )


# ============================================================
# ADMIN DIRECT DELETE
# ============================================================


@require_POST
def admin_direct_delete_view(
    request,
    batch_id,
    subject_id,
    content_type,
    object_id,
):
    """
    SENSITIVE ADMIN-ONLY OPERATION.

    Teacher cannot access this successfully even if they
    manually construct the URL.

    Admin:
        audit -> capture assets -> delete DB -> Cloudinary
        cleanup after successful transaction.
    """

    batch, subject = _get_batch_subject(
        batch_id,
        subject_id,
    )

    actor = _authorize_admin(
        request
    )

    if actor is None:

        messages.error(
            request,
            "Only Admin can directly delete course content.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    if content_type not in VALID_CONTENT_TYPES:

        messages.error(
            request,
            "Invalid content type.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    reason = (
        request.POST.get(
            "reason",
            "",
        )
        .strip()
    )

    if not reason:

        messages.error(
            request,
            "Please enter a deletion reason.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    chapter_id = (
        request.POST.get(
            "chapter_id"
        )
    )

    obj = _get_content_object(
        batch=batch,
        subject=subject,
        content_type=content_type,
        object_id=object_id,
        chapter_id=chapter_id,
    )

    if obj is None:

        messages.error(
            request,
            "Invalid content.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

    # --------------------------------------------------------
    # CAPTURE CLOUDINARY ASSETS BEFORE DELETE
    # --------------------------------------------------------

    if content_type == "chapter":

        cleanup_assets = (
            _capture_chapter_assets(
                obj
            )
        )

    elif content_type == "video":

        cleanup_assets = (
            _capture_video_assets(
                obj
            )
        )

    elif content_type == "pdf":

        cleanup_assets = (
            _capture_pdf_assets(
                obj
            )
        )

    else:

        cleanup_assets = []

    # --------------------------------------------------------
    # AUDIT + ORDER + DELETE
    # --------------------------------------------------------

    with transaction.atomic():

        _create_deletion_audit(
            content_type=content_type,
            obj=obj,
            status="deleted",
            actor=actor,
            request_reason=reason,
            deletion_method="admin_direct",
        )

        if content_type == "chapter":

            remove_item_and_close_gap(
                item=obj,
                queryset=CourseChapter.objects.filter(
                    batch=batch,
                    subject=subject,
                ),
                order_field="chapter_order",
            )

        elif content_type == "video":

            remove_item_and_close_gap(
                item=obj,
                queryset=ChapterVideo.objects.filter(
                    chapter=obj.chapter,
                ),
                order_field="video_order",
            )

        elif content_type == "pdf":

            remove_item_and_close_gap(
                item=obj,
                queryset=ChapterPDF.objects.filter(
                    chapter=obj.chapter,
                ),
                order_field="pdf_order",
            )

        elif content_type == "quiz":

            remove_item_and_close_gap(
                item=obj,
                queryset=ChapterQuiz.objects.filter(
                    chapter=obj.chapter,
                ),
                order_field="quiz_order",
            )

        obj.delete()

        if cleanup_assets:
            _schedule_cloudinary_cleanup(
                cleanup_assets
            )

    messages.success(
        request,
        "Content deleted successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
    )


# ============================================================
# ADMIN DELETION AUDIT LIST
# ============================================================


def admin_deletion_audit_list_view(
    request,
):
    """
    Admin-only read-only deletion audit list.
    """

    actor = _authorize_admin(
        request
    )

    if actor is None:

        messages.error(
            request,
            "Only Admin can view deletion audits.",
        )

        return redirect(
            "teacher_login"
        )

    audits = (
        DeletionAudit.objects
        .select_related(
            "created_by_admin",
            "created_by_teacher",
            "requested_by_teacher",
            "decision_by_admin",
            "deleted_by_admin",
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )

    return render(
        request,
        "courses/admin_deletion_audit_list.html",
        {
            "audits": audits,
            "actor": actor,
        },
    )


# ============================================================
# ADMIN DELETION AUDIT DETAIL
# ============================================================


def admin_deletion_audit_detail_view(
    request,
    audit_id,
):
    """
    Admin-only deletion audit detail.
    """

    actor = _authorize_admin(
        request
    )

    if actor is None:

        messages.error(
            request,
            "Only Admin can view deletion audits.",
        )

        return redirect(
            "teacher_login"
        )

    audit = get_object_or_404(
        DeletionAudit,
        id=audit_id,
    )

    return render(
        request,
        "courses/admin_deletion_audit_detail.html",
        {
            "audit": audit,
            "actor": actor,
        },
    )


# ============================================================
# ADMIN APPROVE TEACHER DELETE REQUEST
# ============================================================


@require_POST
def admin_approve_delete_view(
    request,
    audit_id,
):
    """
    SENSITIVE ADMIN-ONLY OPERATION.

    Flow:

        Teacher request
              ↓
        DeletionAudit pending
              ↓
        Admin approves
              ↓
        actual content delete
              ↓
        Cloudinary cleanup
              ↓
        audit becomes deleted
    """

    actor = _authorize_admin(
        request
    )

    if actor is None:

        messages.error(
            request,
            "Only Admin can approve deletion requests.",
        )

        return redirect(
            "teacher_login"
        )

    audit = get_object_or_404(
        DeletionAudit,
        id=audit_id,
        status="pending",
    )

    admin_response = (
        request.POST.get(
            "admin_response",
            "",
        )
        .strip()
    )

    if not admin_response:

        messages.error(
            request,
            "Please enter an Admin response before approving.",
        )

        return redirect(
            "courses:admin_deletion_audit_detail",
            audit_id=audit.id,
        )

    content_type = audit.content_type

    obj = None

    # --------------------------------------------------------
    # FIND CURRENT CONTENT
    # --------------------------------------------------------

    if content_type == "chapter":

        obj = (
            CourseChapter.objects
            .filter(
                id=audit.object_id,
            )
            .first()
        )

    elif content_type == "video":

        obj = (
            ChapterVideo.objects
            .filter(
                id=audit.object_id,
            )
            .select_related(
                "chapter",
            )
            .first()
        )

    elif content_type == "pdf":

        obj = (
            ChapterPDF.objects
            .filter(
                id=audit.object_id,
            )
            .select_related(
                "chapter",
            )
            .first()
        )

    elif content_type == "quiz":

        obj = (
            ChapterQuiz.objects
            .filter(
                id=audit.object_id,
            )
            .select_related(
                "chapter",
            )
            .first()
        )

    if obj is None:

        messages.error(
            request,
            "The requested content no longer exists.",
        )

        return redirect(
            "courses:admin_deletion_audit_detail",
            audit_id=audit.id,
        )

    # --------------------------------------------------------
    # CAPTURE CLOUDINARY ASSETS
    # --------------------------------------------------------

    if content_type == "chapter":

        cleanup_assets = (
            _capture_chapter_assets(
                obj
            )
        )

    elif content_type == "video":

        cleanup_assets = (
            _capture_video_assets(
                obj
            )
        )

    elif content_type == "pdf":

        cleanup_assets = (
            _capture_pdf_assets(
                obj
            )
        )

    else:

        cleanup_assets = []

    # --------------------------------------------------------
    # APPROVE + DELETE
    # --------------------------------------------------------

    with transaction.atomic():

        audit.admin_decision = (
            "approved"
        )

        audit.decision_by_admin = (
            actor["admin"]
        )

        audit.decision_at = (
            timezone.now()
        )

        audit.admin_response = (
            admin_response
        )

        audit.status = "approved"

        audit.save(
            update_fields=[
                "admin_decision",
                "decision_by_admin",
                "decision_at",
                "admin_response",
                "status",
            ]
        )

        if content_type == "chapter":

            remove_item_and_close_gap(
                item=obj,
                queryset=CourseChapter.objects.filter(
                    batch=obj.batch,
                    subject=obj.subject,
                ),
                order_field="chapter_order",
            )

        elif content_type == "video":

            remove_item_and_close_gap(
                item=obj,
                queryset=ChapterVideo.objects.filter(
                    chapter=obj.chapter,
                ),
                order_field="video_order",
            )

        elif content_type == "pdf":

            remove_item_and_close_gap(
                item=obj,
                queryset=ChapterPDF.objects.filter(
                    chapter=obj.chapter,
                ),
                order_field="pdf_order",
            )

        elif content_type == "quiz":

            remove_item_and_close_gap(
                item=obj,
                queryset=ChapterQuiz.objects.filter(
                    chapter=obj.chapter,
                ),
                order_field="quiz_order",
            )

        obj.delete()

        audit.deletion_method = (
            "teacher_request_approved"
        )

        audit.status = "deleted"

        audit.deleted_at = (
            timezone.now()
        )

        audit.save(
            update_fields=[
                "deletion_method",
                "status",
                "deleted_at",
            ]
        )

        if cleanup_assets:
            _schedule_cloudinary_cleanup(
                cleanup_assets
            )

    messages.success(
        request,
        "Deletion request approved and content deleted successfully.",
    )

    return redirect(
        "courses:admin_deletion_audit_list"
    )


# ============================================================
# ADMIN REJECT TEACHER DELETE REQUEST
# ============================================================


@require_POST
def admin_reject_delete_view(
    request,
    audit_id,
):
    """
    Admin rejects a pending Teacher request.

    IMPORTANT:
    No content deletion happens here.
    """

    actor = _authorize_admin(
        request
    )

    if actor is None:

        messages.error(
            request,
            "Only Admin can reject deletion requests.",
        )

        return redirect(
            "teacher_login"
        )

    audit = get_object_or_404(
        DeletionAudit,
        id=audit_id,
        status="pending",
    )

    admin_response = (
        request.POST.get(
            "admin_response",
            "",
        )
        .strip()
    )

    if not admin_response:

        messages.error(
            request,
            "Please enter an Admin response before rejecting.",
        )

        return redirect(
            "courses:admin_deletion_audit_detail",
            audit_id=audit.id,
        )

    audit.admin_decision = (
        "rejected"
    )

    audit.decision_by_admin = (
        actor["admin"]
    )

    audit.decision_at = (
        timezone.now()
    )

    audit.admin_response = (
        admin_response
    )

    audit.status = "rejected"

    audit.save(
        update_fields=[
            "admin_decision",
            "decision_by_admin",
            "decision_at",
            "admin_response",
            "status",
        ]
    )

    messages.success(
        request,
        "Deletion request rejected successfully.",
    )

    return redirect(
        "courses:admin_deletion_audit_list"
    )