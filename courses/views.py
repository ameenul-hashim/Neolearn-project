from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

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


# ============================================================
# COMMON ACTOR HELPERS
# ============================================================


def _get_teacher(request):
    """
    Return the Teacher profile belonging to the logged-in user.
    """

    if not request.user.is_authenticated:
        return None

    try:
        return request.user.teacher_profile
    except Teacher.DoesNotExist:
        return None


def _is_admin(request):
    """
    Admin access is based on staff/superuser status.
    """

    return bool(
        request.user.is_authenticated
        and (
            request.user.is_staff
            or request.user.is_superuser
        )
    )


def _get_actor(request):
    """
    Determine the current actor from request.user.

    No actor information comes from HTML.
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

    if teacher is not None:
        return {
            "role": "teacher",
            "admin": None,
            "teacher": teacher,
        }

    return None


def _get_actor_name(actor):
    """
    Return the display name of the current actor.
    """

    if actor["role"] == "admin":
        name = actor["admin"].get_full_name().strip()

        if name:
            return name

        return actor["admin"].get_username()

    name = actor["teacher"].full_name.strip()

    if name:
        return name

    return actor["teacher"].user.get_username()


def _get_creator_fields(actor):
    """
    Return the correct creator fields.
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


def _get_change_actor_fields(actor):
    """
    Return the correct timeline actor fields.
    """

    if actor["role"] == "admin":
        return {
            "changed_by_admin": actor["admin"],
            "changed_by_teacher": None,
        }

    return {
        "changed_by_admin": None,
        "changed_by_teacher": actor["teacher"],
    }


# ============================================================
# COMMON AUTHORIZATION
# ============================================================


def _get_teacher_assignment(
    teacher,
    batch,
    subject,
):
    """
    Verify active teacher assignment for this exact
    batch + subject.
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
    Admin:
        allowed.

    Teacher:
        allowed only when actively assigned to this
        exact batch + subject.
    """

    actor = _get_actor(request)

    if actor is None:
        return None

    if actor["role"] == "admin":
        return actor

    assignment = _get_teacher_assignment(
        actor["teacher"],
        batch,
        subject,
    )

    if assignment is None:
        return None

    actor["assignment"] = assignment

    return actor


def _get_batch_subject(
    batch_id,
    subject_id,
):
    """
    Make sure subject belongs to requested batch.
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
    Make sure chapter belongs to exact batch + subject.
    """

    return get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=batch,
        subject=subject,
    )


# ============================================================
# COMMON REDIRECT
# ============================================================


def _builder_redirect(
    batch,
    subject,
    chapter=None,
):
    """
    Central builder redirect.
    """

    if chapter is not None:
        return redirect(
            "courses:course_builder",
            batch_id=batch.id,
            subject_id=subject.id,
        )

    return redirect(
        "courses:course_builder",
        batch_id=batch.id,
        subject_id=subject.id,
    )


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
    Common Course Builder context.

    selected_content controls the right-side workspace:
        videos
        pdfs
        quizzes
        live
        timeline

    The actual content querysets are loaded for the selected chapter.
    The template decides which workspace to display.
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

    # Always select the first chapter when no chapter was
    # explicitly selected and chapters are available.
    if selected_chapter is None:
        selected_chapter = chapters.first()

    valid_views = {
        "videos",
        "pdfs",
        "quizzes",
        "live",
        "timeline",
    }

    if selected_content not in valid_views:
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
    }

    if selected_chapter is not None:

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

    else:

        context.update(
            {
                "videos": [],
                "video_count": 0,

                "pdfs": [],
                "pdf_count": 0,

                "quizzes": [],
                "quiz_count": 0,

                "next_video_order": 1,
                "next_pdf_order": 1,
                "next_quiz_order": 1,
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
# COURSE BUILDER
# ============================================================


def course_builder_view(
    request,
    batch_id,
    subject_id,
):
    """
    Main Course Builder.

    Same backend for Admin and Teacher.

    The selected chapter and selected workspace are controlled
    by the URL query string:

        ?chapter=<chapter_id>&view=videos
        ?chapter=<chapter_id>&view=pdfs
        ?chapter=<chapter_id>&view=quizzes
        ?chapter=<chapter_id>&view=live
        ?chapter=<chapter_id>&view=timeline
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

        return redirect("teacher_login")

    # --------------------------------------------------------
    # SELECTED CHAPTER
    # --------------------------------------------------------

    chapter_id = request.GET.get("chapter")

    selected_chapter = None

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

    # --------------------------------------------------------
    # SELECTED RIGHT-SIDE WORKSPACE
    # --------------------------------------------------------

    selected_content = (
        request.GET.get(
            "view",
            "videos",
        )
        or "videos"
    ).strip().lower()

    valid_views = {
        "videos",
        "pdfs",
        "quizzes",
        "live",
        "timeline",
    }

    if selected_content not in valid_views:
        selected_content = "videos"

    # --------------------------------------------------------
    # COMMON BUILDER CONTEXT
    # --------------------------------------------------------

    context = _get_builder_context(
        batch=batch,
        subject=subject,
        actor=actor,
        selected_chapter=selected_chapter,
        selected_content=selected_content,
    )

    # _get_builder_context() automatically selects the first
    # chapter when no chapter was supplied.
    selected_chapter = context["selected_chapter"]

    # --------------------------------------------------------
    # CHAPTER TIMELINE
    # --------------------------------------------------------

    timeline_type = (
        request.GET.get(
            "timeline",
            "",
        )
        .strip()
        .lower()
    )

    timeline_item = request.GET.get("item")

    context["timeline_entries"] = []
    context["video_timeline_entries"] = []
    context["pdf_timeline_entries"] = []
    context["quiz_timeline_entries"] = []

    context["selected_video"] = None
    context["selected_pdf"] = None
    context["selected_quiz"] = None

    if (
        timeline_type == "chapter"
        and selected_chapter is not None
    ):

        logs = (
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

        context["timeline_entries"] = logs

    elif (
        timeline_type == "video"
        and selected_chapter is not None
        and timeline_item
    ):

        try:
            video_id = int(timeline_item)

            selected_video = get_object_or_404(
                ChapterVideo,
                id=video_id,
                chapter=selected_chapter,
            )

            logs = (
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

            context["selected_video"] = selected_video
            context["video_timeline_entries"] = logs

        except (
            ValueError,
            TypeError,
        ):
            pass

    elif (
        timeline_type == "pdf"
        and selected_chapter is not None
        and timeline_item
    ):

        try:
            pdf_id = int(timeline_item)

            selected_pdf = get_object_or_404(
                ChapterPDF,
                id=pdf_id,
                chapter=selected_chapter,
            )

            logs = (
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

            context["selected_pdf"] = selected_pdf
            context["pdf_timeline_entries"] = logs

        except (
            ValueError,
            TypeError,
        ):
            pass

    elif (
        timeline_type == "quiz"
        and selected_chapter is not None
        and timeline_item
    ):

        try:
            quiz_id = int(timeline_item)

            selected_quiz = get_object_or_404(
                ChapterQuiz,
                id=quiz_id,
                chapter=selected_chapter,
            )

            logs = (
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

            context["selected_quiz"] = selected_quiz
            context["quiz_timeline_entries"] = logs

        except (
            ValueError,
            TypeError,
        ):
            pass

    # --------------------------------------------------------
    # TEMPLATE
    # --------------------------------------------------------

    if actor["role"] == "admin":
        template_name = (
            "admins/course_builder/admin_course_builder.html"
        )
    else:
        template_name = (
            "teachers/content_builder/course_builder.html"
        )

    return render(
        request,
        template_name,
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
    Create chapter.

    Order is automatically assigned as the next order.
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
            "You do not have permission to create a chapter.",
        )

        return redirect("teacher_login")

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

    if status not in {
        "draft",
        "published",
    }:
        errors["status"] = (
            "Please select a valid chapter status."
        )

    duplicate_exists = (
        CourseChapter.objects
        .filter(
            batch=batch,
            subject=subject,
            chapter_name__iexact=chapter_name,
        )
        .exists()
    )

    if duplicate_exists:
        errors["chapter_name"] = (
            "A chapter with this name already exists "
            "in this subject."
        )

    if errors:
        context = _get_builder_context(
            batch=batch,
            subject=subject,
            actor=actor,
        )

        context["chapter_form_errors"] = errors

        context["chapter_form_data"] = {
            "chapter_name": chapter_name,
            "chapter_description": chapter_description,
            "status": status,
        }

        context["chapter_create_open"] = True

        for error in errors.values():
            messages.error(
                request,
                error,
            )

        if actor["role"] == "admin":
            template_name = (
                "admins/course_builder/admin_course_builder.html"
            )
        else:
            template_name = (
                "teachers/content_builder/course_builder.html"
            )

        return render(
            request,
            template_name,
            context,
        )

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

        _log_chapter(
            chapter=chapter,
            actor=actor,
            action="created",
            field_name="chapter",
            old_value="",
            new_value=(
                f"Name: {chapter.chapter_name}\n"
                f"Description: {chapter.chapter_description}\n"
                f"Order: {chapter.chapter_order}\n"
                f"Status: {chapter.status}"
            ),
            summary=(
                f"Chapter created by "
                f"{_get_actor_name(actor)} "
                f"({actor['role'].title()})."
            ),
        )

    messages.success(
        request,
        "Chapter created successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
    )


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
    Edit chapter.

    IMPORTANT:
    chapter_order is part of this edit.

    If order changes, move_item() automatically adjusts
    all affected sibling chapter orders.
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
            "You do not have permission to edit this chapter.",
        )

        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

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

    raw_order = (
        request.POST.get(
            "chapter_order",
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

    if not raw_order:
        errors["chapter_order"] = (
            "Please enter the chapter order."
        )
        new_order = None
    else:
        try:
            new_order = int(raw_order)

            if new_order < 1:
                errors["chapter_order"] = (
                    "Chapter order must be greater than or equal to 1."
                )

        except (
            TypeError,
            ValueError,
        ):
            new_order = None
            errors["chapter_order"] = (
                "Chapter order must be a valid whole number."
            )

    if not status:
        errors["status"] = (
            "Please select a chapter status."
        )

    elif status not in {
        "draft",
        "published",
    }:
        errors["status"] = (
            "Please select a valid chapter status."
        )

    duplicate_exists = (
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

    if duplicate_exists:
        errors["chapter_name"] = (
            "A chapter with this name already exists "
            "in this subject."
        )

    if errors:

        for error in errors.values():
            messages.error(
                request,
                error,
            )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    changes = []

    if chapter.chapter_name != chapter_name:
        changes.append(
            (
                "chapter_name",
                chapter.chapter_name,
                chapter_name,
            )
        )

    if (
        chapter.chapter_description
        != chapter_description
    ):
        changes.append(
            (
                "chapter_description",
                chapter.chapter_description,
                chapter_description,
            )
        )

    if chapter.status != status:
        changes.append(
            (
                "status",
                chapter.status,
                status,
            )
        )

    old_order = chapter.chapter_order

    with transaction.atomic():

        queryset = CourseChapter.objects.filter(
            batch=batch,
            subject=subject,
        )

        if old_order != new_order:

            move_item(
                item=chapter,
                queryset=queryset,
                order_field="chapter_order",
                new_order=new_order,
            )

            _log_chapter(
                chapter=chapter,
                actor=actor,
                action="order_changed",
                field_name="chapter_order",
                old_value=old_order,
                new_value=new_order,
                summary=(
                    f"Chapter order changed from "
                    f"{old_order} to {new_order} by "
                    f"{_get_actor_name(actor)} "
                    f"({actor['role'].title()})."
                ),
            )

        chapter.chapter_name = chapter_name
        chapter.chapter_description = chapter_description
        chapter.status = status

        chapter.save(
            update_fields=[
                "chapter_name",
                "chapter_description",
                "status",
                "updated_at",
            ]
        )

        for (
            field_name,
            old_value,
            new_value,
        ) in changes:

            _log_chapter(
                chapter=chapter,
                actor=actor,
                action="updated",
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                summary=(
                    f"{field_name.replace('_', ' ').title()} "
                    f"updated by "
                    f"{_get_actor_name(actor)} "
                    f"({actor['role'].title()})."
                ),
            )

    messages.success(
        request,
        "Chapter updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
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
    Create video.

    video_order is automatically the next available order.
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
            "You do not have permission to create a video.",
        )

        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

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

    video_file = request.FILES.get(
        "video_file",
    )

    video_thumbnail = request.FILES.get(
        "video_thumbnail",
    )

    errors = {}

    if not video_name:
        errors["video_name"] = (
            "Please enter the video name."
        )

    elif len(video_name) > 100:
        errors["video_name"] = (
            "Video name cannot exceed 100 characters."
        )

    if not video_description:
        errors["video_description"] = (
            "Please enter the video description."
        )

    elif len(video_description) > 250:
        errors["video_description"] = (
            "Video description cannot exceed 250 characters."
        )

    if not video_file:
        errors["video_file"] = (
            "Please select a video file."
        )

    if not status:
        errors["status"] = (
            "Please select a video status."
        )

    elif status not in {
        "draft",
        "published",
    }:
        errors["status"] = (
            "Please select a valid video status."
        )

    duplicate_exists = (
        ChapterVideo.objects
        .filter(
            chapter=chapter,
            video_name__iexact=video_name,
        )
        .exists()
    )

    if duplicate_exists:
        errors["video_name"] = (
            "A video with this name already exists "
            "in this chapter."
        )

    if errors:
        for error in errors.values():
            messages.error(
                request,
                error,
            )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

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
            video_thumbnail=video_thumbnail,
            video_order=video_order,
            status=status,
            **_get_creator_fields(actor),
        )

        _log_video(
            video=video,
            actor=actor,
            action="created",
            field_name="video",
            old_value="",
            new_value=(
                f"Name: {video.video_name}\n"
                f"Description: {video.video_description}\n"
                f"Order: {video.video_order}\n"
                f"Status: {video.status}"
            ),
            summary=(
                f"Video created by "
                f"{_get_actor_name(actor)} "
                f"({actor['role'].title()})."
            ),
        )

    messages.success(
        request,
        "Video created successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
    )


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
    Edit video.

    video_order is editable here.

    move_item() handles the +1 / -1 balancing.
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
            "You do not have permission to edit this video.",
        )

        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    video = get_object_or_404(
        ChapterVideo,
        id=video_id,
        chapter=chapter,
    )

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

    raw_order = (
        request.POST.get(
            "video_order",
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

    new_video_file = request.FILES.get(
        "video_file",
    )

    new_thumbnail = request.FILES.get(
        "video_thumbnail",
    )

    errors = {}

    if not video_name:
        errors["video_name"] = (
            "Please enter the video name."
        )

    elif len(video_name) > 100:
        errors["video_name"] = (
            "Video name cannot exceed 100 characters."
        )

    if not video_description:
        errors["video_description"] = (
            "Please enter the video description."
        )

    elif len(video_description) > 250:
        errors["video_description"] = (
            "Video description cannot exceed 250 characters."
        )

    if not raw_order:
        errors["video_order"] = (
            "Please enter the video order."
        )
        new_order = None
    else:
        try:
            new_order = int(raw_order)

            if new_order < 1:
                errors["video_order"] = (
                    "Video order must be greater than or equal to 1."
                )

        except (
            TypeError,
            ValueError,
        ):
            new_order = None
            errors["video_order"] = (
                "Video order must be a valid whole number."
            )

    if not status:
        errors["status"] = (
            "Please select a video status."
        )

    elif status not in {
        "draft",
        "published",
    }:
        errors["status"] = (
            "Please select a valid video status."
        )

    duplicate_exists = (
        ChapterVideo.objects
        .filter(
            chapter=chapter,
            video_name__iexact=video_name,
        )
        .exclude(
            pk=video.pk,
        )
        .exists()
    )

    if duplicate_exists:
        errors["video_name"] = (
            "A video with this name already exists "
            "in this chapter."
        )

    if errors:

        for error in errors.values():
            messages.error(
                request,
                error,
            )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    changes = []

    if video.video_name != video_name:
        changes.append(
            (
                "video_name",
                video.video_name,
                video_name,
            )
        )

    if (
        video.video_description
        != video_description
    ):
        changes.append(
            (
                "video_description",
                video.video_description,
                video_description,
            )
        )

    if video.status != status:
        changes.append(
            (
                "status",
                video.status,
                status,
            )
        )

    if new_video_file:
        changes.append(
            (
                "video_file",
                "Existing file",
                new_video_file.name,
            )
        )

    if new_thumbnail:
        changes.append(
            (
                "video_thumbnail",
                "Existing thumbnail",
                new_thumbnail.name,
            )
        )

    old_order = video.video_order

    with transaction.atomic():

        queryset = ChapterVideo.objects.filter(
            chapter=chapter,
        )

        if old_order != new_order:

            move_item(
                item=video,
                queryset=queryset,
                order_field="video_order",
                new_order=new_order,
            )

            _log_video(
                video=video,
                actor=actor,
                action="order_changed",
                field_name="video_order",
                old_value=old_order,
                new_value=new_order,
                summary=(
                    f"Video order changed from "
                    f"{old_order} to {new_order} by "
                    f"{_get_actor_name(actor)} "
                    f"({actor['role'].title()})."
                ),
            )

        video.video_name = video_name
        video.video_description = video_description
        video.status = status

        if new_video_file:
            video.video_file = new_video_file

        if new_thumbnail:
            video.video_thumbnail = new_thumbnail

        video.save()

        for (
            field_name,
            old_value,
            new_value,
        ) in changes:

            _log_video(
                video=video,
                actor=actor,
                action="updated",
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                summary=(
                    f"{field_name.replace('_', ' ').title()} "
                    f"updated by "
                    f"{_get_actor_name(actor)} "
                    f"({actor['role'].title()})."
                ),
            )

    messages.success(
        request,
        "Video updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
    )


# ============================================================
# VIDEO ORDER
#
# Kept as a backend endpoint for compatibility.
#
# Edit already supports order.
# ============================================================


@require_POST
def change_video_order_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    video_id,
):
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
            "You do not have permission to change video order.",
        )

        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    video = get_object_or_404(
        ChapterVideo,
        id=video_id,
        chapter=chapter,
    )

    raw_order = (
        request.POST.get(
            "video_order",
            "",
        )
        .strip()
    )

    try:
        new_order = int(raw_order)
    except (
        TypeError,
        ValueError,
    ):
        messages.error(
            request,
            "Video order must be a valid whole number.",
        )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    try:

        old_order, new_order = move_item(
            item=video,
            queryset=ChapterVideo.objects.filter(
                chapter=chapter,
            ),
            order_field="video_order",
            new_order=new_order,
        )

    except ValueError as exc:

        messages.error(
            request,
            str(exc),
        )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    if old_order != new_order:

        _log_video(
            video=video,
            actor=actor,
            action="order_changed",
            field_name="video_order",
            old_value=old_order,
            new_value=new_order,
            summary=(
                f"Video order changed from "
                f"{old_order} to {new_order} by "
                f"{_get_actor_name(actor)} "
                f"({actor['role'].title()})."
            ),
        )

    messages.success(
        request,
        "Video order updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
    )


# ============================================================
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
    Create PDF.

    pdf_order automatically gets next order.
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

        return redirect("teacher_login")

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
        "pdf_file",
    )

    pdf_thumbnail = request.FILES.get(
        "pdf_thumbnail",
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

    if not status:
        errors["status"] = (
            "Please select a PDF status."
        )

    elif status not in {
        "draft",
        "published",
    }:
        errors["status"] = (
            "Please select a valid PDF status."
        )

    duplicate_exists = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            pdf_name__iexact=pdf_name,
        )
        .exists()
    )

    if duplicate_exists:
        errors["pdf_name"] = (
            "A PDF with this name already exists "
            "in this chapter."
        )

    if errors:

        for error in errors.values():
            messages.error(
                request,
                error,
            )

        return _builder_redirect(
            batch,
            subject,
            chapter,
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
            pdf_thumbnail=pdf_thumbnail,
            pdf_order=pdf_order,
            status=status,
            **_get_creator_fields(actor),
        )

        _log_pdf(
            pdf=pdf,
            actor=actor,
            action="created",
            field_name="pdf",
            old_value="",
            new_value=(
                f"Name: {pdf.pdf_name}\n"
                f"Description: {pdf.pdf_description}\n"
                f"Order: {pdf.pdf_order}\n"
                f"Status: {pdf.status}"
            ),
            summary=(
                f"PDF created by "
                f"{_get_actor_name(actor)} "
                f"({actor['role'].title()})."
            ),
        )

    messages.success(
        request,
        "PDF created successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
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
    Edit PDF.

    pdf_order is editable here.
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

        return redirect("teacher_login")

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

    raw_order = (
        request.POST.get(
            "pdf_order",
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

    new_pdf_file = request.FILES.get(
        "pdf_file",
    )

    new_thumbnail = request.FILES.get(
        "pdf_thumbnail",
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

    if not raw_order:
        errors["pdf_order"] = (
            "Please enter the PDF order."
        )
        new_order = None
    else:
        try:
            new_order = int(raw_order)

            if new_order < 1:
                errors["pdf_order"] = (
                    "PDF order must be greater than or equal to 1."
                )

        except (
            TypeError,
            ValueError,
        ):
            new_order = None
            errors["pdf_order"] = (
                "PDF order must be a valid whole number."
            )

    if not status:
        errors["status"] = (
            "Please select a PDF status."
        )

    elif status not in {
        "draft",
        "published",
    }:
        errors["status"] = (
            "Please select a valid PDF status."
        )

    duplicate_exists = (
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

    if duplicate_exists:
        errors["pdf_name"] = (
            "A PDF with this name already exists "
            "in this chapter."
        )

    if errors:

        for error in errors.values():
            messages.error(
                request,
                error,
            )

        return _builder_redirect(
            batch,
            subject,
            chapter,
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

    if new_pdf_file:
        changes.append(
            (
                "pdf_file",
                "Existing file",
                new_pdf_file.name,
            )
        )

    if new_thumbnail:
        changes.append(
            (
                "pdf_thumbnail",
                "Existing thumbnail",
                new_thumbnail.name,
            )
        )

    old_order = pdf.pdf_order

    with transaction.atomic():

        queryset = ChapterPDF.objects.filter(
            chapter=chapter,
        )

        if old_order != new_order:

            move_item(
                item=pdf,
                queryset=queryset,
                order_field="pdf_order",
                new_order=new_order,
            )

            _log_pdf(
                pdf=pdf,
                actor=actor,
                action="order_changed",
                field_name="pdf_order",
                old_value=old_order,
                new_value=new_order,
                summary=(
                    f"PDF order changed from "
                    f"{old_order} to {new_order} by "
                    f"{_get_actor_name(actor)} "
                    f"({actor['role'].title()})."
                ),
            )

        pdf.pdf_name = pdf_name
        pdf.pdf_description = pdf_description
        pdf.status = status

        if new_pdf_file:
            pdf.pdf_file = new_pdf_file

        if new_thumbnail:
            pdf.pdf_thumbnail = new_thumbnail

        pdf.save()

        for (
            field_name,
            old_value,
            new_value,
        ) in changes:

            _log_pdf(
                pdf=pdf,
                actor=actor,
                action="updated",
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                summary=(
                    f"{field_name.replace('_', ' ').title()} "
                    f"updated by "
                    f"{_get_actor_name(actor)} "
                    f"({actor['role'].title()})."
                ),
            )

    messages.success(
        request,
        "PDF updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
    )


# ============================================================
# PDF ORDER
# ============================================================


@require_POST
def change_pdf_order_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    pdf_id,
):
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
            "You do not have permission to change PDF order.",
        )

        return redirect("teacher_login")

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

    raw_order = (
        request.POST.get(
            "pdf_order",
            "",
        )
        .strip()
    )

    try:
        new_order = int(raw_order)
    except (
        TypeError,
        ValueError,
    ):
        messages.error(
            request,
            "PDF order must be a valid whole number.",
        )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    try:

        old_order, new_order = move_item(
            item=pdf,
            queryset=ChapterPDF.objects.filter(
                chapter=chapter,
            ),
            order_field="pdf_order",
            new_order=new_order,
        )

    except ValueError as exc:

        messages.error(
            request,
            str(exc),
        )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    if old_order != new_order:

        _log_pdf(
            pdf=pdf,
            actor=actor,
            action="order_changed",
            field_name="pdf_order",
            old_value=old_order,
            new_value=new_order,
            summary=(
                f"PDF order changed from "
                f"{old_order} to {new_order} by "
                f"{_get_actor_name(actor)} "
                f"({actor['role'].title()})."
            ),
        )

    messages.success(
        request,
        "PDF order updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
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
    Create quiz.

    quiz_order automatically gets next order.
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

        return redirect("teacher_login")

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

    maximum_attempts = (
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

    attempts_value = None

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

    if not maximum_attempts:

        errors["maximum_attempts"] = (
            "Please enter the maximum attempts."
        )

    else:

        try:
            attempts_value = int(
                maximum_attempts,
            )
        except (
            TypeError,
            ValueError,
        ):
            attempts_value = None
            errors["maximum_attempts"] = (
                "Maximum attempts must be a valid number."
            )

        if (
            attempts_value is not None
            and attempts_value < 1
        ):
            errors["maximum_attempts"] = (
                "Maximum attempts must be at least 1."
            )

    if not status:
        errors["status"] = (
            "Please select a quiz status."
        )

    elif status not in {
        "draft",
        "published",
    }:
        errors["status"] = (
            "Please select a valid quiz status."
        )

    duplicate_exists = (
        ChapterQuiz.objects
        .filter(
            chapter=chapter,
            quiz_name__iexact=quiz_name,
        )
        .exists()
    )

    if duplicate_exists:
        errors["quiz_name"] = (
            "A quiz with this name already exists "
            "in this chapter."
        )

    if errors:

        for error in errors.values():
            messages.error(
                request,
                error,
            )

        return _builder_redirect(
            batch,
            subject,
            chapter,
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
            maximum_attempts=attempts_value,
            status=status,
            **_get_creator_fields(actor),
        )

        _log_quiz(
            quiz=quiz,
            actor=actor,
            action="created",
            field_name="quiz",
            old_value="",
            new_value=(
                f"Name: {quiz.quiz_name}\n"
                f"Description: {quiz.quiz_description}\n"
                f"Order: {quiz.quiz_order}\n"
                f"Maximum Attempts: "
                f"{quiz.maximum_attempts}\n"
                f"Status: {quiz.status}"
            ),
            summary=(
                f"Quiz created by "
                f"{_get_actor_name(actor)} "
                f"({actor['role'].title()})."
            ),
        )

    messages.success(
        request,
        "Quiz created successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
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
    Edit quiz.

    quiz_order is part of edit.

    Changing order automatically balances all sibling quizzes.
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

        return redirect("teacher_login")

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

    maximum_attempts = (
        request.POST.get(
            "maximum_attempts",
            "",
        )
        .strip()
    )

    raw_order = (
        request.POST.get(
            "quiz_order",
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

    attempts_value = None
    new_order = None

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

    if not maximum_attempts:

        errors["maximum_attempts"] = (
            "Please enter the maximum attempts."
        )

    else:

        try:
            attempts_value = int(
                maximum_attempts,
            )
        except (
            TypeError,
            ValueError,
        ):
            attempts_value = None
            errors["maximum_attempts"] = (
                "Maximum attempts must be a valid number."
            )

        if (
            attempts_value is not None
            and attempts_value < 1
        ):
            errors["maximum_attempts"] = (
                "Maximum attempts must be at least 1."
            )

    if not raw_order:

        errors["quiz_order"] = (
            "Please enter the quiz order."
        )

    else:

        try:

            new_order = int(raw_order)

            if new_order < 1:
                errors["quiz_order"] = (
                    "Quiz order must be greater than or equal to 1."
                )

        except (
            TypeError,
            ValueError,
        ):

            new_order = None

            errors["quiz_order"] = (
                "Quiz order must be a valid whole number."
            )

    if not status:
        errors["status"] = (
            "Please select a quiz status."
        )

    elif status not in {
        "draft",
        "published",
    }:
        errors["status"] = (
            "Please select a valid quiz status."
        )

    duplicate_exists = (
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

    if duplicate_exists:
        errors["quiz_name"] = (
            "A quiz with this name already exists "
            "in this chapter."
        )

    if errors:

        for error in errors.values():
            messages.error(
                request,
                error,
            )

        return _builder_redirect(
            batch,
            subject,
            chapter,
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
        != attempts_value
    ):
        changes.append(
            (
                "maximum_attempts",
                quiz.maximum_attempts,
                attempts_value,
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

        queryset = ChapterQuiz.objects.filter(
            chapter=chapter,
        )

        if old_order != new_order:

            move_item(
                item=quiz,
                queryset=queryset,
                order_field="quiz_order",
                new_order=new_order,
            )

            _log_quiz(
                quiz=quiz,
                actor=actor,
                action="order_changed",
                field_name="quiz_order",
                old_value=old_order,
                new_value=new_order,
                summary=(
                    f"Quiz order changed from "
                    f"{old_order} to {new_order} by "
                    f"{_get_actor_name(actor)} "
                    f"({actor['role'].title()})."
                ),
            )

        quiz.quiz_name = quiz_name
        quiz.quiz_description = quiz_description
        quiz.maximum_attempts = attempts_value
        quiz.status = status

        quiz.save()

        for (
            field_name,
            old_value,
            new_value,
        ) in changes:

            _log_quiz(
                quiz=quiz,
                actor=actor,
                action="updated",
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                summary=(
                    f"{field_name.replace('_', ' ').title()} "
                    f"updated by "
                    f"{_get_actor_name(actor)} "
                    f"({actor['role'].title()})."
                ),
            )

    messages.success(
        request,
        "Quiz updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
    )


# ============================================================
# QUIZ ORDER
# ============================================================


@require_POST
def change_quiz_order_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
    quiz_id,
):
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
            "You do not have permission to change quiz order.",
        )

        return redirect("teacher_login")

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

    raw_order = (
        request.POST.get(
            "quiz_order",
            "",
        )
        .strip()
    )

    try:
        new_order = int(raw_order)
    except (
        TypeError,
        ValueError,
    ):
        messages.error(
            request,
            "Quiz order must be a valid whole number.",
        )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    try:

        old_order, new_order = move_item(
            item=quiz,
            queryset=ChapterQuiz.objects.filter(
                chapter=chapter,
            ),
            order_field="quiz_order",
            new_order=new_order,
        )

    except ValueError as exc:

        messages.error(
            request,
            str(exc),
        )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    if old_order != new_order:

        _log_quiz(
            quiz=quiz,
            actor=actor,
            action="order_changed",
            field_name="quiz_order",
            old_value=old_order,
            new_value=new_order,
            summary=(
                f"Quiz order changed from "
                f"{old_order} to {new_order} by "
                f"{_get_actor_name(actor)} "
                f"({actor['role'].title()})."
            ),
        )

    messages.success(
        request,
        "Quiz order updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
    )


# ============================================================
# CHAPTER ORDER
# ============================================================

# Kept for URL compatibility.
# Normal UI should change chapter order through Edit.


@require_POST
def change_chapter_order_view(
    request,
    batch_id,
    subject_id,
    chapter_id,
):
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
            "You do not have permission to change chapter order.",
        )

        return redirect("teacher_login")

    chapter = _get_chapter(
        batch,
        subject,
        chapter_id,
    )

    raw_order = (
        request.POST.get(
            "chapter_order",
            "",
        )
        .strip()
    )

    try:
        new_order = int(raw_order)
    except (
        TypeError,
        ValueError,
    ):
        messages.error(
            request,
            "Chapter order must be a valid whole number.",
        )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    try:

        old_order, new_order = move_item(
            item=chapter,
            queryset=CourseChapter.objects.filter(
                batch=batch,
                subject=subject,
            ),
            order_field="chapter_order",
            new_order=new_order,
        )

    except ValueError as exc:

        messages.error(
            request,
            str(exc),
        )

        return _builder_redirect(
            batch,
            subject,
            chapter,
        )

    if old_order != new_order:

        _log_chapter(
            chapter=chapter,
            actor=actor,
            action="order_changed",
            field_name="chapter_order",
            old_value=old_order,
            new_value=new_order,
            summary=(
                f"Chapter order changed from "
                f"{old_order} to {new_order} by "
                f"{_get_actor_name(actor)} "
                f"({actor['role'].title()})."
            ),
        )

    messages.success(
        request,
        "Chapter order updated successfully.",
    )

    return _builder_redirect(
        batch,
        subject,
        chapter,
    )


# ============================================================
# DELETE SNAPSHOT
# ============================================================


def _build_deletion_snapshot(
    content_type,
    obj,
):
    """
    Snapshot content before permanent deletion.
    """

    if content_type == "chapter":
        chapter = obj
    else:
        chapter = obj.chapter

    snapshot = {
        "content_type": content_type,
        "object_id": obj.pk,
        "content_name": (
            obj.chapter_name
            if content_type == "chapter"
            else obj.video_name
            if content_type == "video"
            else obj.pdf_name
            if content_type == "pdf"
            else obj.quiz_name
        ),
        "batch_name": chapter.batch.batch_name,
        "subject_name": chapter.subject.subject_name,
        "chapter_name": chapter.chapter_name,
    }

    if content_type == "chapter":

        snapshot.update(
            {
                "chapter_description": (
                    obj.chapter_description
                ),
                "chapter_order": obj.chapter_order,
                "status": obj.status,
            }
        )

    elif content_type == "video":

        snapshot.update(
            {
                "video_description": (
                    obj.video_description
                ),
                "video_order": obj.video_order,
                "status": obj.status,
            }
        )

    elif content_type == "pdf":

        snapshot.update(
            {
                "pdf_description": (
                    obj.pdf_description
                ),
                "pdf_order": obj.pdf_order,
                "status": obj.status,
            }
        )

    elif content_type == "quiz":

        snapshot.update(
            {
                "quiz_description": (
                    obj.quiz_description
                ),
                "quiz_order": obj.quiz_order,
                "maximum_attempts": (
                    obj.maximum_attempts
                ),
                "status": obj.status,
            }
        )

        questions = []

        for question in obj.questions.all():

            question_data = {
                "id": question.id,
                "question": question.question,
                "options": [],
            }

            for option in question.options.all():

                question_data["options"].append(
                    {
                        "id": option.id,
                        "option_label": option.option_label,
                        "option_text": option.option_text,
                        "is_correct": option.is_correct,
                    }
                )

            questions.append(
                question_data
            )

        snapshot["questions"] = questions

    return snapshot


def _get_original_creator(obj):
    """
    Return original creator.
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
    Create permanent deletion audit.
    """

    creator = _get_original_creator(
        obj,
    )

    chapter = (
        obj
        if content_type == "chapter"
        else obj.chapter
    )

    return DeletionAudit.objects.create(
        content_type=content_type,
        object_id=obj.pk,

        content_name=(
            obj.chapter_name
            if content_type == "chapter"
            else obj.video_name
            if content_type == "video"
            else obj.pdf_name
            if content_type == "pdf"
            else obj.quiz_name
        ),

        batch_name=chapter.batch.batch_name,
        subject_name=chapter.subject.subject_name,
        chapter_name=chapter.chapter_name,

        created_by_admin=creator["admin"],
        created_by_teacher=creator["teacher"],

        original_created_at=obj.created_at,

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
# FIND CONTENT FOR DELETE
# ============================================================


def _get_content_for_delete(
    batch,
    subject,
    content_type,
    object_id,
    chapter_id=None,
):
    """
    Safely resolve content under the requested
    batch + subject.
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
    Teacher cannot directly delete.

    Teacher creates pending DeletionAudit.
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

    if actor is None or actor["role"] != "teacher":

        messages.error(
            request,
            "Only the assigned teacher can request deletion.",
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

    chapter_id = request.POST.get(
        "chapter_id",
    )

    obj = _get_content_for_delete(
        batch=batch,
        subject=subject,
        content_type=content_type,
        object_id=object_id,
        chapter_id=chapter_id,
    )

    if obj is None:

        messages.error(
            request,
            "Invalid content type.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

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

    with transaction.atomic():

        _create_deletion_audit(
            content_type=content_type,
            obj=obj,
            status="pending",
            actor=actor,
            request_reason=reason,
        )

    messages.success(
        request,
        "Deletion request submitted successfully.",
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
    Admin can permanently delete directly.

    IMPORTANT:
    Audit is created before deletion.

    IMPORTANT:
    Order gap is closed after deletion request is recorded.
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

    if actor is None or actor["role"] != "admin":

        messages.error(
            request,
            "Only Admin can directly delete course content.",
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

    chapter_id = request.POST.get(
        "chapter_id",
    )

    obj = _get_content_for_delete(
        batch=batch,
        subject=subject,
        content_type=content_type,
        object_id=object_id,
        chapter_id=chapter_id,
    )

    if obj is None:

        messages.error(
            request,
            "Invalid content type.",
        )

        return _builder_redirect(
            batch,
            subject,
        )

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

            queryset = CourseChapter.objects.filter(
                batch=batch,
                subject=subject,
            )

            remove_item_and_close_gap(
                item=obj,
                queryset=queryset,
                order_field="chapter_order",
            )

        elif content_type == "video":

            queryset = ChapterVideo.objects.filter(
                chapter=obj.chapter,
            )

            remove_item_and_close_gap(
                item=obj,
                queryset=queryset,
                order_field="video_order",
            )

        elif content_type == "pdf":

            queryset = ChapterPDF.objects.filter(
                chapter=obj.chapter,
            )

            remove_item_and_close_gap(
                item=obj,
                queryset=queryset,
                order_field="pdf_order",
            )

        elif content_type == "quiz":

            queryset = ChapterQuiz.objects.filter(
                chapter=obj.chapter,
            )

            remove_item_and_close_gap(
                item=obj,
                queryset=queryset,
                order_field="quiz_order",
            )

        obj.delete()

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
    Read-only Admin deletion audit list.
    """

    actor = _get_actor(request)

    if actor is None or actor["role"] != "admin":

        messages.error(
            request,
            "Only Admin can view deletion audits.",
        )

        return redirect(
            "teacher_login",
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
    Read-only Admin deletion audit detail.
    """

    actor = _get_actor(request)

    if actor is None or actor["role"] != "admin":

        messages.error(
            request,
            "Only Admin can view deletion audits.",
        )

        return redirect(
            "teacher_login",
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
        },
    )


# ============================================================
# ADMIN APPROVE DELETE
# ============================================================


@require_POST
def admin_approve_delete_view(
    request,
    audit_id,
):
    """
    Approve pending Teacher deletion.

    After approval:
        1. close order gap
        2. delete content
        3. mark audit deleted
    """

    actor = _get_actor(request)

    if actor is None or actor["role"] != "admin":

        messages.error(
            request,
            "Only Admin can approve deletion requests.",
        )

        return redirect(
            "teacher_login",
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

    content_type = audit.content_type
    object_id = audit.object_id

    with transaction.atomic():

        audit.admin_decision = "approved"
        audit.decision_by_admin = actor["admin"]
        audit.decision_at = timezone.now()
        audit.admin_response = admin_response
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

        obj = None

        if content_type == "chapter":

            obj = (
                CourseChapter.objects
                .filter(
                    id=object_id,
                )
                .first()
            )

        elif content_type == "video":

            obj = (
                ChapterVideo.objects
                .filter(
                    id=object_id,
                )
                .first()
            )

        elif content_type == "pdf":

            obj = (
                ChapterPDF.objects
                .filter(
                    id=object_id,
                )
                .first()
            )

        elif content_type == "quiz":

            obj = (
                ChapterQuiz.objects
                .filter(
                    id=object_id,
                )
                .first()
            )

        if obj is not None:

            if content_type == "chapter":

                queryset = CourseChapter.objects.filter(
                    batch=obj.batch,
                    subject=obj.subject,
                )

                remove_item_and_close_gap(
                    item=obj,
                    queryset=queryset,
                    order_field="chapter_order",
                )

            elif content_type == "video":

                queryset = ChapterVideo.objects.filter(
                    chapter=obj.chapter,
                )

                remove_item_and_close_gap(
                    item=obj,
                    queryset=queryset,
                    order_field="video_order",
                )

            elif content_type == "pdf":

                queryset = ChapterPDF.objects.filter(
                    chapter=obj.chapter,
                )

                remove_item_and_close_gap(
                    item=obj,
                    queryset=queryset,
                    order_field="pdf_order",
                )

            elif content_type == "quiz":

                queryset = ChapterQuiz.objects.filter(
                    chapter=obj.chapter,
                )

                remove_item_and_close_gap(
                    item=obj,
                    queryset=queryset,
                    order_field="quiz_order",
                )

            obj.delete()

        audit.deletion_method = (
            "teacher_request_approved"
        )

        audit.status = "deleted"
        audit.deleted_at = timezone.now()

        audit.save(
            update_fields=[
                "deletion_method",
                "status",
                "deleted_at",
            ]
        )

    messages.success(
        request,
        "Deletion request approved and content deleted successfully.",
    )

    return redirect(
        "courses:admin_deletion_audit_list",
    )


# ============================================================
# ADMIN REJECT DELETE
# ============================================================


@require_POST
def admin_reject_delete_view(
    request,
    audit_id,
):
    """
    Reject pending Teacher deletion.
    """

    actor = _get_actor(request)

    if actor is None or actor["role"] != "admin":

        messages.error(
            request,
            "Only Admin can reject deletion requests.",
        )

        return redirect(
            "teacher_login",
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
            "Please enter an Admin response before rejecting the request.",
        )

        return redirect(
            "courses:admin_deletion_audit_detail",
            audit_id=audit.id,
        )

    audit.admin_decision = "rejected"
    audit.decision_by_admin = actor["admin"]
    audit.decision_at = timezone.now()
    audit.admin_response = admin_response
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
        "courses:admin_deletion_audit_list",
    )