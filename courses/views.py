from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_control

from admins.models import (
    Batch,
    Subject,
    Teacher,
    TeacherBatch,
    TeacherSubject,
)

from .helpers import (
    get_active_items,
    get_next_order,
    move_item,
    remove_item_from_order,
)

from .models import (
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
# COMMON COURSE BUILDER HELPERS
# ============================================================


COURSE_BUILDER_VIEWS = {
    "videos",
    "pdfs",
    "quizzes",
    "live",
    "timeline",
    "video_timeline",
    "pdf_timeline",
    "quiz_timeline",
}


def _is_admin(request):
    """
    Admin access for the shared Course Builder.

    Superusers and staff users are treated as Admin users,
    matching the existing Admin area authorization.
    """
    return bool(
        request.user.is_authenticated
        and (
            request.user.is_staff
            or request.user.is_superuser
        )
    )


def _get_teacher(request):
    """
    Return the logged-in Teacher profile if available.
    """
    if not request.user.is_authenticated:
        return None

    try:
        return request.user.teacher_profile
    except Teacher.DoesNotExist:
        return None


def _is_teacher(request):
    return _get_teacher(request) is not None


def _get_teacher_assignment(
    request,
    batch,
    subject,
):
    """
    Verify that the logged-in Teacher is actually assigned to
    this exact Batch + Subject.

    This is intentionally server-side so a teacher cannot access
    another subject simply by changing URL IDs.
    """

    teacher = _get_teacher(request)

    if teacher is None:
        return None

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
    Common authorization for the shared Course Builder.

    Returns:

        {
            "allowed": True/False,
            "is_admin": True/False,
            "is_teacher": True/False,
            "teacher": Teacher/None,
            "assignment": TeacherSubject/None,
        }
    """

    is_admin = _is_admin(request)
    teacher = _get_teacher(request)
    is_teacher = teacher is not None

    if is_admin:
        return {
            "allowed": True,
            "is_admin": True,
            "is_teacher": is_teacher,
            "teacher": teacher,
            "assignment": None,
        }

    if is_teacher:
        assignment = _get_teacher_assignment(
            request,
            batch,
            subject,
        )

        if assignment is not None:
            return {
                "allowed": True,
                "is_admin": False,
                "is_teacher": True,
                "teacher": teacher,
                "assignment": assignment,
            }

    return {
        "allowed": False,
        "is_admin": False,
        "is_teacher": False,
        "teacher": None,
        "assignment": None,
    }


def _builder_url(
    batch_id,
    subject_id,
    *,
    chapter_id=None,
    view="videos",
    extra=None,
):
    """
    Build the shared Course Builder URL.

    Navigation remains Django URL based.
    JavaScript is not responsible for navigation.
    """

    url = reverse(
        "course_builder",
        kwargs={
            "batch_id": batch_id,
            "subject_id": subject_id,
        },
    )

    query = []

    if chapter_id is not None:
        query.append(
            f"chapter={chapter_id}"
        )

    if view:
        query.append(
            f"view={view}"
        )

    if extra:
        query.extend(extra)

    if query:
        return f"{url}?{'&'.join(query)}"

    return url


def _redirect_builder(
    batch,
    subject,
    *,
    chapter=None,
    view="videos",
    extra=None,
):
    return redirect(
        _builder_url(
            batch.id,
            subject.id,
            chapter_id=(
                chapter.id
                if chapter
                else None
            ),
            view=view,
            extra=extra,
        )
    )


def _actor_data(
    request,
    teacher=None,
):
    """
    Return the correct actor information for timeline records.
    """

    if teacher is not None:
        full_name = (
            teacher.full_name
            or teacher.user.get_username()
        ).strip()

        return {
            "teacher": teacher,
            "admin": None,
            "name": (
                full_name
                or "Teacher"
            ),
        }

    full_name = (
        request.user.get_full_name()
        or request.user.get_username()
    ).strip()

    return {
        "teacher": None,
        "admin": request.user,
        "name": (
            full_name
            or "Admin"
        ),
    }


def _timeline_entry(log):
    """
    Convert any Course Builder change log into a template-friendly
    dictionary.

    Works with both Teacher and Admin actors.
    """

    teacher = getattr(
        log,
        "changed_by",
        None,
    )

    admin = getattr(
        log,
        "changed_by_admin",
        None,
    )

    if teacher is not None:
        full_name = (
            getattr(
                teacher,
                "full_name",
                "",
            )
            or ""
        ).strip()

        actor_name = (
            full_name
            or "Teacher"
        )

    elif admin is not None:
        full_name = (
            admin.get_full_name()
            or admin.get_username()
        ).strip()

        actor_name = (
            full_name
            or "Admin"
        )

    else:
        full_name = ""
        actor_name = "System"

    return {
        "id": log.id,
        "actor_name": actor_name.split()[0],
        "actor_full_name": actor_name,
        "action": log.get_action_display(),
        "action_key": log.action,
        "field_name": log.field_name,
        "old_value": log.old_value,
        "new_value": log.new_value,
        "summary": log.change_summary,
        "changed_at": log.changed_at,
    }


# ============================================================
# OBJECT ACCESS HELPERS
# ============================================================


def _get_chapter(
    batch,
    subject,
    chapter_id,
):
    return get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=batch,
        subject=subject,
        is_deleted=False,
    )


def _get_video(
    chapter,
    video_id,
):
    return get_object_or_404(
        ChapterVideo,
        id=video_id,
        chapter=chapter,
        is_deleted=False,
    )


def _get_pdf(
    chapter,
    pdf_id,
):
    return get_object_or_404(
        ChapterPDF,
        id=pdf_id,
        chapter=chapter,
        is_deleted=False,
    )


def _get_quiz(
    chapter,
    quiz_id,
):
    return get_object_or_404(
        ChapterQuiz,
        id=quiz_id,
        chapter=chapter,
        is_deleted=False,
    )


# ============================================================
# FILE VALIDATION
# ============================================================


def _validate_mp4(video_file):
    if not video_file:
        return (
            False,
            "Please select a valid MP4 video file.",
        )

    if getattr(
        video_file,
        "size",
        0,
    ) <= 0:
        return (
            False,
            "The selected video file is empty.",
        )

    file_name = (
        getattr(
            video_file,
            "name",
            "",
        )
        or ""
    ).strip().lower()

    if not file_name.endswith(".mp4"):
        return (
            False,
            "Invalid video format. Only MP4 video files are allowed.",
        )

    content_type = (
        getattr(
            video_file,
            "content_type",
            "",
        )
        or ""
    ).strip().lower()

    rejected_types = {
        "text/plain",
        "text/html",
        "application/pdf",
        "application/zip",
        "application/x-zip-compressed",
        "image/jpeg",
        "image/png",
        "image/gif",
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
    }

    if content_type in rejected_types:
        return (
            False,
            "The selected file is not a valid MP4 video.",
        )

    return True, ""


def _validate_pdf(pdf_file):
    if not pdf_file:
        return (
            False,
            "Please select a PDF file.",
        )

    if getattr(
        pdf_file,
        "size",
        0,
    ) <= 0:
        return (
            False,
            "The selected PDF file is empty.",
        )

    file_name = (
        getattr(
            pdf_file,
            "name",
            "",
        )
        or ""
    ).strip().lower()

    if not file_name.endswith(".pdf"):
        return (
            False,
            "Invalid file format. Only PDF files are allowed.",
        )

    content_type = (
        getattr(
            pdf_file,
            "content_type",
            "",
        )
        or ""
    ).strip().lower()

    rejected_types = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "video/mp4",
        "audio/mpeg",
        "audio/wav",
        "application/zip",
        "application/x-zip-compressed",
        "text/plain",
        "text/html",
    }

    if content_type in rejected_types:
        return (
            False,
            "The selected file is not a valid PDF document.",
        )

    return True, ""


def _validate_thumbnail(thumbnail):
    if not thumbnail:
        return True, ""

    name = (
        getattr(
            thumbnail,
            "name",
            "",
        )
        or ""
    ).strip().lower()

    extension = ""

    if "." in name:
        extension = (
            "."
            + name.rsplit(
                ".",
                1,
            )[1]
        )

    allowed_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }

    if extension not in allowed_extensions:
        return (
            False,
            (
                "Invalid thumbnail format. Only PNG, JPG, "
                "JPEG, and WEBP images are allowed."
            ),
        )

    if getattr(
        thumbnail,
        "size",
        0,
    ) <= 0:
        return (
            False,
            "The selected thumbnail image is empty.",
        )

    content_type = (
        getattr(
            thumbnail,
            "content_type",
            "",
        )
        or ""
    ).strip().lower()

    allowed_types = {
        "image/png",
        "image/jpeg",
        "image/webp",
    }

    if (
        content_type
        and content_type not in allowed_types
    ):
        return (
            False,
            (
                "The selected thumbnail is not a valid image. "
                "Use PNG, JPG, JPEG, or WEBP."
            ),
        )

    return True, ""


# ============================================================
# COMMON COURSE BUILDER DISPLAY
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_builder_view(
    request,
    batch_id,
    subject_id,
):
    """
    ONE Course Builder for both Admin and Teacher.

    Admin:
        - may open any valid Batch + Subject
        - full management UI

    Teacher:
        - must have an active TeacherSubject assignment
        - only the exact assigned Batch + Subject is accessible
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

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to access this Course Builder.",
        )

        if _is_teacher(request):
            return redirect("teacher_login")

        return redirect("admin_dashboard")

    is_admin = auth["is_admin"]
    is_teacher = auth["is_teacher"]
    teacher = auth["teacher"]
    assignment = auth["assignment"]

    chapters = (
        CourseChapter.objects
        .filter(
            batch=batch,
            subject=subject,
            is_deleted=False,
        )
        .select_related(
            "created_by",
            "created_by_admin",
            "updated_by",
            "updated_by_admin",
        )
        .order_by(
            "chapter_order",
            "id",
        )
    )

    chapter_count = chapters.count()

    chapter_query = (
        request.GET.get(
            "chapter",
            "",
        )
        or ""
    ).strip()

    selected_chapter = None

    if chapter_query.isdigit():
        selected_chapter = (
            chapters
            .filter(
                id=int(chapter_query),
            )
            .first()
        )

    if (
        selected_chapter is None
        and chapter_count
    ):
        selected_chapter = chapters.first()

    requested_view = (
        request.GET.get(
            "view",
            "videos",
        )
        or "videos"
    ).strip().lower()

    if requested_view not in COURSE_BUILDER_VIEWS:
        requested_view = "videos"

    selected_content = requested_view

    # ------------------------------------------------------------
    # CONTENT
    # ------------------------------------------------------------

    if selected_chapter:

        videos = (
            ChapterVideo.objects
            .filter(
                chapter=selected_chapter,
                is_deleted=False,
            )
            .select_related(
                "created_by",
                "created_by_admin",
                "updated_by",
                "updated_by_admin",
            )
            .order_by(
                "video_order",
                "id",
            )
        )

        pdfs = (
            ChapterPDF.objects
            .filter(
                chapter=selected_chapter,
                is_deleted=False,
            )
            .select_related(
                "created_by",
                "created_by_admin",
                "updated_by",
                "updated_by_admin",
            )
            .order_by(
                "pdf_order",
                "id",
            )
        )

        quizzes = (
            ChapterQuiz.objects
            .filter(
                chapter=selected_chapter,
                is_deleted=False,
            )
            .select_related(
                "created_by",
                "created_by_admin",
                "updated_by",
                "updated_by_admin",
            )
            .prefetch_related(
                "questions__options",
            )
            .order_by("id")
        )

    else:
        videos = ChapterVideo.objects.none()
        pdfs = ChapterPDF.objects.none()
        quizzes = ChapterQuiz.objects.none()

    # ------------------------------------------------------------
    # SELECTED VIDEO
    # ------------------------------------------------------------

    selected_video = None
    video_timeline_entries = []

    video_id = (
        request.GET.get(
            "video",
            "",
        )
        or ""
    ).strip()

    if (
        selected_chapter
        and selected_content == "video_timeline"
        and video_id.isdigit()
    ):
        selected_video = (
            ChapterVideo.objects
            .filter(
                id=int(video_id),
                chapter=selected_chapter,
                is_deleted=False,
            )
            .select_related(
                "created_by",
                "created_by_admin",
                "updated_by",
                "updated_by_admin",
            )
            .first()
        )

        if selected_video:
            video_logs = (
                VideoChangeLog.objects
                .filter(
                    video=selected_video,
                )
                .select_related(
                    "changed_by",
                    "changed_by_admin",
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

            video_timeline_entries = [
                _timeline_entry(log)
                for log in video_logs
            ]

    # ------------------------------------------------------------
    # SELECTED PDF
    # ------------------------------------------------------------

    selected_pdf = None
    pdf_timeline_entries = []

    pdf_id = (
        request.GET.get(
            "pdf",
            "",
        )
        or ""
    ).strip()

    if (
        selected_chapter
        and selected_content == "pdf_timeline"
        and pdf_id.isdigit()
    ):
        selected_pdf = (
            ChapterPDF.objects
            .filter(
                id=int(pdf_id),
                chapter=selected_chapter,
                is_deleted=False,
            )
            .select_related(
                "created_by",
                "created_by_admin",
                "updated_by",
                "updated_by_admin",
            )
            .first()
        )

        if selected_pdf:
            pdf_logs = (
                PDFChangeLog.objects
                .filter(
                    pdf=selected_pdf,
                )
                .select_related(
                    "changed_by",
                    "changed_by_admin",
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

            pdf_timeline_entries = [
                _timeline_entry(log)
                for log in pdf_logs
            ]

    # ------------------------------------------------------------
    # SELECTED QUIZ
    # ------------------------------------------------------------

    selected_quiz = None
    quiz_timeline_entries = []

    quiz_id = (
        request.GET.get(
            "quiz",
            "",
        )
        or ""
    ).strip()

    if (
        selected_chapter
        and selected_content in {
            "quizzes",
            "quiz_timeline",
        }
        and quiz_id.isdigit()
    ):
        selected_quiz = (
            ChapterQuiz.objects
            .filter(
                id=int(quiz_id),
                chapter=selected_chapter,
                is_deleted=False,
            )
            .select_related(
                "created_by",
                "created_by_admin",
                "updated_by",
                "updated_by_admin",
            )
            .prefetch_related(
                "questions__options",
            )
            .first()
        )

        if (
            selected_quiz
            and selected_content == "quiz_timeline"
        ):
            quiz_logs = (
                QuizChangeLog.objects
                .filter(
                    quiz=selected_quiz,
                )
                .select_related(
                    "changed_by",
                    "changed_by_admin",
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

            quiz_timeline_entries = [
                _timeline_entry(log)
                for log in quiz_logs
            ]

    # ------------------------------------------------------------
    # CHAPTER TIMELINE
    # ------------------------------------------------------------

    timeline_entries = []

    if (
        selected_chapter
        and selected_content == "timeline"
    ):
        chapter_logs = (
            ChapterChangeLog.objects
            .filter(
                chapter=selected_chapter,
            )
            .select_related(
                "changed_by",
                "changed_by_admin",
            )
            .order_by(
                "-changed_at",
                "-id",
            )
        )

        timeline_entries = [
            _timeline_entry(log)
            for log in chapter_logs
        ]

    # ------------------------------------------------------------
    # ASSIGNED TEACHERS
    # ------------------------------------------------------------

    assigned_teachers = (
        TeacherSubject.objects
        .filter(
            batch=batch,
            subject=subject,
            is_active=True,
        )
        .select_related(
            "teacher",
        )
        .order_by(
            "teacher__full_name",
        )
    )

    # ------------------------------------------------------------
    # SESSION POPUP STATE
    # ------------------------------------------------------------

    session_keys = (
        "chapter_edit_open",
        "chapter_edit_error",
        "chapter_edit_form",

        "video_upload_open",
        "video_upload_error",
        "video_upload_form",

        "video_edit_open",
        "video_edit_error",
        "video_edit_form",

        "pdf_upload_open",
        "pdf_upload_error",
        "pdf_upload_form",

        "pdf_edit_open",
        "pdf_edit_error",
        "pdf_edit_form",

        "quiz_create_open",
        "quiz_create_error",
        "quiz_create_form",

        "quiz_question_open",
        "quiz_question_error",
        "quiz_question_form",
        "quiz_question_quiz_id",

        "quiz_edit_validation_errors",
    )

    popup_state = {}

    for key in session_keys:
        popup_state[key] = request.session.pop(
            key,
            False if key.endswith("_open")
            else {} if key.endswith("_form")
            else [] if key.endswith("_errors")
            else "",
        )

    request.session.modified = True

    # ------------------------------------------------------------
    # CHAPTER ACTOR INFORMATION
    # ------------------------------------------------------------

    chapter_creator_name = ""
    chapter_creator_first_name = "System"

    chapter_updater_name = ""
    chapter_updater_first_name = "System"

    if selected_chapter:

        if selected_chapter.created_by:
            chapter_creator_name = (
                selected_chapter.created_by.full_name
                or ""
            ).strip()

            if chapter_creator_name:
                chapter_creator_first_name = (
                    chapter_creator_name.split()[0]
                )

        elif selected_chapter.created_by_admin:
            chapter_creator_name = (
                selected_chapter.created_by_admin.get_full_name()
                or selected_chapter.created_by_admin.get_username()
            ).strip()

            if chapter_creator_name:
                chapter_creator_first_name = (
                    chapter_creator_name.split()[0]
                )

        if selected_chapter.updated_by:
            chapter_updater_name = (
                selected_chapter.updated_by.full_name
                or ""
            ).strip()

            if chapter_updater_name:
                chapter_updater_first_name = (
                    chapter_updater_name.split()[0]
                )

        elif selected_chapter.updated_by_admin:
            chapter_updater_name = (
                selected_chapter.updated_by_admin.get_full_name()
                or selected_chapter.updated_by_admin.get_username()
            ).strip()

            if chapter_updater_name:
                chapter_updater_first_name = (
                    chapter_updater_name.split()[0]
                )

    context = {
        "batch": batch,
        "subject": subject,

        "teacher": teacher,
        "assignment": assignment,

        "is_admin": is_admin,
        "is_teacher": is_teacher,

        "assigned_teachers": assigned_teachers,

        "chapters": chapters,
        "chapter_count": chapter_count,
        "selected_chapter": selected_chapter,

        "selected_content": selected_content,

        "videos": videos,
        "video_count": videos.count(),

        "pdfs": pdfs,
        "pdf_count": pdfs.count(),

        "quizzes": quizzes,
        "quiz_count": quizzes.count(),

        "selected_video": selected_video,
        "video_timeline_entries": video_timeline_entries,
        "video_timeline_count": len(
            video_timeline_entries
        ),

        "selected_pdf": selected_pdf,
        "pdf_timeline_entries": pdf_timeline_entries,
        "pdf_timeline_count": len(
            pdf_timeline_entries
        ),

        "selected_quiz": selected_quiz,
        "quiz_timeline_entries": quiz_timeline_entries,
        "quiz_timeline_count": len(
            quiz_timeline_entries
        ),

        "timeline_entries": timeline_entries,
        "timeline_count": len(
            timeline_entries
        ),

        "chapter_creator_name": chapter_creator_name,
        "chapter_creator_first_name": chapter_creator_first_name,
        "chapter_updater_name": chapter_updater_name,
        "chapter_updater_first_name": chapter_updater_first_name,

        "chapter_edit_open": popup_state[
            "chapter_edit_open"
        ],
        "chapter_edit_error": popup_state[
            "chapter_edit_error"
        ],
        "chapter_edit_form": popup_state[
            "chapter_edit_form"
        ],

        "video_upload_open": popup_state[
            "video_upload_open"
        ],
        "video_upload_error": popup_state[
            "video_upload_error"
        ],
        "video_upload_form": popup_state[
            "video_upload_form"
        ],

        "video_edit_open": popup_state[
            "video_edit_open"
        ],
        "video_edit_error": popup_state[
            "video_edit_error"
        ],
        "video_edit_form": popup_state[
            "video_edit_form"
        ],

        "pdf_upload_open": popup_state[
            "pdf_upload_open"
        ],
        "pdf_upload_error": popup_state[
            "pdf_upload_error"
        ],
        "pdf_upload_form": popup_state[
            "pdf_upload_form"
        ],

        "pdf_edit_open": popup_state[
            "pdf_edit_open"
        ],
        "pdf_edit_error": popup_state[
            "pdf_edit_error"
        ],
        "pdf_edit_form": popup_state[
            "pdf_edit_form"
        ],

        "quiz_create_open": popup_state[
            "quiz_create_open"
        ],
        "quiz_create_error": popup_state[
            "quiz_create_error"
        ],
        "quiz_create_form": popup_state[
            "quiz_create_form"
        ],

        "quiz_question_open": popup_state[
            "quiz_question_open"
        ],
        "quiz_question_error": popup_state[
            "quiz_question_error"
        ],
        "quiz_question_form": popup_state[
            "quiz_question_form"
        ],
        "quiz_question_quiz_id": popup_state[
            "quiz_question_quiz_id"
        ],

        "quiz_edit_validation_errors": popup_state[
            "quiz_edit_validation_errors"
        ],

        "quiz_mode": (
            request.GET.get(
                "quiz_mode",
                "",
            )
            or ""
        ).strip().lower(),
    }

    return render(
        request,
        "courses/course_builder.html",
        context,
    )


# ============================================================
# CREATE CHAPTER
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_create_chapter_view(
    request,
    batch_id,
    subject_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to create chapters.",
        )
        return redirect("teacher_login")

    if request.method != "POST":
        messages.error(
            request,
            "Invalid chapter creation request.",
        )

        return _redirect_builder(
            batch,
            subject,
        )

    teacher = auth["teacher"]
    is_admin = auth["is_admin"]

    chapter_name = (
        request.POST.get(
            "chapter_name",
            "",
        )
        or ""
    ).strip()

    chapter_description = (
        request.POST.get(
            "chapter_description",
            "",
        )
        or ""
    ).strip()

    status = (
        request.POST.get(
            "status",
            "draft",
        )
        or "draft"
    ).strip().lower()

    if not chapter_name:
        messages.error(
            request,
            "Chapter name is required.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

    if len(chapter_name) > 255:
        messages.error(
            request,
            "Chapter name cannot exceed 255 characters.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

    if not chapter_description:
        messages.error(
            request,
            "Chapter description is required.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

    if len(chapter_description) > 255:
        messages.error(
            request,
            "Chapter description cannot exceed 255 characters.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

    valid_statuses = {
        choice[0]
        for choice in CourseChapter.STATUS_CHOICES
    }

    if status not in valid_statuses:
        messages.error(
            request,
            "Invalid chapter status selected.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

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
        messages.error(
            request,
            "A chapter with this name already exists in this subject.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

    existing_chapters = CourseChapter.objects.filter(
        batch=batch,
        subject=subject,
        is_deleted=False,
    )

    with transaction.atomic():

        chapter_order = get_next_order(
            existing_chapters,
            order_field="chapter_order",
            deleted_field="is_deleted",
        )

        chapter = CourseChapter.objects.create(
            batch=batch,
            subject=subject,
            chapter_name=chapter_name,
            chapter_description=chapter_description,
            chapter_order=chapter_order,
            status=status,

            created_by=(
                None
                if is_admin
                else teacher
            ),

            created_by_admin=(
                request.user
                if is_admin
                else None
            ),

            updated_by=(
                None
                if is_admin
                else teacher
            ),

            updated_by_admin=(
                request.user
                if is_admin
                else None
            ),

            is_deleted=False,
        )

        actor = _actor_data(
            request,
            teacher=(
                None
                if is_admin
                else teacher
            ),
        )

        ChapterChangeLog.objects.create(
            chapter=chapter,
            changed_by=actor["teacher"],
            changed_by_admin=actor["admin"],
            action="created",
            field_name="chapter",
            old_value="",
            new_value=(
                f"Chapter Name: {chapter_name}; "
                f"Description: {chapter_description}; "
                f"Order: {chapter_order}; "
                f"Status: {status}"
            ),
            change_summary=(
                f"{actor['name']} created chapter "
                f"'{chapter_name}' at order "
                f"{chapter_order}."
            ),
        )

    messages.success(
        request,
        (
            f'Chapter "{chapter.chapter_name}" '
            f"created successfully as Chapter "
            f"{chapter.chapter_order}."
        ),
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
    )


# ============================================================
# EDIT CHAPTER
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_edit_chapter_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to edit chapters.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    if request.method == "GET":

        request.session["chapter_edit_open"] = True
        request.session["chapter_edit_error"] = ""

        request.session["chapter_edit_form"] = {
            "chapter_id": chapter.id,
            "chapter_name": chapter.chapter_name,
            "chapter_description": (
                chapter.chapter_description
                or ""
            ),
            "chapter_order": str(
                chapter.chapter_order
            ),
            "status": chapter.status,
        }

        request.session.modified = True

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
        )

    if request.method != "POST":

        messages.error(
            request,
            "Invalid chapter edit request.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
        )

    teacher = auth["teacher"]
    is_admin = auth["is_admin"]

    chapter_name = (
        request.POST.get(
            "chapter_name",
            "",
        )
        or ""
    ).strip()

    chapter_description = (
        request.POST.get(
            "chapter_description",
            "",
        )
        or ""
    ).strip()

    chapter_order_raw = (
        request.POST.get(
            "chapter_order",
            "",
        )
        or ""
    ).strip()

    status = (
        request.POST.get(
            "status",
            "",
        )
        or ""
    ).strip().lower()

    form_data = {
        "chapter_id": chapter.id,
        "chapter_name": chapter_name,
        "chapter_description": chapter_description,
        "chapter_order": chapter_order_raw,
        "status": status,
    }

    def validation_error(message):
        request.session[
            "chapter_edit_open"
        ] = True

        request.session[
            "chapter_edit_error"
        ] = message

        request.session[
            "chapter_edit_form"
        ] = form_data

        request.session.modified = True

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
        )

    if not chapter_name:
        return validation_error(
            "Chapter name is required."
        )

    if len(chapter_name) > 255:
        return validation_error(
            "Chapter name cannot exceed 255 characters."
        )

    if not chapter_description:
        return validation_error(
            "Chapter description is required."
        )

    if len(chapter_description) > 255:
        return validation_error(
            "Chapter description cannot exceed 255 characters."
        )

    duplicate = (
        CourseChapter.objects
        .filter(
            batch=batch,
            subject=subject,
            chapter_name__iexact=chapter_name,
            is_deleted=False,
        )
        .exclude(
            id=chapter.id,
        )
        .exists()
    )

    if duplicate:
        return validation_error(
            "Another chapter with this name already exists."
        )

    if not chapter_order_raw:
        return validation_error(
            "Chapter order is required."
        )

    try:
        new_order = int(
            chapter_order_raw
        )
    except (
        TypeError,
        ValueError,
    ):
        return validation_error(
            "Invalid chapter order. Enter a whole number."
        )

    if new_order <= 0:
        return validation_error(
            "Chapter order must be greater than zero."
        )

    valid_statuses = {
        choice[0]
        for choice in CourseChapter.STATUS_CHOICES
    }

    if status not in valid_statuses:
        return validation_error(
            "Invalid chapter status selected."
        )

    old_name = chapter.chapter_name
    old_description = (
        chapter.chapter_description
        or ""
    )
    old_order = chapter.chapter_order
    old_status = chapter.status

    with transaction.atomic():

        all_chapters = list(
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

        total_chapters = len(
            all_chapters
        )

        if new_order > total_chapters:
            return validation_error(
                (
                    "Chapter order cannot be greater than "
                    f"{total_chapters}."
                )
            )

        ordered = [
            item
            for item in all_chapters
            if item.id != chapter.id
        ]

        ordered.insert(
            new_order - 1,
            chapter,
        )

        temporary_start = (
            total_chapters + 1000
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

        for position, item in enumerate(
            ordered,
            start=1,
        ):
            item.chapter_order = position

        chapter.chapter_name = chapter_name
        chapter.chapter_description = (
            chapter_description
        )
        chapter.chapter_order = new_order
        chapter.status = status

        if is_admin:
            chapter.updated_by = None
            chapter.updated_by_admin = request.user
        else:
            chapter.updated_by = teacher
            chapter.updated_by_admin = None

        chapter.save()

        actor = _actor_data(
            request,
            teacher=(
                None
                if is_admin
                else teacher
            ),
        )

        if old_name != chapter_name:
            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="updated",
                field_name="chapter_name",
                old_value=old_name,
                new_value=chapter_name,
                change_summary=(
                    "Chapter name was updated."
                ),
            )

        if old_description != chapter_description:
            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="updated",
                field_name="chapter_description",
                old_value=old_description,
                new_value=chapter_description,
                change_summary=(
                    "Chapter description was updated."
                ),
            )

        if old_order != new_order:
            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="order_changed",
                field_name="chapter_order",
                old_value=str(old_order),
                new_value=str(new_order),
                change_summary=(
                    f"Chapter order changed from "
                    f"{old_order} to {new_order}."
                ),
            )

        if old_status != status:
            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="status_changed",
                field_name="status",
                old_value=old_status,
                new_value=status,
                change_summary=(
                    f"Chapter status changed from "
                    f"{old_status} to {status}."
                ),
            )

    request.session.pop(
        "chapter_edit_open",
        None,
    )
    request.session.pop(
        "chapter_edit_error",
        None,
    )
    request.session.pop(
        "chapter_edit_form",
        None,
    )
    request.session.modified = True

    messages.success(
        request,
        (
            f'Chapter "{chapter.chapter_name}" '
            "updated successfully."
        ),
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
    )


# ============================================================
# CREATE / UPLOAD VIDEO
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_video_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to manage videos.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    if request.method != "POST":
        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="videos",
        )

    teacher = auth["teacher"]
    is_admin = auth["is_admin"]

    action = (
        request.POST.get(
            "action",
            "upload",
        )
        or "upload"
    ).strip().lower()

    # ------------------------------------------------------------
    # UPLOAD
    # ------------------------------------------------------------

    if action == "upload":

        video_name = (
            request.POST.get(
                "video_name",
                "",
            )
            or ""
        ).strip()

        video_description = (
            request.POST.get(
                "video_description",
                "",
            )
            or ""
        ).strip()

        video_file = request.FILES.get(
            "video_file"
        )

        def upload_error(message):
            request.session[
                "video_upload_open"
            ] = True

            request.session[
                "video_upload_error"
            ] = message

            request.session[
                "video_upload_form"
            ] = {
                "video_name": video_name,
                "video_description": video_description,
            }

            request.session.modified = True

            return _redirect_builder(
                batch,
                subject,
                chapter=chapter,
                view="videos",
            )

        if not video_name:
            return upload_error(
                "Video name is required."
            )

        if len(video_name) > 255:
            return upload_error(
                "Video name cannot exceed 255 characters."
            )

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
            return upload_error(
                "A video with this name already exists in this chapter."
            )

        if not video_description:
            return upload_error(
                "Video description is required."
            )

        if len(video_description) > 5000:
            return upload_error(
                "Video description cannot exceed 5000 characters."
            )

        valid_file, file_error = _validate_mp4(
            video_file
        )

        if not valid_file:
            return upload_error(
                file_error
            )

        with transaction.atomic():

            existing_videos = ChapterVideo.objects.filter(
                chapter=chapter,
                is_deleted=False,
            )

            video_order = get_next_order(
                existing_videos,
                order_field="video_order",
                deleted_field="is_deleted",
            )

            video = ChapterVideo.objects.create(
                chapter=chapter,
                video_name=video_name,
                video_description=video_description,
                video_file=video_file,
                video_order=video_order,

                created_by=(
                    None
                    if is_admin
                    else teacher
                ),

                created_by_admin=(
                    request.user
                    if is_admin
                    else None
                ),

                updated_by=(
                    None
                    if is_admin
                    else teacher
                ),

                updated_by_admin=(
                    request.user
                    if is_admin
                    else None
                ),

                delete_requested=False,
                delete_status="pending",
                is_deleted=False,
            )

            actor = _actor_data(
                request,
                teacher=(
                    None
                    if is_admin
                    else teacher
                ),
            )

            VideoChangeLog.objects.create(
                video=video,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="created",
                field_name="video",
                old_value="",
                new_value=(
                    f"Name: {video.video_name}; "
                    f"Description: {video.video_description}; "
                    f"Order: {video.video_order}; "
                    f"File: {getattr(video_file, 'name', '')}"
                ),
                change_summary=(
                    f'{actor["name"]} created video '
                    f'"{video.video_name}" at order '
                    f"{video.video_order}."
                ),
            )

        for key in (
            "video_upload_open",
            "video_upload_error",
            "video_upload_form",
        ):
            request.session.pop(
                key,
                None,
            )

        request.session.modified = True

        messages.success(
            request,
            (
                f'Video "{video.video_name}" '
                "uploaded successfully."
            ),
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="videos",
        )

    # ------------------------------------------------------------
    # EDIT
    # ------------------------------------------------------------

    if action == "edit":

        video_id_raw = (
            request.POST.get(
                "video_id",
                "",
            )
            or ""
        ).strip()

        if not video_id_raw.isdigit():
            messages.error(
                request,
                "The selected video is invalid.",
            )
            return _redirect_builder(
                batch,
                subject,
                chapter=chapter,
                view="videos",
            )

        video = _get_video(
            chapter,
            int(video_id_raw),
        )

        old_name = video.video_name or ""
        old_description = (
            video.video_description
            or ""
        )
        old_order = video.video_order
        old_file_name = (
            getattr(
                video.video_file,
                "name",
                "",
            )
            or ""
        )

        new_name = (
            request.POST.get(
                "video_name",
                "",
            )
            or ""
        ).strip()

        new_description = (
            request.POST.get(
                "video_description",
                "",
            )
            or ""
        ).strip()

        order_raw = (
            request.POST.get(
                "video_order",
                "",
            )
            or ""
        ).strip()

        replacement_file = request.FILES.get(
            "video_file"
        )

        def edit_error(message):
            request.session[
                "video_edit_open"
            ] = True

            request.session[
                "video_edit_error"
            ] = message

            request.session[
                "video_edit_form"
            ] = {
                "video_id": video.id,
                "video_name": new_name,
                "video_description": new_description,
                "video_order": (
                    order_raw
                    or str(old_order)
                ),
                "current_file_name": old_file_name,
            }

            request.session.modified = True

            return _redirect_builder(
                batch,
                subject,
                chapter=chapter,
                view="videos",
            )

        if not new_name:
            return edit_error(
                "Video name is required."
            )

        if len(new_name) > 255:
            return edit_error(
                "Video name cannot exceed 255 characters."
            )

        duplicate = (
            ChapterVideo.objects
            .filter(
                chapter=chapter,
                video_name__iexact=new_name,
                is_deleted=False,
            )
            .exclude(
                id=video.id,
            )
            .exists()
        )

        if duplicate:
            return edit_error(
                "A video with this name already exists in this chapter."
            )

        if not new_description:
            return edit_error(
                "Video description is required."
            )

        if len(new_description) > 5000:
            return edit_error(
                "Video description cannot exceed 5000 characters."
            )

        if not order_raw:
            return edit_error(
                "Video order is required."
            )

        try:
            new_order = int(
                order_raw
            )
        except (
            TypeError,
            ValueError,
        ):
            return edit_error(
                "Video order must be a valid number."
            )

        if new_order <= 0:
            return edit_error(
                "Video order must be greater than zero."
            )

        current_count = (
            ChapterVideo.objects
            .filter(
                chapter=chapter,
                is_deleted=False,
            )
            .count()
        )

        if new_order > current_count:
            return edit_error(
                (
                    f"Video order must be between "
                    f"1 and {current_count}."
                )
            )

        if replacement_file:

            valid_file, file_error = _validate_mp4(
                replacement_file
            )

            if not valid_file:
                return edit_error(
                    file_error
                )

        with transaction.atomic():

            locked_videos = list(
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

            locked_video = next(
                (
                    item
                    for item in locked_videos
                    if item.id == video.id
                ),
                None,
            )

            if locked_video is None:
                return edit_error(
                    "The selected video no longer exists."
                )

            old_order = locked_video.video_order

            if new_order > old_order:

                ChapterVideo.objects.filter(
                    chapter=chapter,
                    is_deleted=False,
                    video_order__gt=old_order,
                    video_order__lte=new_order,
                ).update(
                    video_order=F(
                        "video_order"
                    ) - 1
                )

            elif new_order < old_order:

                ChapterVideo.objects.filter(
                    chapter=chapter,
                    is_deleted=False,
                    video_order__gte=new_order,
                    video_order__lt=old_order,
                ).update(
                    video_order=F(
                        "video_order"
                    ) + 1
                )

            locked_video.video_name = new_name
            locked_video.video_description = (
                new_description
            )
            locked_video.video_order = new_order

            if is_admin:
                locked_video.updated_by = None
                locked_video.updated_by_admin = (
                    request.user
                )
            else:
                locked_video.updated_by = teacher
                locked_video.updated_by_admin = None

            if replacement_file:
                locked_video.video_file = (
                    replacement_file
                )

            locked_video.save()

            actor = _actor_data(
                request,
                teacher=(
                    None
                    if is_admin
                    else teacher
                ),
            )

            if old_name != new_name:
                VideoChangeLog.objects.create(
                    video=locked_video,
                    changed_by=actor["teacher"],
                    changed_by_admin=actor["admin"],
                    action="name_changed",
                    field_name="video_name",
                    old_value=old_name,
                    new_value=new_name,
                    change_summary=(
                        "Video name was updated."
                    ),
                )

            if old_description != new_description:
                VideoChangeLog.objects.create(
                    video=locked_video,
                    changed_by=actor["teacher"],
                    changed_by_admin=actor["admin"],
                    action="description_changed",
                    field_name="video_description",
                    old_value=old_description,
                    new_value=new_description,
                    change_summary=(
                        "Video description was updated."
                    ),
                )

            if old_order != new_order:
                VideoChangeLog.objects.create(
                    video=locked_video,
                    changed_by=actor["teacher"],
                    changed_by_admin=actor["admin"],
                    action="order_changed",
                    field_name="video_order",
                    old_value=str(old_order),
                    new_value=str(new_order),
                    change_summary=(
                        f"Video order changed from "
                        f"{old_order} to {new_order}."
                    ),
                )

            if replacement_file:
                VideoChangeLog.objects.create(
                    video=locked_video,
                    changed_by=actor["teacher"],
                    changed_by_admin=actor["admin"],
                    action="file_changed",
                    field_name="video_file",
                    old_value=(
                        old_file_name
                        or "Previous MP4 file"
                    ),
                    new_value=(
                        getattr(
                            replacement_file,
                            "name",
                            "",
                        )
                        or "New MP4 file"
                    ),
                    change_summary=(
                        "Video file was replaced."
                    ),
                )

        for key in (
            "video_edit_open",
            "video_edit_error",
            "video_edit_form",
        ):
            request.session.pop(
                key,
                None,
            )

        request.session.modified = True

        messages.success(
            request,
            (
                f'Video "{locked_video.video_name}" '
                "updated successfully."
            ),
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="videos",
        )

    messages.error(
        request,
        "Invalid video action.",
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="videos",
    )


# ============================================================
# CREATE / UPLOAD PDF
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_pdf_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to manage PDF notes.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    if request.method != "POST":
        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    teacher = auth["teacher"]
    is_admin = auth["is_admin"]

    action = (
        request.POST.get(
            "action",
            "upload",
        )
        or "upload"
    ).strip().lower()

    if action == "upload":

        pdf_name = (
            request.POST.get(
                "pdf_name",
                "",
            )
            or ""
        ).strip()

        pdf_description = (
            request.POST.get(
                "pdf_description",
                "",
            )
            or ""
        ).strip()

        pdf_file = request.FILES.get(
            "pdf_file"
        )

        pdf_thumbnail = request.FILES.get(
            "pdf_thumbnail"
        )

        def upload_error(message):
            request.session[
                "pdf_upload_open"
            ] = True

            request.session[
                "pdf_upload_error"
            ] = message

            request.session[
                "pdf_upload_form"
            ] = {
                "pdf_name": pdf_name,
                "pdf_description": pdf_description,
            }

            request.session.modified = True

            return _redirect_builder(
                batch,
                subject,
                chapter=chapter,
                view="pdfs",
            )

        if not pdf_name:
            return upload_error(
                "PDF notes name is required."
            )

        if len(pdf_name) > 255:
            return upload_error(
                "PDF notes name cannot exceed 255 characters."
            )

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
            return upload_error(
                "A PDF with this name already exists in this chapter."
            )

        if not pdf_description:
            return upload_error(
                "PDF notes description is required."
            )

        if len(pdf_description) > 5000:
            return upload_error(
                "PDF notes description cannot exceed 5000 characters."
            )

        valid_pdf, pdf_error = _validate_pdf(
            pdf_file
        )

        if not valid_pdf:
            return upload_error(
                pdf_error
            )

        valid_thumbnail, thumbnail_error = (
            _validate_thumbnail(
                pdf_thumbnail
            )
        )

        if not valid_thumbnail:
            return upload_error(
                thumbnail_error
            )

        with transaction.atomic():

            existing_pdfs = ChapterPDF.objects.filter(
                chapter=chapter,
                is_deleted=False,
            )

            pdf_order = get_next_order(
                existing_pdfs,
                order_field="pdf_order",
                deleted_field="is_deleted",
            )

            pdf = ChapterPDF.objects.create(
                chapter=chapter,
                pdf_name=pdf_name,
                pdf_description=pdf_description,
                pdf_file=pdf_file,
                pdf_thumbnail=pdf_thumbnail,
                pdf_order=pdf_order,

                created_by=(
                    None
                    if is_admin
                    else teacher
                ),

                created_by_admin=(
                    request.user
                    if is_admin
                    else None
                ),

                updated_by=(
                    None
                    if is_admin
                    else teacher
                ),

                updated_by_admin=(
                    request.user
                    if is_admin
                    else None
                ),

                delete_requested=False,
                delete_requested_by=None,
                delete_requested_at=None,
                delete_reason="",
                delete_status="pending",
                is_deleted=False,
            )

            actor = _actor_data(
                request,
                teacher=(
                    None
                    if is_admin
                    else teacher
                ),
            )

            thumbnail_name = (
                getattr(
                    pdf_thumbnail,
                    "name",
                    "",
                )
                or "Default NeoLearner branding thumbnail"
            )

            PDFChangeLog.objects.create(
                pdf=pdf,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="created",
                field_name="pdf",
                old_value="",
                new_value=(
                    f"Name: {pdf.pdf_name}; "
                    f"Description: {pdf.pdf_description}; "
                    f"Order: {pdf.pdf_order}; "
                    f"File: {getattr(pdf_file, 'name', '')}; "
                    f"Thumbnail: {thumbnail_name}"
                ),
                change_summary=(
                    f'{actor["name"]} created PDF '
                    f'"{pdf.pdf_name}" at order '
                    f"{pdf.pdf_order}."
                ),
            )

        for key in (
            "pdf_upload_open",
            "pdf_upload_error",
            "pdf_upload_form",
        ):
            request.session.pop(
                key,
                None,
            )

        request.session.modified = True

        messages.success(
            request,
            (
                f'PDF "{pdf.pdf_name}" uploaded '
                f"successfully as PDF {pdf.pdf_order}."
            ),
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    messages.error(
        request,
        "Invalid PDF action.",
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="pdfs",
    )


# ============================================================
# EDIT PDF
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_edit_pdf_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    pdf_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to edit PDF notes.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    pdf = _get_pdf(
        chapter,
        pdf_id,
    )

    teacher = auth["teacher"]
    is_admin = auth["is_admin"]

    if request.method == "GET":

        current_thumbnail_url = ""

        if pdf.pdf_thumbnail:
            try:
                current_thumbnail_url = (
                    pdf.pdf_thumbnail.url
                )
            except Exception:
                current_thumbnail_url = ""

        request.session[
            "pdf_edit_open"
        ] = True

        request.session[
            "pdf_edit_error"
        ] = ""

        request.session[
            "pdf_edit_form"
        ] = {
            "pdf_id": pdf.id,
            "pdf_name": pdf.pdf_name or "",
            "pdf_description": (
                pdf.pdf_description or ""
            ),
            "pdf_order": str(
                pdf.pdf_order
            ),
            "current_file_name": (
                getattr(
                    pdf.pdf_file,
                    "name",
                    "",
                )
                or ""
            ),
            "current_thumbnail_url": (
                current_thumbnail_url
            ),
        }

        request.session.modified = True

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    if request.method != "POST":
        messages.error(
            request,
            "Invalid PDF edit request.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    new_name = (
        request.POST.get(
            "pdf_name",
            "",
        )
        or ""
    ).strip()

    new_description = (
        request.POST.get(
            "pdf_description",
            "",
        )
        or ""
    ).strip()

    order_raw = (
        request.POST.get(
            "pdf_order",
            "",
        )
        or ""
    ).strip()

    replacement_file = request.FILES.get(
        "pdf_file"
    )

    replacement_thumbnail = request.FILES.get(
        "pdf_thumbnail"
    )

    old_name = pdf.pdf_name or ""
    old_description = (
        pdf.pdf_description or ""
    )
    old_order = pdf.pdf_order

    old_file_name = (
        getattr(
            pdf.pdf_file,
            "name",
            "",
        )
        or ""
    )

    old_thumbnail_name = ""

    if pdf.pdf_thumbnail:
        old_thumbnail_name = str(
            getattr(
                pdf.pdf_thumbnail,
                "name",
                "",
            )
            or ""
        )

    def edit_error(message):
        request.session[
            "pdf_edit_open"
        ] = True

        request.session[
            "pdf_edit_error"
        ] = message

        request.session[
            "pdf_edit_form"
        ] = {
            "pdf_id": pdf.id,
            "pdf_name": new_name,
            "pdf_description": new_description,
            "pdf_order": (
                order_raw
                or str(old_order)
            ),
            "current_file_name": old_file_name,
        }

        request.session.modified = True

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    if not new_name:
        return edit_error(
            "PDF notes name is required."
        )

    if len(new_name) > 255:
        return edit_error(
            "PDF notes name cannot exceed 255 characters."
        )

    duplicate = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            pdf_name__iexact=new_name,
            is_deleted=False,
        )
        .exclude(
            id=pdf.id,
        )
        .exists()
    )

    if duplicate:
        return edit_error(
            "A PDF with this name already exists in this chapter."
        )

    if not new_description:
        return edit_error(
            "PDF notes description is required."
        )

    if len(new_description) > 5000:
        return edit_error(
            "PDF notes description cannot exceed 5000 characters."
        )

    if not order_raw:
        return edit_error(
            "PDF order is required."
        )

    try:
        new_order = int(
            order_raw
        )
    except (
        TypeError,
        ValueError,
    ):
        return edit_error(
            "PDF order must be a valid number."
        )

    if new_order <= 0:
        return edit_error(
            "PDF order must be greater than zero."
        )

    current_count = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            is_deleted=False,
        )
        .count()
    )

    if new_order > current_count:
        return edit_error(
            (
                f"PDF order must be between "
                f"1 and {current_count}."
            )
        )

    if replacement_file:

        valid_pdf, pdf_error = _validate_pdf(
            replacement_file
        )

        if not valid_pdf:
            return edit_error(
                pdf_error
            )

    if replacement_thumbnail:

        valid_thumbnail, thumbnail_error = (
            _validate_thumbnail(
                replacement_thumbnail
            )
        )

        if not valid_thumbnail:
            return edit_error(
                thumbnail_error
            )

    with transaction.atomic():

        locked_pdfs = list(
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

        locked_pdf = next(
            (
                item
                for item in locked_pdfs
                if item.id == pdf.id
            ),
            None,
        )

        if locked_pdf is None:
            return edit_error(
                "The selected PDF no longer exists."
            )

        original_orders = {
            item.id: item.pdf_order
            for item in locked_pdfs
        }

        reordered_ids = [
            item.id
            for item in locked_pdfs
            if item.id != locked_pdf.id
        ]

        reordered_ids.insert(
            new_order - 1,
            locked_pdf.id,
        )

        pdf_by_id = {
            item.id: item
            for item in locked_pdfs
        }

        for index, item_id in enumerate(
            reordered_ids,
            start=1,
        ):
            pdf_by_id[
                item_id
            ].pdf_order = index

        locked_pdf.pdf_name = new_name
        locked_pdf.pdf_description = (
            new_description
        )

        if is_admin:
            locked_pdf.updated_by = None
            locked_pdf.updated_by_admin = (
                request.user
            )
        else:
            locked_pdf.updated_by = teacher
            locked_pdf.updated_by_admin = None

        if replacement_file:
            locked_pdf.pdf_file = (
                replacement_file
            )

        if replacement_thumbnail:
            locked_pdf.pdf_thumbnail = (
                replacement_thumbnail
            )

        for target in locked_pdfs:

            original_order = original_orders[
                target.id
            ]

            if target.id == locked_pdf.id:
                target.save()

            elif original_order != target.pdf_order:

                if is_admin:
                    target.updated_by = None
                    target.updated_by_admin = request.user
                else:
                    target.updated_by = teacher
                    target.updated_by_admin = None

                target.save(
                    update_fields=[
                        "pdf_order",
                        "updated_by",
                        "updated_by_admin",
                        "updated_at",
                    ]
                )

        actor = _actor_data(
            request,
            teacher=(
                None
                if is_admin
                else teacher
            ),
        )

        if old_name != new_name:
            PDFChangeLog.objects.create(
                pdf=locked_pdf,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="name_changed",
                field_name="pdf_name",
                old_value=old_name,
                new_value=new_name,
                change_summary=(
                    "PDF notes name was updated."
                ),
            )

        if old_description != new_description:
            PDFChangeLog.objects.create(
                pdf=locked_pdf,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="description_changed",
                field_name="pdf_description",
                old_value=old_description,
                new_value=new_description,
                change_summary=(
                    "PDF notes description was updated."
                ),
            )

        for target in locked_pdfs:

            original_order = original_orders[
                target.id
            ]

            if original_order != target.pdf_order:
                PDFChangeLog.objects.create(
                    pdf=target,
                    changed_by=actor["teacher"],
                    changed_by_admin=actor["admin"],
                    action="order_changed",
                    field_name="pdf_order",
                    old_value=str(
                        original_order
                    ),
                    new_value=str(
                        target.pdf_order
                    ),
                    change_summary=(
                        f'PDF "{target.pdf_name}" '
                        f"order changed from "
                        f"{original_order} to "
                        f"{target.pdf_order}."
                    ),
                )

        if replacement_file:
            PDFChangeLog.objects.create(
                pdf=locked_pdf,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="file_changed",
                field_name="pdf_file",
                old_value=(
                    old_file_name
                    or "Previous PDF file"
                ),
                new_value=(
                    getattr(
                        replacement_file,
                        "name",
                        "",
                    )
                    or "New PDF file"
                ),
                change_summary=(
                    "PDF file was replaced."
                ),
            )

        if replacement_thumbnail:
            PDFChangeLog.objects.create(
                pdf=locked_pdf,
                changed_by=actor["teacher"],
                changed_by_admin=actor["admin"],
                action="thumbnail_changed",
                field_name="pdf_thumbnail",
                old_value=(
                    old_thumbnail_name
                    or "Default NeoLearner thumbnail"
                ),
                new_value=(
                    getattr(
                        replacement_thumbnail,
                        "name",
                        "",
                    )
                    or "New PDF thumbnail"
                ),
                change_summary=(
                    "PDF thumbnail was replaced."
                ),
            )

    for key in (
        "pdf_edit_open",
        "pdf_edit_error",
        "pdf_edit_form",
    ):
        request.session.pop(
            key,
            None,
        )

    request.session.modified = True

    messages.success(
        request,
        (
            f'PDF "{locked_pdf.pdf_name}" '
            "updated successfully."
        ),
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="pdfs",
    )


# ============================================================
# CREATE QUIZ
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_quiz_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to manage quizzes.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    if request.method != "POST":
        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="quizzes",
        )

    teacher = auth["teacher"]
    is_admin = auth["is_admin"]

    action = (
        request.POST.get(
            "action",
            "",
        )
        or ""
    ).strip().lower()

    if action != "create_quiz":
        messages.error(
            request,
            "Invalid quiz action.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="quizzes",
        )

    quiz_name = (
        request.POST.get(
            "quiz_name",
            "",
        )
        or ""
    ).strip()

    quiz_description = (
        request.POST.get(
            "quiz_description",
            "",
        )
        or ""
    ).strip()

    attempt_limit_raw = (
        request.POST.get(
            "attempt_limit",
            "",
        )
        or ""
    ).strip()

    question_count_raw = (
        request.POST.get(
            "question_count",
            "",
        )
        or ""
    ).strip()

    question_count = (
        int(question_count_raw)
        if question_count_raw.isdigit()
        else 0
    )

    question_count = min(
        max(question_count, 0),
        100,
    )

    questions = []

    for index in range(
        question_count
    ):
        questions.append(
            {
                "question_text": (
                    request.POST.get(
                        f"question_{index}_text",
                        "",
                    )
                    or ""
                ).strip(),

                "option_a": (
                    request.POST.get(
                        f"question_{index}_option_a",
                        "",
                    )
                    or ""
                ).strip(),

                "option_b": (
                    request.POST.get(
                        f"question_{index}_option_b",
                        "",
                    )
                    or ""
                ).strip(),

                "option_c": (
                    request.POST.get(
                        f"question_{index}_option_c",
                        "",
                    )
                    or ""
                ).strip(),

                "option_d": (
                    request.POST.get(
                        f"question_{index}_option_d",
                        "",
                    )
                    or ""
                ).strip(),

                "correct_option": (
                    request.POST.get(
                        f"question_{index}_correct",
                        "",
                    )
                    or ""
                ).strip().upper(),

                "marks": (
                    request.POST.get(
                        f"question_{index}_marks",
                        "",
                    )
                    or ""
                ).strip(),
            }
        )

    form_data = {
        "quiz_name": quiz_name,
        "quiz_description": quiz_description,
        "attempt_limit": attempt_limit_raw,
        "questions": questions,
    }

    def quiz_error(message):
        request.session[
            "quiz_create_open"
        ] = True

        request.session[
            "quiz_create_error"
        ] = message

        request.session[
            "quiz_create_form"
        ] = form_data

        request.session.modified = True

        messages.error(
            request,
            message,
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="quizzes",
        )

    if not quiz_name:
        return quiz_error(
            "Quiz name is required."
        )

    if len(quiz_name) < 2:
        return quiz_error(
            "Quiz name must contain at least 2 characters."
        )

    if len(quiz_name) > 255:
        return quiz_error(
            "Quiz name cannot exceed 255 characters."
        )

    if not quiz_description:
        return quiz_error(
            "Quiz description is required."
        )

    if len(quiz_description) < 5:
        return quiz_error(
            "Quiz description must contain at least 5 characters."
        )

    if len(quiz_description) > 5000:
        return quiz_error(
            "Quiz description cannot exceed 5000 characters."
        )

    if not attempt_limit_raw:
        return quiz_error(
            "Maximum attempts is required."
        )

    if not attempt_limit_raw.isdigit():
        return quiz_error(
            "Maximum attempts must be a positive whole number."
        )

    attempt_limit = int(
        attempt_limit_raw
    )

    if attempt_limit < 1:
        return quiz_error(
            "Maximum attempts must be greater than zero."
        )

    if attempt_limit > 100:
        return quiz_error(
            "Maximum attempts cannot be greater than 100."
        )

    if not questions:
        return quiz_error(
            "Add at least one question before saving the quiz."
        )

    validated_questions = []

    for index, question_data in enumerate(
        questions,
        start=1,
    ):
        question_text = (
            question_data[
                "question_text"
            ]
        )

        options = {
            "A": question_data[
                "option_a"
            ],
            "B": question_data[
                "option_b"
            ],
            "C": question_data[
                "option_c"
            ],
            "D": question_data[
                "option_d"
            ],
        }

        correct_option = (
            question_data[
                "correct_option"
            ]
        )

        marks_raw = (
            question_data[
                "marks"
            ]
        )

        if not question_text:
            return quiz_error(
                (
                    f"Question {index}: "
                    "question text is required."
                )
            )

        if len(question_text) < 3:
            return quiz_error(
                (
                    f"Question {index}: "
                    "question must contain at least "
                    "3 characters."
                )
            )

        if len(question_text) > 10000:
            return quiz_error(
                (
                    f"Question {index}: "
                    "question cannot exceed "
                    "10000 characters."
                )
            )

        for label, value in options.items():

            if not value:
                return quiz_error(
                    (
                        f"Question {index}: "
                        f"Option {label} is required."
                    )
                )

            if len(value) > 500:
                return quiz_error(
                    (
                        f"Question {index}: "
                        f"Option {label} cannot exceed "
                        "500 characters."
                    )
                )

        if len(
            {
                value.casefold()
                for value in options.values()
            }
        ) != 4:
            return quiz_error(
                (
                    f"Question {index}: "
                    "all four answer options must be different."
                )
            )

        if correct_option not in {
            "A",
            "B",
            "C",
            "D",
        }:
            return quiz_error(
                (
                    f"Question {index}: "
                    "select exactly one correct answer."
                )
            )

        if not marks_raw or not marks_raw.isdigit():
            return quiz_error(
                (
                    f"Question {index}: "
                    "marks must be a positive whole number."
                )
            )

        marks = int(
            marks_raw
        )

        if marks < 1 or marks > 1000:
            return quiz_error(
                (
                    f"Question {index}: "
                    "marks must be between "
                    "1 and 1000."
                )
            )

        validated_questions.append(
            {
                "question_text": question_text,
                "marks": marks,
                "options": options,
                "correct_option": correct_option,
            }
        )

    duplicate_quiz = (
        ChapterQuiz.objects
        .filter(
            chapter=chapter,
            quiz_name__iexact=quiz_name,
            is_deleted=False,
        )
        .exists()
    )

    if duplicate_quiz:
        return quiz_error(
            "A quiz with this name already exists in this chapter."
        )

    with transaction.atomic():

        quiz = ChapterQuiz.objects.create(
            chapter=chapter,
            quiz_name=quiz_name,
            quiz_description=quiz_description,
            attempt_limit=attempt_limit,

            created_by=(
                None
                if is_admin
                else teacher
            ),

            created_by_admin=(
                request.user
                if is_admin
                else None
            ),

            updated_by=(
                None
                if is_admin
                else teacher
            ),

            updated_by_admin=(
                request.user
                if is_admin
                else None
            ),

            delete_requested=False,
            delete_requested_by=None,
            delete_requested_at=None,
            delete_reason="",
            delete_status="pending",
            is_deleted=False,
        )

        total_marks = 0

        for question_data in validated_questions:

            question = QuizQuestion.objects.create(
                quiz=quiz,
                question_text=(
                    question_data[
                        "question_text"
                    ]
                ),
                marks=(
                    question_data[
                        "marks"
                    ]
                ),
            )

            total_marks += question.marks

            for label, option_text in (
                question_data[
                    "options"
                ].items()
            ):
                QuizOption.objects.create(
                    question=question,
                    option_label=label,
                    option_text=option_text,
                    is_correct=(
                        label
                        == question_data[
                            "correct_option"
                        ]
                    ),
                )

        actor = _actor_data(
            request,
            teacher=(
                None
                if is_admin
                else teacher
            ),
        )

        QuizChangeLog.objects.create(
            quiz=quiz,
            changed_by=actor["teacher"],
            changed_by_admin=actor["admin"],
            action="created",
            field_name="quiz",
            old_value="",
            new_value=(
                f"Name: {quiz.quiz_name}; "
                f"Description: {quiz.quiz_description}; "
                f"Attempt Limit: {quiz.attempt_limit}; "
                f"Questions: {len(validated_questions)}; "
                f"Total Marks: {total_marks}"
            ),
            change_summary=(
                f'{actor["name"]} created quiz '
                f'"{quiz.quiz_name}" with '
                f"{len(validated_questions)} question"
                f'{"s" if len(validated_questions) != 1 else ""}.'
            ),
        )

    for key in (
        "quiz_create_open",
        "quiz_create_error",
        "quiz_create_form",
        "quiz_question_open",
        "quiz_question_error",
        "quiz_question_form",
        "quiz_question_quiz_id",
    ):
        request.session.pop(
            key,
            None,
        )

    request.session.modified = True

    messages.success(
        request,
        (
            f'Quiz "{quiz.quiz_name}" created '
            f"successfully with "
            f"{len(validated_questions)} question"
            f'{"s" if len(validated_questions) != 1 else ""}.'
        ),
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="quizzes",
    )


# ============================================================
# TEACHER DELETE REQUEST — CHAPTER
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_request_chapter_delete_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"] or not auth["is_teacher"]:
        messages.error(
            request,
            "Only an assigned Teacher can request chapter deletion.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    if request.method != "POST":
        messages.error(
            request,
            "Invalid delete request.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
        )

    teacher = auth["teacher"]

    if (
        chapter.delete_requested
        and chapter.delete_status == "pending"
    ):
        messages.info(
            request,
            "A delete request for this chapter is already pending.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
        )

    delete_reason = (
        request.POST.get(
            "delete_reason",
            "",
        )
        or ""
    ).strip()

    if not delete_reason:
        messages.error(
            request,
            "Please provide a reason for deleting the chapter.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
        )

    if len(delete_reason) > 2000:
        messages.error(
            request,
            "Delete reason cannot exceed 2000 characters.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
        )

    with transaction.atomic():

        chapter.delete_requested = True
        chapter.delete_requested_by = teacher
        chapter.delete_requested_at = timezone.now()
        chapter.delete_reason = delete_reason
        chapter.delete_status = "pending"

        chapter.save(
            update_fields=[
                "delete_requested",
                "delete_requested_by",
                "delete_requested_at",
                "delete_reason",
                "delete_status",
                "updated_at",
            ]
        )

        ChapterChangeLog.objects.create(
            chapter=chapter,
            changed_by=teacher,
            changed_by_admin=None,
            action="delete_requested",
            field_name="delete_request",
            old_value="",
            new_value=delete_reason,
            change_summary=(
                "Chapter deletion was requested."
            ),
        )

    messages.success(
        request,
        "Chapter deletion request submitted successfully.",
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
    )


# ============================================================
# TEACHER DELETE REQUEST — PDF
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_request_pdf_delete_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    pdf_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"] or not auth["is_teacher"]:
        messages.error(
            request,
            "Only an assigned Teacher can request PDF deletion.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    pdf = _get_pdf(
        chapter,
        pdf_id,
    )

    if request.method != "POST":
        messages.error(
            request,
            "Invalid delete request.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    teacher = auth["teacher"]

    if (
        pdf.delete_requested
        and pdf.delete_status == "pending"
    ):
        messages.info(
            request,
            "A delete request for this PDF is already pending.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    delete_reason = (
        request.POST.get(
            "delete_reason",
            "",
        )
        or ""
    ).strip()

    if not delete_reason:
        messages.error(
            request,
            "Please provide a reason for deleting the PDF.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    if len(delete_reason) > 2000:
        messages.error(
            request,
            "Delete reason cannot exceed 2000 characters.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="pdfs",
        )

    with transaction.atomic():

        pdf.delete_requested = True
        pdf.delete_requested_by = teacher
        pdf.delete_requested_at = timezone.now()
        pdf.delete_reason = delete_reason
        pdf.delete_status = "pending"
        pdf.updated_by = teacher
        pdf.updated_by_admin = None

        pdf.save(
            update_fields=[
                "delete_requested",
                "delete_requested_by",
                "delete_requested_at",
                "delete_reason",
                "delete_status",
                "updated_by",
                "updated_by_admin",
                "updated_at",
            ]
        )

        PDFChangeLog.objects.create(
            pdf=pdf,
            changed_by=teacher,
            changed_by_admin=None,
            action="delete_requested",
            field_name="delete_request",
            old_value="",
            new_value=delete_reason,
            change_summary=(
                "PDF deletion was requested."
            ),
        )

    messages.success(
        request,
        "PDF deletion request submitted successfully.",
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="pdfs",
    )


# ============================================================
# TEACHER DELETE REQUEST — QUIZ
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_request_quiz_delete_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    quiz_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"] or not auth["is_teacher"]:
        messages.error(
            request,
            "Only an assigned Teacher can request quiz deletion.",
        )
        return _redirect_builder(
            batch,
            subject,
        )

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    quiz = _get_quiz(
        chapter,
        quiz_id,
    )

    if request.method != "POST":
        messages.error(
            request,
            "Invalid delete request.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="quizzes",
        )

    teacher = auth["teacher"]

    if (
        quiz.delete_requested
        and quiz.delete_status == "pending"
    ):
        messages.info(
            request,
            "A delete request for this quiz is already pending.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="quizzes",
        )

    delete_reason = (
        request.POST.get(
            "delete_reason",
            "",
        )
        or ""
    ).strip()

    if not delete_reason:
        messages.error(
            request,
            "Please provide a reason for deleting the quiz.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="quizzes",
        )

    if len(delete_reason) > 2000:
        messages.error(
            request,
            "Delete reason cannot exceed 2000 characters.",
        )

        return _redirect_builder(
            batch,
            subject,
            chapter=chapter,
            view="quizzes",
        )

    with transaction.atomic():

        quiz.delete_requested = True
        quiz.delete_requested_by = teacher
        quiz.delete_requested_at = timezone.now()
        quiz.delete_reason = delete_reason
        quiz.delete_status = "pending"
        quiz.updated_by = teacher
        quiz.updated_by_admin = None

        quiz.save(
            update_fields=[
                "delete_requested",
                "delete_requested_by",
                "delete_requested_at",
                "delete_reason",
                "delete_status",
                "updated_by",
                "updated_by_admin",
                "updated_at",
            ]
        )

        QuizChangeLog.objects.create(
            quiz=quiz,
            changed_by=teacher,
            changed_by_admin=None,
            action="delete_requested",
            field_name="delete_request",
            old_value="",
            new_value=delete_reason,
            change_summary=(
                "Quiz deletion was requested."
            ),
        )

    messages.success(
        request,
        "Quiz deletion request submitted successfully.",
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="quizzes",
    )


# ============================================================
# TIMELINE REDIRECTS
# ============================================================


@login_required
def course_video_timeline_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    video_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to view video history.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    video = _get_video(
        chapter,
        video_id,
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="video_timeline",
        extra=[
            f"video={video.id}",
        ],
    )


@login_required
def course_pdf_timeline_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    pdf_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to view PDF history.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    pdf = _get_pdf(
        chapter,
        pdf_id,
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="pdf_timeline",
        extra=[
            f"pdf={pdf.id}",
        ],
    )


@login_required
def course_quiz_timeline_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    quiz_id,
):
    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to view quiz history.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    quiz = _get_quiz(
        chapter,
        quiz_id,
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="quiz_timeline",
        extra=[
            f"quiz={quiz.id}",
        ],
    )


# ============================================================
# LIVE WORKSPACE
# ============================================================


@login_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def course_live_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
    """
    Shared Live workspace entry point.

    The supplied old Course Builder reference does not contain
    a Live model/CRUD implementation, so this view only opens
    the existing Live workspace. Live scheduling logic should
    remain in the appropriate existing module until we connect
    its real model.
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

    auth = _authorize_builder(
        request,
        batch,
        subject,
    )

    if not auth["allowed"]:
        messages.error(
            request,
            "You do not have permission to access Live classes.",
        )
        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    return _redirect_builder(
        batch,
        subject,
        chapter=chapter,
        view="live",
    )
    
