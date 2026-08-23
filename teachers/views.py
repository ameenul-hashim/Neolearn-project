from django.urls import reverse

from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.cache import cache_control
from django.db import transaction
from django.db.models import F

import re

from admins.models import (
    Teacher,
    TeacherBatch,
    TeacherSubject,
    Batch,
    Subject,
)
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
# TEACHER LOGIN
# ============================================================

@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_login_view(request):

    if request.user.is_authenticated:

        if hasattr(request.user, "teacher_profile"):

            teacher = request.user.teacher_profile

            if teacher.is_first_login:
                return redirect("teacher_change_password")

            return redirect("teacher_dashboard")

    if request.method == "POST":

        email = request.POST.get(
            "email",
            "",
        ).strip().lower()

        password = request.POST.get(
            "password",
            "",
        )

        if not email or not password:

            messages.error(
                request,
                "All fields are required.",
            )

            return redirect("teacher_login")

        try:

            existing_user = User.objects.get(
                username=email
            )

        except User.DoesNotExist:

            messages.error(
                request,
                "Teacher account not found.",
            )

            return redirect("teacher_login")

        user = authenticate(
            request,
            username=existing_user.username,
            password=password,
        )

        if user is None:

            messages.error(
                request,
                "Incorrect password.",
            )

            return redirect("teacher_login")

        try:

            teacher = user.teacher_profile

        except Teacher.DoesNotExist:

            messages.error(
                request,
                "Teacher profile not found.",
            )

            return redirect("teacher_login")

        if teacher.is_blocked:

            messages.error(
                request,
                "Your teacher account has been blocked.",
            )

            return redirect("teacher_login")

        login(
            request,
            user,
        )

        messages.success(
            request,
            "Teacher logged in successfully.",
        )

        if teacher.is_first_login:

            return redirect(
                "teacher_change_password"
            )

        return redirect(
            "teacher_dashboard"
        )

    return render(
        request,
        "teachers/auth/teacher_login.html",
    )


# ============================================================
# TEACHER CHANGE PASSWORD
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_change_password_view(request):

    if not hasattr(
        request.user,
        "teacher_profile",
    ):

        messages.error(
            request,
            "Access denied.",
        )

        return redirect("teacher_login")

    teacher = request.user.teacher_profile
    user = request.user

    if not teacher.is_first_login:

        return redirect(
            "teacher_dashboard"
        )

    if request.method == "POST":

        password = request.POST.get(
            "password",
            "",
        )

        confirm_password = request.POST.get(
            "confirm_password",
            "",
        )

        if not password or not confirm_password:

            messages.error(
                request,
                "All fields are required.",
            )

            return redirect(
                "teacher_change_password"
            )

        if len(password) < 8:

            messages.error(
                request,
                "Password must contain at least 8 characters.",
            )

            return redirect(
                "teacher_change_password"
            )

        if not re.search(
            r"[A-Z]",
            password,
        ):

            messages.error(
                request,
                "Password must contain at least one uppercase letter.",
            )

            return redirect(
                "teacher_change_password"
            )

        if not re.search(
            r"[a-z]",
            password,
        ):

            messages.error(
                request,
                "Password must contain at least one lowercase letter.",
            )

            return redirect(
                "teacher_change_password"
            )

        if not re.search(
            r"[0-9]",
            password,
        ):

            messages.error(
                request,
                "Password must contain at least one number.",
            )

            return redirect(
                "teacher_change_password"
            )

        if not re.search(
            r"[!@#$%^&*()_+=\-[\]{};:'\"\\|,.<>/?]",
            password,
        ):

            messages.error(
                request,
                "Password must contain at least one special character.",
            )

            return redirect(
                "teacher_change_password"
            )

        if password != confirm_password:

            messages.error(
                request,
                "Passwords do not match.",
            )

            return redirect(
                "teacher_change_password"
            )

        user.set_password(password)
        user.save()

        teacher.is_first_login = False
        teacher.save()

        update_session_auth_hash(
            request,
            user,
        )

        messages.success(
            request,
            "Security setup completed successfully.",
        )

        return redirect(
            "teacher_dashboard"
        )

    return render(
        request,
        "teachers/auth/change_password.html",
    )


# ============================================================
# TEACHER DASHBOARD
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_dashboard_view(request):

    if not hasattr(
        request.user,
        "teacher_profile",
    ):

        messages.error(
            request,
            "Access denied.",
        )

        return redirect("teacher_login")

    teacher = request.user.teacher_profile

    if teacher.is_first_login:

        return redirect(
            "teacher_change_password"
        )

    response = render(
        request,
        "teachers/dashboard/dashboard.html",
        {
            "teacher": teacher,
        },
    )

    response["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )

    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response


# ============================================================
# TEACHER LOGOUT
# ============================================================

@login_required(login_url="teacher_login")
def teacher_logout_view(request):

    logout(request)

    request.session.flush()

    response = redirect(
        "teacher_login"
    )

    response.delete_cookie(
        "sessionid"
    )

    response.delete_cookie(
        "csrftoken"
    )

    messages.success(
        request,
        "Logged out successfully.",
    )

    return response


# ============================================================
# TEACHER BATCHES
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_batches_view(request):

    if not hasattr(
        request.user,
        "teacher_profile",
    ):

        messages.error(
            request,
            "Access denied.",
        )

        return redirect("teacher_login")

    teacher = request.user.teacher_profile

    assigned_batches = (
        TeacherBatch.objects
        .filter(
            teacher=teacher,
            is_active=True,
        )
        .select_related("batch")
        .order_by("batch__batch_name")
    )

    batch_cards = []

    for assignment in assigned_batches:

        batch = assignment.batch

        subject_count = (
            TeacherSubject.objects
            .filter(
                teacher=teacher,
                batch=batch,
                is_active=True,
            )
            .count()
        )

        teacher_count = (
            TeacherBatch.objects
            .filter(
                batch=batch,
                is_active=True,
            )
            .count()
        )

        batch_cards.append(
            {
                "assignment": assignment,
                "batch": batch,
                "subject_count": subject_count,
                "teacher_count": teacher_count,
            }
        )

    context = {
        "teacher": teacher,
        "batch_cards": batch_cards,
        "batch_count": len(batch_cards),
    }

    return render(
        request,
        "teachers/batches/batches.html",
        context,
    )


# ============================================================
# TEACHER SUBJECTS
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_subjects_view(
    request,
    batch_id,
):

    if not hasattr(
        request.user,
        "teacher_profile",
    ):

        messages.error(
            request,
            "Access denied.",
        )

        return redirect("teacher_login")

    teacher = request.user.teacher_profile

    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    assigned_subjects = (
        TeacherSubject.objects
        .filter(
            teacher=teacher,
            batch=batch,
            is_active=True,
        )
        .select_related(
            "subject",
            "batch",
        )
        .order_by(
            "subject__subject_name"
        )
    )

    # ========================================================
    # TEACHER COUNT FOR EACH SUBJECT
    # ========================================================

    for assignment in assigned_subjects:

        assignment.teacher_count = (
            TeacherSubject.objects
            .filter(
                subject=assignment.subject,
                is_active=True,
            )
            .count()
        )

    # ========================================================
    # TOTAL TEACHERS IN BATCH
    # ========================================================

    batch_teacher_count = (
        TeacherBatch.objects
        .filter(
            batch=batch,
            is_active=True,
        )
        .count()
    )

    context = {
        "teacher": teacher,
        "batch": batch,
        "assigned_subjects": assigned_subjects,
        "subject_count": assigned_subjects.count(),
        "batch_teacher_count": batch_teacher_count,
    }

    return render(
        request,
        "teachers/batches/subjects.html",
        context,
    )


# ============================================================
# COURSE BUILDER - COMMON ASSIGNMENT HELPER
# ============================================================

def _get_teacher_subject_assignment(
    request,
    subject_id,
):

    if not hasattr(
        request.user,
        "teacher_profile",
    ):

        return None, None

    teacher = request.user.teacher_profile

    assignment = get_object_or_404(
        TeacherSubject.objects.select_related(
            "subject",
            "batch",
        ),
        teacher=teacher,
        subject_id=subject_id,
        is_active=True,
    )

    return teacher, assignment


# ============================================================
# COURSE BUILDER
#
# RESPONSIBILITY:
# ONLY DISPLAY THE COURSE BUILDER.
#
# CHAPTER CREATION IS NOW SEPARATED INTO:
# teacher_create_chapter_view()
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_course_builder_view(
    request,
    subject_id,
):

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None:

        messages.error(
            request,
            "Access denied.",
        )

        return redirect(
            "teacher_login"
        )

    assigned_teachers = (
        TeacherSubject.objects
        .filter(
            subject=assignment.subject,
            is_active=True,
        )
        .select_related("teacher")
        .order_by("teacher__full_name")
    )

    chapters = (
        CourseChapter.objects
        .filter(
            batch=assignment.batch,
            subject=assignment.subject,
            is_deleted=False,
        )
        .order_by(
            "chapter_order",
            "id",
        )
    )

    chapter_count = chapters.count()

    # ========================================================
    # KEEP THE CURRENT CHAPTER SELECTED
    #
    # /builder/
    #     -> first chapter
    #
    # /builder/?chapter=7
    #     -> chapter 7
    # ========================================================

    selected_chapter = None

    chapter_query = (
        request.GET.get(
            "chapter",
            "",
        )
        .strip()
    )

    if chapter_query.isdigit():

        selected_chapter = (
            chapters
            .filter(
                id=int(chapter_query),
            )
            .first()
        )

    if selected_chapter is None and chapter_count > 0:

        selected_chapter = chapters.first()

    # ========================================================
    # RIGHT-SIDE WORKSPACE VIEW
    #
    # "timeline" is server-rendered through the normal builder
    # URL:
    #
    #     ?chapter=<id>&view=timeline
    #
    # No JavaScript controls this workspace.
    # ========================================================

    requested_view = (
        request.GET.get(
            "view",
            "videos",
        )
        .strip()
        .lower()
    )

    if requested_view not in {
        "videos",
        "pdfs",
        "quizzes",
        "live",
        "timeline",
        "video_timeline",
        "pdf_timeline",
        "quiz_timeline",
    }:
        requested_view = "videos"

    selected_content = requested_view

    # ========================================================
    # SELECTED VIDEO TIMELINE
    #
    # URL:
    # ?chapter=<chapter_id>&view=video_timeline&video=<video_id>
    #
    # The video must belong to the currently selected chapter.
    # This keeps every video timeline completely isolated.
    # ========================================================

    video_timeline_entries = []
    selected_video = None

    # ========================================================
    # SELECTED PDF TIMELINE
    # ========================================================

    pdf_timeline_entries = []
    selected_pdf = None

    # ========================================================
    # SELECTED QUIZ TIMELINE
    #
    # URL:
    # ?chapter=<chapter_id>&view=quiz_timeline&quiz=<quiz_id>
    # ========================================================

    quiz_timeline_entries = []
    selected_quiz = None

    quiz_query = (
        request.GET.get(
            "quiz",
            "",
        )
        or ""
    ).strip()

    quiz_mode = (
        request.GET.get(
            "quiz_mode",
            "",
        )
        or ""
    ).strip().lower()

    pdf_query = (
        request.GET.get(
            "pdf",
            "",
        )
        or ""
    ).strip()

    video_query = (
        request.GET.get(
            "video",
            "",
        )
        .strip()
    )

    # We validate the selected video after the allowed view is known.
    timeline_entries = []

    if (
        selected_chapter
        and selected_content == "video_timeline"
        and video_query.isdigit()
    ):

        selected_video = (
            ChapterVideo.objects
            .filter(
                id=int(video_query),
                chapter=selected_chapter,
                is_deleted=False,
            )
            .select_related(
                "created_by",
                "updated_by",
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
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

            for log in video_logs:

                full_name = (
                    getattr(
                        log.changed_by,
                        "full_name",
                        "",
                    )
                    or ""
                ).strip()

                first_name = (
                    full_name.split()[0]
                    if full_name
                    else "Teacher"
                )

                video_timeline_entries.append(
                    {
                        "id": log.id,
                        "actor_name": first_name,
                        "actor_full_name": full_name,
                        "action": log.get_action_display(),
                        "action_key": log.action,
                        "field_name": log.field_name,
                        "old_value": log.old_value,
                        "new_value": log.new_value,
                        "summary": log.change_summary,
                        "changed_at": log.changed_at,
                    }
                )

    if (
        selected_chapter
        and selected_content == "quiz_timeline"
        and quiz_query.isdigit()
    ):

        selected_quiz = (
            ChapterQuiz.objects
            .filter(
                id=int(quiz_query),
                chapter=selected_chapter,
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

        if selected_quiz:

            quiz_logs = (
                QuizChangeLog.objects
                .filter(
                    quiz=selected_quiz,
                )
                .select_related(
                    "changed_by",
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

            for log in quiz_logs:

                full_name = (
                    getattr(
                        log.changed_by,
                        "full_name",
                        "",
                    )
                    or ""
                ).strip()

                first_name = (
                    full_name.split()[0]
                    if full_name
                    else "Teacher"
                )

                quiz_timeline_entries.append(
                    {
                        "id": log.id,
                        "actor_name": first_name,
                        "actor_full_name": full_name,
                        "action": log.get_action_display(),
                        "action_key": log.action,
                        "field_name": log.field_name,
                        "old_value": log.old_value,
                        "new_value": log.new_value,
                        "summary": log.change_summary,
                        "changed_at": log.changed_at,
                    }
                )

    if (
        selected_chapter
        and selected_content == "pdf_timeline"
        and pdf_query.isdigit()
    ):

        selected_pdf = (
            ChapterPDF.objects
            .filter(
                id=int(pdf_query),
                chapter=selected_chapter,
            )
            .select_related(
                "created_by",
                "updated_by",
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
                )
                .order_by(
                    "-changed_at",
                    "-id",
                )
            )

            for log in pdf_logs:

                full_name = (
                    getattr(
                        log.changed_by,
                        "full_name",
                        "",
                    )
                    or ""
                ).strip()

                first_name = (
                    full_name.split()[0]
                    if full_name
                    else "Teacher"
                )

                pdf_timeline_entries.append(
                    {
                        "id": log.id,
                        "actor_name": first_name,
                        "actor_full_name": full_name,
                        "action": log.get_action_display(),
                        "action_key": log.action,
                        "field_name": log.field_name,
                        "old_value": log.old_value,
                        "new_value": log.new_value,
                        "summary": log.change_summary,
                        "changed_at": log.changed_at,
                    }
                )

    if selected_chapter and selected_content == "timeline":

        timeline_logs = (
            ChapterChangeLog.objects
            .filter(
                chapter=selected_chapter,
            )
            .select_related(
                "changed_by",
            )
            .order_by(
                "-changed_at",
                "-id",
            )
        )

        for log in timeline_logs:

            full_name = (
                getattr(
                    log.changed_by,
                    "full_name",
                    "",
                )
                or ""
            ).strip()

            first_name = (
                full_name.split()[0]
                if full_name
                else "Teacher"
            )

            timeline_entries.append(
                {
                    "id": log.id,
                    "actor_name": first_name,
                    "actor_full_name": full_name,
                    "action": log.get_action_display(),
                    "action_key": log.action,
                    "field_name": log.field_name,
                    "old_value": log.old_value,
                    "new_value": log.new_value,
                    "summary": log.change_summary,
                    "changed_at": log.changed_at,
                }
            )

    # ========================================================
    # CHAPTER EDIT POPUP STATE
    #
    # The edit view stores this in the session when validation
    # fails. We consume it here and let the template render the
    # popup directly. No JavaScript is needed to decide whether
    # the popup should be visible.
    # ========================================================

    chapter_edit_open = request.session.pop(
        "chapter_edit_open",
        False,
    )

    chapter_edit_error = request.session.pop(
        "chapter_edit_error",
        "",
    )

    chapter_edit_form = request.session.pop(
        "chapter_edit_form",
        {},
    )

    # ========================================================
    # VIDEO UPLOAD POPUP STATE
    #
    # Server-side validation failures return to the unified
    # builder and reopen the Video Upload popup.
    # ========================================================

    video_upload_open = request.session.pop(
        "video_upload_open",
        False,
    )

    video_upload_error = request.session.pop(
        "video_upload_error",
        "",
    )

    video_upload_form = request.session.pop(
        "video_upload_form",
        {},
    )

    # ========================================================
    # VIDEO EDIT POPUP STATE
    #
    # Validation failures from the Video Edit POST store these
    # values in the session. The builder consumes them and
    # re-renders the SAME selected chapter with the Edit popup
    # open.
    # ========================================================

    video_edit_open = request.session.pop(
        "video_edit_open",
        False,
    )

    video_edit_error = request.session.pop(
        "video_edit_error",
        "",
    )

    video_edit_form = request.session.pop(
        "video_edit_form",
        {},
    )

    # ========================================================
    # PDF UPLOAD POPUP STATE
    #
    # Django stores validation state in the session so the same
    # Course Builder page can reopen the PDF upload popup with
    # the entered text values and the custom error message.
    #
    # Uploaded files are never stored in session.
    # ========================================================

    pdf_upload_open = request.session.pop(
        "pdf_upload_open",
        False,
    )

    pdf_upload_error = request.session.pop(
        "pdf_upload_error",
        "",
    )

    pdf_upload_form = request.session.pop(
        "pdf_upload_form",
        {},
    )

    # ========================================================
    # PDF EDIT POPUP STATE
    # ========================================================

    pdf_edit_open = request.session.pop(
        "pdf_edit_open",
        False,
    )

    pdf_edit_error = request.session.pop(
        "pdf_edit_error",
        "",
    )

    pdf_edit_form = request.session.pop(
        "pdf_edit_form",
        {},
    )

    # ========================================================
    # QUIZ CREATE / QUESTION BUILDER POPUP STATE
    # ========================================================

    quiz_create_open = request.session.pop(
        "quiz_create_open",
        False,
    )

    quiz_create_error = request.session.pop(
        "quiz_create_error",
        "",
    )

    quiz_create_form = request.session.pop(
        "quiz_create_form",
        {},
    )

    quiz_question_open = request.session.pop(
        "quiz_question_open",
        False,
    )

    quiz_question_error = request.session.pop(
        "quiz_question_error",
        "",
    )

    quiz_question_form = request.session.pop(
        "quiz_question_form",
        {},
    )

    quiz_question_quiz_id = request.session.pop(
        "quiz_question_quiz_id",
        None,
    )

    request.session.modified = True

    # ========================================================
    # SELECTED CHAPTER VIDEOS
    # ========================================================

    if selected_chapter:

        videos = (
            ChapterVideo.objects
            .filter(
                chapter=selected_chapter,
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

    else:

        videos = ChapterVideo.objects.none()

    # ========================================================
    # SELECTED CHAPTER PDFs
    #
    # Loaded for the unified Course Builder regardless of whether
    # the current workspace is Videos or PDFs.
    # ========================================================

    if selected_chapter:

        pdfs = (
            ChapterPDF.objects
            .filter(
                chapter=selected_chapter,
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

    else:

        pdfs = ChapterPDF.objects.none()

    # ========================================================
    # SELECTED CHAPTER QUIZZES
    # ========================================================

    if selected_chapter:

        quizzes = (
            ChapterQuiz.objects
            .filter(
                chapter=selected_chapter,
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

    else:

        quizzes = ChapterQuiz.objects.none()

    context = {
        "teacher": teacher,
        "subject": assignment.subject,
        "batch": assignment.batch,
        "assignment": assignment,
        "assigned_teachers": assigned_teachers,
        "chapters": chapters,
        "chapter_count": chapter_count,
        "selected_chapter": selected_chapter,
        "selected_content": selected_content,
        "videos": videos,
        "video_count": videos.count(),

        # PDF notes.
        "pdfs": pdfs,
        "pdf_count": pdfs.count(),

        # PDF upload popup.
        "pdf_upload_open": pdf_upload_open,
        "pdf_upload_error": pdf_upload_error,
        "pdf_upload_form": pdf_upload_form,

        # PDF edit popup.
        "pdf_edit_open": pdf_edit_open,
        "pdf_edit_error": pdf_edit_error,
        "pdf_edit_form": pdf_edit_form,

        # Quiz workspace.
        "quizzes": quizzes,
        "quiz_count": quizzes.count(),

        # Selected Quiz / Quiz Timeline.
        "selected_quiz": selected_quiz,
        "quiz_timeline_entries": quiz_timeline_entries,
        "quiz_timeline_count": len(quiz_timeline_entries),

        # Quiz create / question popup state.
        "quiz_create_open": quiz_create_open,
        "quiz_create_error": quiz_create_error,
        "quiz_create_form": quiz_create_form,
        "quiz_question_open": quiz_question_open,
        "quiz_question_error": quiz_question_error,
        "quiz_question_form": quiz_question_form,
        "quiz_question_quiz_id": quiz_question_quiz_id,
        "quiz_mode": quiz_mode,

        # Chapter timeline.
        "timeline_entries": timeline_entries,
        "timeline_count": len(timeline_entries),

        # Video timeline.
        "selected_video": selected_video,
        "video_timeline_entries": video_timeline_entries,
        "video_timeline_count": len(video_timeline_entries),

        # PDF timeline.
        "selected_pdf": selected_pdf,
        "pdf_timeline_entries": pdf_timeline_entries,
        "pdf_timeline_count": len(pdf_timeline_entries),
        "chapter_creator_name": (
            selected_chapter.created_by.full_name
            if selected_chapter
            and selected_chapter.created_by
            else ""
        ),
        "chapter_creator_first_name": (
            (
                selected_chapter.created_by.full_name or ""
            ).strip().split()[0]
            if selected_chapter
            and selected_chapter.created_by
            and selected_chapter.created_by.full_name
            else "Teacher"
        ),
        "chapter_updater_name": (
            selected_chapter.updated_by.full_name
            if selected_chapter
            and selected_chapter.updated_by
            else ""
        ),
        "chapter_updater_first_name": (
            (
                selected_chapter.updated_by.full_name or ""
            ).strip().split()[0]
            if selected_chapter
            and selected_chapter.updated_by
            and selected_chapter.updated_by.full_name
            else "Teacher"
        ),

        # Chapter edit popup.
        "chapter_edit_open": chapter_edit_open,
        "chapter_edit_error": chapter_edit_error,
        "chapter_edit_form": chapter_edit_form,

        # Video upload popup.
        "video_upload_open": video_upload_open,
        "video_upload_error": video_upload_error,
        "video_upload_form": video_upload_form,

        # Video edit popup.
        "video_edit_open": video_edit_open,
        "video_edit_error": video_edit_error,
        "video_edit_form": video_edit_form,
    }

    return render(
        request,
        "teachers/content_builder/course_builder.html",
        context,
    )




# ============================================================
# CREATE CHAPTER
#
# URL:
# subjects/<subject_id>/builder/chapter/create/
#
# RESPONSIBILITY:
# - Validate every chapter-create field in this view.
# - Create the chapter.
# - Automatically assign the next chapter order.
# - Never accept manual chapter ordering from the form.
# - Return clear success/error messages through Django messages.
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_create_chapter_view(
    request,
    subject_id,
):

    # ========================================================
    # TEACHER + SUBJECT ASSIGNMENT
    # ========================================================

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    # ========================================================
    # ACCESS CHECK
    # ========================================================

    if teacher is None:

        messages.error(
            request,
            "Access denied.",
        )

        return redirect(
            "teacher_login"
        )

    # ========================================================
    # ONLY POST IS ALLOWED
    # ========================================================

    if request.method != "POST":

        messages.error(
            request,
            "Invalid chapter creation request.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    # ========================================================
    # READ FORM DATA
    # ========================================================

    chapter_name = request.POST.get(
        "chapter_name",
        "",
    ).strip()

    chapter_description = request.POST.get(
        "chapter_description",
        "",
    ).strip()

    status = request.POST.get(
        "status",
        "",
    ).strip().lower()

    # ========================================================
    # FIELD 1 — CHAPTER NAME
    # ========================================================

    if not chapter_name:

        messages.error(
            request,
            "Chapter name is required.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    if len(chapter_name) > 255:

        messages.error(
            request,
            "Chapter name cannot exceed 255 characters.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    # ========================================================
    # FIELD 2 — CHAPTER DESCRIPTION
    #
    # Description is required according to the current
    # chapter-create workflow.
    # ========================================================

    if not chapter_description:

        messages.error(
            request,
            "Chapter description is required.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    if len(chapter_description) > 255:

        messages.error(
            request,
            "Chapter description cannot exceed 255 characters.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    # ========================================================
    # FIELD 3 — STATUS
    # ========================================================

    valid_statuses = {
        choice[0]
        for choice in CourseChapter.STATUS_CHOICES
    }

    if not status:

        messages.error(
            request,
            "Chapter status is required.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    if status not in valid_statuses:

        messages.error(
            request,
            "Invalid chapter status selected.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    # ========================================================
    # DUPLICATE CHAPTER NAME CHECK
    #
    # Uniqueness is handled within the exact:
    #
    #     batch + subject
    #
    # Deleted chapters are ignored.
    # ========================================================

    duplicate_chapter = (
        CourseChapter.objects
        .filter(
            batch=assignment.batch,
            subject=assignment.subject,
            chapter_name__iexact=chapter_name,
            is_deleted=False,
        )
        .exists()
    )

    if duplicate_chapter:

        messages.error(
            request,
            "A chapter with this name already exists in this subject.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    # ========================================================
    # AUTOMATIC CHAPTER ORDER
    #
    # IMPORTANT:
    # The teacher does NOT enter chapter order anymore.
    #
    # Existing:
    #
    #     1
    #     2
    #     3
    #
    # New chapter:
    #
    #     4
    #
    # Empty subject:
    #
    #     1
    #
    # We use the highest existing active order + 1 rather
    # than chapter count + 1 so ordering remains correct even
    # if an old record has a non-contiguous number.
    # ========================================================

    last_chapter = (
        CourseChapter.objects
        .filter(
            batch=assignment.batch,
            subject=assignment.subject,
            is_deleted=False,
        )
        .order_by(
            "-chapter_order",
            "-id",
        )
        .first()
    )

    if last_chapter:

        chapter_order = (
            last_chapter.chapter_order + 1
        )

    else:

        chapter_order = 1

    # ========================================================
    # CREATE CHAPTER
    #
    # No manual order is accepted.
    # ========================================================

    try:

        with transaction.atomic():

            chapter = CourseChapter.objects.create(
                batch=assignment.batch,
                subject=assignment.subject,
                created_by=teacher,
                updated_by=teacher,
                chapter_name=chapter_name,
                chapter_description=chapter_description,
                chapter_order=chapter_order,
                status=status,
            )

            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=teacher,
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
                    f'Chapter "{chapter_name}" was created as '
                    f"Chapter {chapter_order}."
                ),
            )

    except Exception as exc:

        # Keep the error user-friendly while preserving the
        # actual exception for server-side debugging.
        print(
            "Chapter creation error:",
            exc,
        )

        messages.error(
            request,
            "The chapter could not be created. Please try again.",
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    # ========================================================
    # SUCCESS
    #
    # Display the new automatic order in the success message.
    # ========================================================

    messages.success(
        request,
        (
            f'Chapter "{chapter.chapter_name}" created successfully '
            f'as Chapter {chapter.chapter_order}.'
        ),
    )

    # ========================================================
    # OPEN THE NEWLY CREATED CHAPTER
    # ========================================================

    return redirect(
        "teacher_chapter",
        subject_id=subject_id,
        chapter_id=chapter.id,
    )

# ============================================================
# OPEN / SELECT CHAPTER
#
# URL:
# subjects/<subject_id>/builder/chapter/<chapter_id>/
#
# RESPONSIBILITY:
# SELECT A CHAPTER AND OPEN ITS DEFAULT CONTENT WORKSPACE.
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_chapter_view(
    request,
    subject_id,
    chapter_id,
):

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None:
        messages.error(
            request,
            "Access denied.",
        )
        return redirect("teacher_login")

    # ========================================================
    # SELECTED CHAPTER
    #
    # The chapter must belong to the teacher's exact:
    # batch + subject and must not be deleted.
    # ========================================================

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    # ========================================================
    # ASSIGNED TEACHERS
    # ========================================================

    assigned_teachers = (
        TeacherSubject.objects
        .filter(
            subject=assignment.subject,
            is_active=True,
        )
        .select_related("teacher")
        .order_by("teacher__full_name")
    )

    # ========================================================
    # ALL CHAPTERS
    # ========================================================

    chapters = (
        CourseChapter.objects
        .filter(
            batch=assignment.batch,
            subject=assignment.subject,
            is_deleted=False,
        )
        .order_by(
            "chapter_order",
            "id",
        )
    )

    # ========================================================
    # IMPORTANT FIX:
    # LOAD ALL VIDEOS BELONGING TO THIS SELECTED CHAPTER
    #
    # Without this, clicking a chapter correctly changes
    # selected_chapter, but the template receives no "videos"
    # variable. That is why returning to a previously uploaded
    # chapter showed "No videos added yet".
    # ========================================================

    videos = (
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

    # ========================================================
    # IMPORTANT:
    # LOAD ALL PDFs BELONGING TO THIS SELECTED CHAPTER
    #
    # This view is used when the teacher clicks a chapter name
    # in the curriculum. PDFs must be loaded here as well, or
    # returning to a chapter appears to have no PDF notes.
    # ========================================================

    pdfs = (
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

    # ========================================================
    # PDF UPLOAD POPUP STATE
    # ========================================================

    pdf_upload_open = request.session.pop(
        "pdf_upload_open",
        False,
    )

    pdf_upload_error = request.session.pop(
        "pdf_upload_error",
        "",
    )

    pdf_upload_form = request.session.pop(
        "pdf_upload_form",
        {},
    )

    request.session.modified = True

    context = {
        "teacher": teacher,
        "subject": assignment.subject,
        "batch": assignment.batch,
        "assignment": assignment,
        "assigned_teachers": assigned_teachers,
        "chapters": chapters,
        "chapter_count": chapters.count(),

        # Selected chapter.
        "selected_chapter": chapter,

        # Default right-side workspace.
        "selected_content": "videos",

        # Videos belonging ONLY to this selected chapter.
        "videos": videos,
        "video_count": videos.count(),

        # PDFs belonging ONLY to this selected chapter.
        "pdfs": pdfs,
        "pdf_count": pdfs.count(),

        # PDF upload popup state.
        "pdf_upload_open": pdf_upload_open,
        "pdf_upload_error": pdf_upload_error,
        "pdf_upload_form": pdf_upload_form,

        # Empty states expected by the unified template.
        "timeline_entries": [],
        "timeline_count": 0,
        "selected_video": None,
        "video_timeline_entries": [],
        "video_timeline_count": 0,
        "pdf_timeline_entries": [],
        "pdf_timeline_count": 0,
        "selected_pdf": None,
        "chapter_edit_open": False,
        "chapter_edit_error": "",
        "chapter_edit_form": {},
        "video_upload_open": False,
        "video_upload_error": "",
        "video_upload_form": {},
        "video_edit_open": False,
        "video_edit_error": "",
        "video_edit_form": {},
    }

    return render(
        request,
        "teachers/content_builder/course_builder.html",
        context,
    )


# ============================================================
# EDIT CHAPTER
#
# URL:
# subjects/<subject_id>/builder/chapter/<chapter_id>/edit/
#
# RESPONSIBILITY:
# EDIT CHAPTER INFORMATION.
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_edit_chapter_view(
    request,
    subject_id,
    chapter_id,
):

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None:

        messages.error(
            request,
            "Access denied.",
        )

        return redirect(
            "teacher_login"
        )

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    builder_url = reverse(
        "teacher_course_builder",
        kwargs={
            "subject_id": subject_id,
        },
    )

    # ========================================================
    # SESSION STATE FOR POPUP
    # ========================================================

    def open_edit_popup(
        error_message="",
        form_data=None,
    ):

        if form_data is None:

            form_data = {
                "chapter_id": chapter.id,
                "chapter_name": chapter.chapter_name,
                "chapter_description": (
                    chapter.chapter_description or ""
                ),
                "chapter_order": str(
                    chapter.chapter_order
                ),
                "status": chapter.status,
            }

        request.session["chapter_edit_open"] = True
        request.session["chapter_edit_error"] = error_message
        request.session["chapter_edit_form"] = form_data
        request.session.modified = True

        return redirect(
            f"{builder_url}?chapter={chapter.id}"
        )

    def close_edit_popup():

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

    # ========================================================
    # GET
    #
    # Edit is URL/template driven.
    # GET opens the same Course Builder with the popup state
    # stored in the session.
    # ========================================================

    if request.method == "GET":

        return open_edit_popup()

    # ========================================================
    # POST
    # ========================================================

    if request.method != "POST":

        return open_edit_popup(
            "Invalid chapter edit request.",
        )

    # ========================================================
    # READ FORM
    # ========================================================

    chapter_name = request.POST.get(
        "chapter_name",
        "",
    ).strip()

    chapter_description = request.POST.get(
        "chapter_description",
        "",
    ).strip()

    chapter_order_raw = request.POST.get(
        "chapter_order",
        "",
    ).strip()

    status = request.POST.get(
        "status",
        "",
    ).strip().lower()

    form_data = {
        "chapter_id": chapter.id,
        "chapter_name": chapter_name,
        "chapter_description": chapter_description,
        "chapter_order": chapter_order_raw,
        "status": status,
    }

    # ========================================================
    # NAME VALIDATION
    # ========================================================

    if not chapter_name:

        return open_edit_popup(
            "Chapter name is required.",
            form_data,
        )

    if len(chapter_name) > 255:

        return open_edit_popup(
            "Chapter name cannot exceed 255 characters.",
            form_data,
        )

    # ========================================================
    # DESCRIPTION VALIDATION
    # ========================================================

    if not chapter_description:

        return open_edit_popup(
            "Chapter description is required.",
            form_data,
        )

    if len(chapter_description) > 255:

        return open_edit_popup(
            "Chapter description cannot exceed 255 characters.",
            form_data,
        )

    # ========================================================
    # DUPLICATE NAME VALIDATION
    # ========================================================

    duplicate_chapter = (
        CourseChapter.objects
        .filter(
            batch=assignment.batch,
            subject=assignment.subject,
            chapter_name__iexact=chapter_name,
            is_deleted=False,
        )
        .exclude(
            id=chapter.id,
        )
        .exists()
    )

    if duplicate_chapter:

        return open_edit_popup(
            "Another chapter with this name already exists.",
            form_data,
        )

    # ========================================================
    # ORDER VALIDATION
    # ========================================================

    if not chapter_order_raw:

        return open_edit_popup(
            "Chapter order is required.",
            form_data,
        )

    try:

        new_order = int(
            chapter_order_raw
        )

    except (
        TypeError,
        ValueError,
    ):

        return open_edit_popup(
            "Invalid chapter order. Enter a whole number.",
            form_data,
        )

    if new_order <= 0:

        return open_edit_popup(
            "Chapter order must be greater than zero.",
            form_data,
        )

    # ========================================================
    # STATUS VALIDATION
    # ========================================================

    valid_statuses = {
        choice[0]
        for choice in CourseChapter.STATUS_CHOICES
    }

    if not status:

        return open_edit_popup(
            "Chapter status is required.",
            form_data,
        )

    if status not in valid_statuses:

        return open_edit_popup(
            "Invalid chapter status selected.",
            form_data,
        )

    # ========================================================
    # VALUES BEFORE UPDATE
    #
    # These are used for the chapter timeline.
    # ========================================================

    old_name = chapter.chapter_name
    old_description = (
        chapter.chapter_description or ""
    )
    old_order = chapter.chapter_order
    old_status = chapter.status

    # ========================================================
    # ATOMIC UPDATE + ORDER REPOSITIONING
    # ========================================================

    with transaction.atomic():

        all_chapters = list(
            CourseChapter.objects
            .select_for_update()
            .filter(
                batch=assignment.batch,
                subject=assignment.subject,
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

        if total_chapters == 0:

            return open_edit_popup(
                "No chapters are available to reorder.",
                form_data,
            )

        if new_order > total_chapters:

            return open_edit_popup(
                (
                    "Chapter order cannot be greater than "
                    f"the current number of chapters ({total_chapters})."
                ),
                form_data,
            )

        # Remove edited chapter from current order.
        ordered = [
            item
            for item in all_chapters
            if item.id != chapter.id
        ]

        # Insert at requested 1-based position.
        ordered.insert(
            new_order - 1,
            chapter,
        )

        # Temporary values avoid collisions while the final
        # contiguous sequence is written.
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
            [
                "chapter_order",
            ],
        )

        # Final order 1..N.
        for position, item in enumerate(
            ordered,
            start=1,
        ):

            item.chapter_order = position

        # Edited chapter gets its new values.
        chapter.chapter_name = chapter_name
        chapter.chapter_description = chapter_description
        chapter.chapter_order = new_order
        chapter.status = status
        chapter.updated_by = teacher

        chapter.save()

        # Save the other reordered chapters.
        other_chapters = [
            item
            for item in ordered
            if item.id != chapter.id
        ]

        if other_chapters:

            CourseChapter.objects.bulk_update(
                other_chapters,
                [
                    "chapter_order",
                ],
            )

        # ====================================================
        # TIMELINE LOGS
        #
        # Only actual changes are recorded.
        # ====================================================

        if old_name != chapter_name:

            ChapterChangeLog.objects.create(
                chapter=chapter,
                changed_by=teacher,
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
                changed_by=teacher,
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
                changed_by=teacher,
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
                changed_by=teacher,
                action="status_changed",
                field_name="status",
                old_value=old_status,
                new_value=status,
                change_summary=(
                    f"Chapter status changed from "
                    f"{old_status} to {status}."
                ),
            )

    # ========================================================
    # SUCCESS
    # ========================================================

    close_edit_popup()

    messages.success(
        request,
        f'Chapter "{chapter.chapter_name}" updated successfully.',
    )

    return redirect(
        f"{builder_url}?chapter={chapter.id}"
    )




# ============================================================
# CHAPTER DELETE REQUEST
#
# URL:
# subjects/<subject_id>/builder/chapter/<chapter_id>/
# delete-request/
#
# RESPONSIBILITY:
# TEACHER REQUESTS DELETION.
#
# ACTUAL DELETE IS NOT DONE HERE.
# ADMIN WILL HANDLE APPROVAL LATER.
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_request_chapter_delete_view(
    request,
    subject_id,
    chapter_id,
):

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None:

        messages.error(
            request,
            "Access denied.",
        )

        return redirect(
            "teacher_login"
        )

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    # ========================================================
    # DELETE REQUEST MUST BE POST
    # ========================================================

    if request.method != "POST":

        messages.error(
            request,
            "Invalid delete request.",
        )

        return redirect(
            "teacher_chapter",
            subject_id=subject_id,
            chapter_id=chapter.id,
        )

    # ========================================================
    # ALREADY PENDING
    # ========================================================

    if (
        chapter.delete_requested
        and chapter.delete_status == "pending"
    ):

        messages.info(
            request,
            "A delete request for this chapter is already pending.",
        )

        return redirect(
            "teacher_chapter",
            subject_id=subject_id,
            chapter_id=chapter.id,
        )

    # ========================================================
    # DELETE REASON
    # ========================================================

    delete_reason = request.POST.get(
        "delete_reason",
        "",
    ).strip()

    if not delete_reason:

        messages.error(
            request,
            "Please provide a reason for deleting the chapter.",
        )

        return redirect(
            "teacher_chapter",
            subject_id=subject_id,
            chapter_id=chapter.id,
        )

    # ========================================================
    # SAVE DELETE REQUEST
    # ========================================================

    from django.utils import timezone

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

    return redirect(
        "teacher_chapter",
        subject_id=subject_id,
        chapter_id=chapter.id,
    )
    
# ============================================================
# CHAPTER → VIDEO WORKSPACE
#
# URL:
# subjects/<subject_id>/builder/chapter/<chapter_id>/videos/
#
# RESPONSIBILITY:
# Open the Video workspace for the selected chapter.
#
# VIDEO CRUD / CLOUDINARY WILL BE ADDED LATER.
# ============================================================

# ============================================================
# CHAPTER → VIDEO WORKSPACE
#
# URL:
# subjects/<subject_id>/builder/chapter/<chapter_id>/videos/
#
# RESPONSIBILITY:
# - Open Video workspace
# - Upload new videos
# - Automatically assign video order
# - Support inserting a video at a requested order
# - Shift existing videos when inserting
# - Create video timeline entry
# - Display all videos of the selected chapter
# ============================================================

# ============================================================
# NORMALIZE VIDEO ORDERS
#
# Used whenever a video is actually removed/approved for deletion
# and whenever a future video-edit operation repositions videos.
#
# This guarantees:
#
#   1, 2, 3, 4
#
# never becomes:
#
#   1, 2, 4, 5
#
# ============================================================

def _normalize_video_orders(
    chapter,
):
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



def _normalize_pdf_orders(
    chapter,
):
    """
    Keep active PDF order values continuous: 1, 2, 3, ...
    Must be called inside a transaction after the chapter's
    active PDFs have been locked.
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

            old_order = pdf.pdf_order

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


@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_chapter_videos_view(
    request,
    subject_id,
    chapter_id,
):

    # ========================================================
    # TEACHER + SUBJECT ASSIGNMENT
    # ========================================================

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:

        messages.error(
            request,
            "You do not have permission to manage videos.",
        )

        return redirect("teacher_login")

    # ========================================================
    # EXACT CHAPTER
    # ========================================================

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    def redirect_to_builder():
        return redirect(
            (
                f"{reverse('teacher_course_builder', kwargs={'subject_id': subject_id})}"
                f"?chapter={chapter.id}&view=videos"
            )
        )

    # ========================================================
    # COMMON MP4 VALIDATION
    # ========================================================

    def validate_mp4(video_file):

        if not video_file:
            return False, "Please select a valid MP4 video file."

        if getattr(video_file, "size", 0) <= 0:
            return False, "The selected video file is empty."

        file_name = (
            getattr(video_file, "name", "") or ""
        ).strip().lower()

        if not file_name.endswith(".mp4"):
            return (
                False,
                "Invalid video format. Only MP4 video files are allowed.",
            )

        content_type = (
            getattr(video_file, "content_type", "") or ""
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
            return False, "The selected file is not a valid MP4 video."

        return True, ""

    # ========================================================
    # UPLOAD VALIDATION ERROR
    # ========================================================

    def upload_error(message, video_name="", video_description=""):

        request.session["video_upload_open"] = True
        request.session["video_upload_error"] = message
        request.session["video_upload_form"] = {
            "video_name": video_name,
            "video_description": video_description,
        }
        request.session.modified = True

        return redirect_to_builder()

    # ========================================================
    # EDIT VALIDATION ERROR
    # ========================================================

    def edit_error(
        message,
        video_id,
        video_name,
        video_description,
        video_order,
        current_file_name="",
    ):

        request.session["video_edit_open"] = True
        request.session["video_edit_error"] = message
        request.session["video_edit_form"] = {
            "video_id": video_id,
            "video_name": video_name,
            "video_description": video_description,
            "video_order": str(video_order),
            "current_file_name": current_file_name,
        }
        request.session.modified = True

        return redirect_to_builder()

    # ========================================================
    # POST ONLY
    # ========================================================

    if request.method != "POST":
        return redirect_to_builder()

    action = (
        request.POST.get("action", "upload") or "upload"
    ).strip().lower()

    # ========================================================
    # CREATE / UPLOAD VIDEO
    # ========================================================

    if action == "upload":

        video_name = (
            request.POST.get("video_name", "") or ""
        ).strip()

        video_description = (
            request.POST.get("video_description", "") or ""
        ).strip()

        video_file = request.FILES.get("video_file")

        # NAME
        if not video_name:
            return upload_error(
                "Video name is required.",
                video_name,
                video_description,
            )

        if len(video_name) > 255:
            return upload_error(
                "Video name cannot exceed 255 characters.",
                video_name,
                video_description,
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
                "A video with this name already exists in this chapter.",
                video_name,
                video_description,
            )

        # DESCRIPTION
        if not video_description:
            return upload_error(
                "Video description is required.",
                video_name,
                video_description,
            )

        if len(video_description) > 5000:
            return upload_error(
                "Video description cannot exceed 5000 characters.",
                video_name,
                video_description,
            )

        # FILE
        valid_file, file_error = validate_mp4(video_file)

        if not valid_file:
            return upload_error(
                file_error,
                video_name,
                video_description,
            )

        try:

            with transaction.atomic():

                last_video = (
                    ChapterVideo.objects
                    .select_for_update()
                    .filter(
                        chapter=chapter,
                        is_deleted=False,
                    )
                    .order_by("-video_order", "-id")
                    .first()
                )

                video_order = (
                    last_video.video_order + 1
                    if last_video
                    else 1
                )

                video = ChapterVideo.objects.create(
                    chapter=chapter,
                    video_name=video_name,
                    video_description=video_description,
                    video_file=video_file,
                    video_order=video_order,
                    created_by=teacher,
                    updated_by=teacher,
                    delete_requested=False,
                    delete_status="pending",
                    is_deleted=False,
                )

                VideoChangeLog.objects.create(
                    video=video,
                    changed_by=teacher,
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
                        f'Video "{video.video_name}" was created '
                        f"at order {video.video_order}."
                    ),
                )

        except Exception as exc:

            print("Video upload error:", exc)

            return upload_error(
                "The video could not be uploaded. Please try again.",
                video_name,
                video_description,
            )

        # Clear only upload error state.
        request.session.pop("video_upload_open", None)
        request.session.pop("video_upload_error", None)
        request.session.pop("video_upload_form", None)
        request.session.modified = True

        messages.success(
            request,
            f'Video "{video.video_name}" uploaded successfully.',
        )

        return redirect_to_builder()

    # ========================================================
    # EDIT EXISTING VIDEO
    # ========================================================

    if action == "edit":

        raw_video_id = (
            request.POST.get("video_id", "") or ""
        ).strip()

        if not raw_video_id.isdigit():

            request.session["video_edit_open"] = True
            request.session["video_edit_error"] = (
                "The selected video is invalid."
            )
            request.session["video_edit_form"] = {}
            request.session.modified = True

            return redirect_to_builder()

        video = get_object_or_404(
            ChapterVideo,
            id=int(raw_video_id),
            chapter=chapter,
            is_deleted=False,
        )

        old_name = video.video_name or ""
        old_description = video.video_description or ""
        old_order = video.video_order
        old_file_name = getattr(video.video_file, "name", "") or ""

        new_name = (
            request.POST.get("video_name", "") or ""
        ).strip()

        new_description = (
            request.POST.get("video_description", "") or ""
        ).strip()

        order_raw = (
            request.POST.get("video_order", "") or ""
        ).strip()

        replacement_file = request.FILES.get("video_file")

        # ----------------------------------------------------
        # NAME REQUIRED
        # ----------------------------------------------------

        if not new_name:

            return edit_error(
                "Video name is required.",
                video.id,
                new_name,
                new_description,
                order_raw or old_order,
                old_file_name,
            )

        if len(new_name) > 255:

            return edit_error(
                "Video name cannot exceed 255 characters.",
                video.id,
                new_name,
                new_description,
                order_raw or old_order,
                old_file_name,
            )

        # ----------------------------------------------------
        # DUPLICATE NAME — EXCLUDE CURRENT VIDEO
        # ----------------------------------------------------

        duplicate = (
            ChapterVideo.objects
            .filter(
                chapter=chapter,
                video_name__iexact=new_name,
                is_deleted=False,
            )
            .exclude(id=video.id)
            .exists()
        )

        if duplicate:

            return edit_error(
                "A video with this name already exists in this chapter.",
                video.id,
                new_name,
                new_description,
                order_raw or old_order,
                old_file_name,
            )

        # ----------------------------------------------------
        # DESCRIPTION REQUIRED
        # ----------------------------------------------------

        if not new_description:

            return edit_error(
                "Video description is required.",
                video.id,
                new_name,
                new_description,
                order_raw or old_order,
                old_file_name,
            )

        if len(new_description) > 5000:

            return edit_error(
                "Video description cannot exceed 5000 characters.",
                video.id,
                new_name,
                new_description,
                order_raw or old_order,
                old_file_name,
            )

        # ----------------------------------------------------
        # ORDER REQUIRED + >= 1
        # ----------------------------------------------------

        if not order_raw:

            return edit_error(
                "Video order is required.",
                video.id,
                new_name,
                new_description,
                order_raw,
                old_file_name,
            )

        try:
            new_order = int(order_raw)
        except (TypeError, ValueError):

            return edit_error(
                "Video order must be a valid number.",
                video.id,
                new_name,
                new_description,
                order_raw,
                old_file_name,
            )

        if new_order <= 0:

            return edit_error(
                "Video order must be greater than zero.",
                video.id,
                new_name,
                new_description,
                new_order,
                old_file_name,
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
                f"Video order must be between 1 and {current_count}.",
                video.id,
                new_name,
                new_description,
                new_order,
                old_file_name,
            )

        # ----------------------------------------------------
        # OPTIONAL FILE REPLACEMENT
        # ----------------------------------------------------

        if replacement_file:

            valid_file, file_error = validate_mp4(
                replacement_file,
            )

            if not valid_file:

                return edit_error(
                    file_error,
                    video.id,
                    new_name,
                    new_description,
                    new_order,
                    old_file_name,
                )

        # ----------------------------------------------------
        # SAVE / REORDER / LOG
        # ----------------------------------------------------

        try:

            with transaction.atomic():

                # Lock active videos in this chapter.
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

                locked_count = len(locked_videos)

                if new_order > locked_count:

                    return edit_error(
                        (
                            f"Video order must be between "
                            f"1 and {locked_count}."
                        ),
                        video.id,
                        new_name,
                        new_description,
                        new_order,
                        old_file_name,
                    )

                # Find current persisted order after locking.
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
                        "The selected video no longer exists.",
                        video.id,
                        new_name,
                        new_description,
                        new_order,
                        old_file_name,
                    )

                old_order = locked_video.video_order

                # Move down: 2 -> 5
                # 3,4,5 shift to 2,3,4
                if new_order > old_order:

                    ChapterVideo.objects.filter(
                        chapter=chapter,
                        is_deleted=False,
                        video_order__gt=old_order,
                        video_order__lte=new_order,
                    ).update(
                        video_order=F("video_order") - 1
                    )

                # Move up: 5 -> 2
                # 2,3,4 shift to 3,4,5
                elif new_order < old_order:

                    ChapterVideo.objects.filter(
                        chapter=chapter,
                        is_deleted=False,
                        video_order__gte=new_order,
                        video_order__lt=old_order,
                    ).update(
                        video_order=F("video_order") + 1
                    )

                video.video_name = new_name
                video.video_description = new_description
                video.video_order = new_order
                video.updated_by = teacher

                if replacement_file:
                    video.video_file = replacement_file

                video.save()

                # NAME
                if old_name != new_name:

                    VideoChangeLog.objects.create(
                        video=video,
                        changed_by=teacher,
                        action="name_changed",
                        field_name="video_name",
                        old_value=old_name,
                        new_value=new_name,
                        change_summary="Video name was updated.",
                    )

                # DESCRIPTION
                if old_description != new_description:

                    VideoChangeLog.objects.create(
                        video=video,
                        changed_by=teacher,
                        action="description_changed",
                        field_name="video_description",
                        old_value=old_description,
                        new_value=new_description,
                        change_summary="Video description was updated.",
                    )

                # ORDER
                if old_order != new_order:

                    VideoChangeLog.objects.create(
                        video=video,
                        changed_by=teacher,
                        action="order_changed",
                        field_name="video_order",
                        old_value=str(old_order),
                        new_value=str(new_order),
                        change_summary=(
                            f"Video order changed from "
                            f"{old_order} to {new_order}."
                        ),
                    )

                # FILE
                if replacement_file:

                    VideoChangeLog.objects.create(
                        video=video,
                        changed_by=teacher,
                        action="file_changed",
                        field_name="video_file",
                        old_value=old_file_name or "Previous MP4 file",
                        new_value=(
                            getattr(
                                replacement_file,
                                "name",
                                "",
                            )
                            or "New MP4 file"
                        ),
                        change_summary="Video file was replaced.",
                    )

                # Always normalize after a reorder.
                _normalize_video_orders(chapter)

        except Exception as exc:

            print("Video edit error:", exc)

            return edit_error(
                "The video could not be updated. Please try again.",
                video.id,
                new_name,
                new_description,
                new_order,
                old_file_name,
            )

        # Clear edit state only.
        request.session.pop("video_edit_open", None)
        request.session.pop("video_edit_error", None)
        request.session.pop("video_edit_form", None)
        request.session.modified = True

        messages.success(
            request,
            f'Video "{video.video_name}" updated successfully.',
        )

        return redirect_to_builder()

    # ========================================================
    # UNKNOWN ACTION
    # ========================================================

    messages.error(
        request,
        "Invalid video action.",
    )

    return redirect_to_builder()



# ============================================================
# CHAPTER → PDF WORKSPACE
#
# URL:
# subjects/<subject_id>/builder/chapter/<chapter_id>/pdfs/
#
# RESPONSIBILITY:
# Open the PDF workspace for the selected chapter.
#
# PDF CRUD WILL BE ADDED LATER.
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_chapter_pdfs_view(
    request,
    subject_id,
    chapter_id,
):
    """
    Handle PDF Notes workspace and PDF upload for one exact chapter.

    Current stage:
        - Open PDF workspace
        - Upload PDF
        - Server-side field validation
        - PDF-only file validation
        - Optional thumbnail validation
        - Automatic PDF order
        - PDFChangeLog creation
        - Popup validation state through Django session

    PDF edit / reorder / delete request / PDF timeline are added
    in later stages and are intentionally not handled here yet.
    """

    # ========================================================
    # TEACHER + SUBJECT ASSIGNMENT
    # ========================================================

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:

        messages.error(
            request,
            "You do not have permission to manage PDF notes.",
        )

        return redirect(
            "teacher_login"
        )

    # ========================================================
    # EXACT CHAPTER
    #
    # This prevents a teacher from posting a PDF into a chapter
    # outside the teacher's assigned batch + subject.
    # ========================================================

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    # ========================================================
    # RETURN TO SAME CHAPTER → PDF WORKSPACE
    # ========================================================

    def redirect_to_builder():
        return redirect(
            (
                f"{reverse('teacher_course_builder', kwargs={'subject_id': subject_id})}"
                f"?chapter={chapter.id}&view=pdfs"
            )
        )

    # ========================================================
    # OPEN PDF UPLOAD POPUP AFTER VALIDATION FAILURE
    # ========================================================

    def validation_error(
        message,
        pdf_name="",
        pdf_description="",
    ):

        request.session["pdf_upload_open"] = True

        request.session["pdf_upload_error"] = message

        request.session["pdf_upload_form"] = {
            "pdf_name": pdf_name,
            "pdf_description": pdf_description,
        }

        request.session.modified = True

        return redirect_to_builder()

    # ========================================================
    # GET
    #
    # A direct GET opens the selected chapter's PDF workspace.
    # Upload is POST-only.
    # ========================================================

    if request.method == "GET":
        return redirect_to_builder()

    # ========================================================
    # ONLY POST CAN CREATE A PDF
    # ========================================================

    if request.method != "POST":

        return validation_error(
            "Invalid PDF upload request.",
        )

    # ========================================================
    # READ TEXT FIELDS
    # ========================================================

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
        "pdf_file",
    )

    pdf_thumbnail = request.FILES.get(
        "pdf_thumbnail",
    )

    # ========================================================
    # FIELD 1 — PDF NAME
    # ========================================================

    if not pdf_name:

        return validation_error(
            "PDF notes name is required.",
            pdf_name,
            pdf_description,
        )

    if len(pdf_name) > 255:

        return validation_error(
            "PDF notes name cannot exceed 255 characters.",
            pdf_name,
            pdf_description,
        )

    # ========================================================
    # DUPLICATE PDF NAME
    #
    # Unique within the exact chapter.
    # Case-insensitive and ignores soft-deleted PDFs.
    # ========================================================

    duplicate_pdf = (
        ChapterPDF.objects
        .filter(
            chapter=chapter,
            pdf_name__iexact=pdf_name,
            is_deleted=False,
        )
        .exists()
    )

    if duplicate_pdf:

        return validation_error(
            "A PDF with this name already exists in this chapter.",
            pdf_name,
            pdf_description,
        )

    # ========================================================
    # FIELD 2 — DESCRIPTION
    # ========================================================

    if not pdf_description:

        return validation_error(
            "PDF notes description is required.",
            pdf_name,
            pdf_description,
        )

    if len(pdf_description) > 5000:

        return validation_error(
            "PDF notes description cannot exceed 5000 characters.",
            pdf_name,
            pdf_description,
        )

    # ========================================================
    # FIELD 3 — PDF FILE
    #
    # Backend rule:
    #     extension must be .pdf
    #
    # We deliberately do not trust the browser's accept="..."
    # attribute as validation.
    # ========================================================

    if not pdf_file:

        return validation_error(
            "Please select a PDF file.",
            pdf_name,
            pdf_description,
        )

    if getattr(pdf_file, "size", 0) <= 0:

        return validation_error(
            "The selected PDF file is empty.",
            pdf_name,
            pdf_description,
        )

    pdf_original_name = (
        getattr(
            pdf_file,
            "name",
            "",
        )
        or ""
    ).strip()

    if not pdf_original_name.lower().endswith(".pdf"):

        return validation_error(
            "Invalid file format. Only PDF files are allowed.",
            pdf_name,
            pdf_description,
        )

    # Browser MIME can be missing or unreliable, so use it only
    # to reject obvious non-PDF values. Extension remains the
    # required backend rule.
    pdf_content_type = (
        getattr(
            pdf_file,
            "content_type",
            "",
        )
        or ""
    ).strip().lower()

    rejected_pdf_types = {
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

    if pdf_content_type in rejected_pdf_types:

        return validation_error(
            "The selected file is not a valid PDF document.",
            pdf_name,
            pdf_description,
        )

    # ========================================================
    # FIELD 4 — OPTIONAL THUMBNAIL
    #
    # Allowed:
    #     PNG
    #     JPG
    #     JPEG
    #     WEBP
    #
    # The model stores it in Cloudinary as an image.
    # ========================================================

    if pdf_thumbnail:

        thumbnail_name = (
            getattr(
                pdf_thumbnail,
                "name",
                "",
            )
            or ""
        ).strip().lower()

        thumbnail_extension = ""

        if "." in thumbnail_name:

            thumbnail_extension = (
                "."
                + thumbnail_name.rsplit(
                    ".",
                    1,
                )[1]
            )

        allowed_thumbnail_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }

        if thumbnail_extension not in allowed_thumbnail_extensions:

            return validation_error(
                (
                    "Invalid thumbnail format. Only PNG, JPG, "
                    "JPEG, and WEBP images are allowed."
                ),
                pdf_name,
                pdf_description,
            )

        if getattr(pdf_thumbnail, "size", 0) <= 0:

            return validation_error(
                "The selected thumbnail image is empty.",
                pdf_name,
                pdf_description,
            )

        thumbnail_content_type = (
            getattr(
                pdf_thumbnail,
                "content_type",
                "",
            )
            or ""
        ).strip().lower()

        allowed_thumbnail_types = {
            "image/png",
            "image/jpeg",
            "image/webp",
        }

        if (
            thumbnail_content_type
            and thumbnail_content_type not in allowed_thumbnail_types
        ):

            return validation_error(
                (
                    "The selected thumbnail is not a valid image. "
                    "Use PNG, JPG, JPEG, or WEBP."
                ),
                pdf_name,
                pdf_description,
            )

    # ========================================================
    # AUTOMATIC ORDER + CREATE
    #
    # New PDFs always go after the current last active PDF.
    #
    # 1, 2, 3
    # new PDF -> 4
    #
    # Reordering is deliberately reserved for PDF Edit.
    # ========================================================

    try:

        with transaction.atomic():

            last_pdf = (
                ChapterPDF.objects
                .select_for_update()
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

            pdf_order = (
                last_pdf.pdf_order + 1
                if last_pdf
                else 1
            )

            pdf = ChapterPDF.objects.create(
                chapter=chapter,
                pdf_name=pdf_name,
                pdf_description=pdf_description,
                pdf_file=pdf_file,
                pdf_thumbnail=pdf_thumbnail,
                pdf_order=pdf_order,
                created_by=teacher,
                updated_by=teacher,
                delete_requested=False,
                delete_requested_by=None,
                delete_requested_at=None,
                delete_reason="",
                delete_status="pending",
                is_deleted=False,
            )

            # ====================================================
            # PDF TIMELINE — CREATED
            #
            # The later PDF Timeline will read this record and
            # display teacher + time + field values.
            # ====================================================

            thumbnail_label = (
                getattr(
                    pdf_thumbnail,
                    "name",
                    "",
                )
                or "Default NeoLearner branding thumbnail"
            )

            PDFChangeLog.objects.create(
                pdf=pdf,
                changed_by=teacher,
                action="created",
                field_name="pdf",
                old_value="",
                new_value=(
                    f"Name: {pdf.pdf_name}; "
                    f"Description: {pdf.pdf_description}; "
                    f"Order: {pdf.pdf_order}; "
                    f"File: {pdf_original_name}; "
                    f"Thumbnail: {thumbnail_label}"
                ),
                change_summary=(
                    f'PDF "{pdf.pdf_name}" was created at '
                    f"order {pdf.pdf_order}."
                ),
            )

    except Exception as exc:

        # Keep the user-facing message clean and preserve the
        # actual exception in the Django server console.
        print(
            "PDF upload error:",
            exc,
        )

        return validation_error(
            "The PDF could not be uploaded. Please try again.",
            pdf_name,
            pdf_description,
        )

    # ========================================================
    # SUCCESS — CLEAR PDF POPUP STATE ONLY
    # ========================================================

    request.session.pop(
        "pdf_upload_open",
        None,
    )

    request.session.pop(
        "pdf_upload_error",
        None,
    )

    request.session.pop(
        "pdf_upload_form",
        None,
    )

    request.session.modified = True

    # ========================================================
    # SUCCESS MESSAGE
    # ========================================================

    messages.success(
        request,
        (
            f'PDF "{pdf.pdf_name}" uploaded successfully '
            f"as PDF {pdf.pdf_order}."
        ),
    )

    # ========================================================
    # RETURN TO SAME CHAPTER → PDF WORKSPACE
    # ========================================================

    return redirect_to_builder()





# ============================================================
# PDF TIMELINE
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_pdf_timeline_view(
    request,
    subject_id,
    chapter_id,
    pdf_id,
):
    """
    Validate the teacher/chapter/pdf relationship, then open the
    PDF timeline inside the unified Course Builder.
    """

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:

        messages.error(
            request,
            "You do not have permission to view PDF history.",
        )

        return redirect("teacher_login")

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    pdf = get_object_or_404(
        ChapterPDF,
        id=pdf_id,
        chapter=chapter,
    )

    return redirect(
        (
            f"{reverse('teacher_course_builder', kwargs={'subject_id': subject_id})}"
            f"?chapter={chapter.id}&view=pdf_timeline&pdf={pdf.id}"
        )
    )


# ============================================================
# PDF EDIT
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_edit_pdf_view(
    request,
    subject_id,
    chapter_id,
    pdf_id,
):
    """
    PDF Edit workflow.

    GET:
        opens the Edit PDF popup inside the existing Course Builder.

    POST:
        validates all fields, optionally replaces the PDF file/
        thumbnail, changes the PDF order, updates the teacher who
        edited it, and writes PDFChangeLog records.
    """

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:

        messages.error(
            request,
            "You do not have permission to edit PDF notes.",
        )

        return redirect("teacher_login")

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    pdf = get_object_or_404(
        ChapterPDF,
        id=pdf_id,
        chapter=chapter,
        is_deleted=False,
    )

    def redirect_to_builder():

        return redirect(
            (
                f"{reverse('teacher_course_builder', kwargs={'subject_id': subject_id})}"
                f"?chapter={chapter.id}&view=pdfs"
            )
        )

    def current_thumbnail_url():

        if not pdf.pdf_thumbnail:
            return ""

        try:
            return pdf.pdf_thumbnail.url
        except Exception:
            return ""

    def save_edit_state(
        message,
        name,
        description,
        order_value,
    ):

        request.session["pdf_edit_open"] = True

        request.session["pdf_edit_error"] = message

        request.session["pdf_edit_form"] = {
            "pdf_id": pdf.id,
            "pdf_name": name,
            "pdf_description": description,
            "pdf_order": str(order_value),
            "current_file_name": (
                getattr(
                    pdf.pdf_file,
                    "name",
                    "",
                )
                or ""
            ),
            "current_thumbnail_url": (
                current_thumbnail_url()
            ),
        }

        request.session.modified = True

        return redirect_to_builder()

    # ========================================================
    # GET -> OPEN POPUP
    # ========================================================

    if request.method == "GET":

        request.session["pdf_edit_open"] = True

        request.session["pdf_edit_error"] = ""

        request.session["pdf_edit_form"] = {
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
                current_thumbnail_url()
            ),
        }

        request.session.modified = True

        return redirect_to_builder()

    # ========================================================
    # POST ONLY
    # ========================================================

    if request.method != "POST":

        messages.error(
            request,
            "Invalid PDF edit request.",
        )

        return redirect_to_builder()

    # ========================================================
    # FORM DATA
    # ========================================================

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

        old_thumbnail_name = (
            str(
                getattr(
                    pdf.pdf_thumbnail,
                    "name",
                    "",
                )
                or ""
            )
        )

    # ========================================================
    # NAME
    # ========================================================

    if not new_name:

        return save_edit_state(
            "PDF notes name is required.",
            new_name,
            new_description,
            order_raw or old_order,
        )

    if len(new_name) > 255:

        return save_edit_state(
            "PDF notes name cannot exceed 255 characters.",
            new_name,
            new_description,
            order_raw or old_order,
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

        return save_edit_state(
            "A PDF with this name already exists in this chapter.",
            new_name,
            new_description,
            order_raw or old_order,
        )

    # ========================================================
    # DESCRIPTION
    # ========================================================

    if not new_description:

        return save_edit_state(
            "PDF notes description is required.",
            new_name,
            new_description,
            order_raw or old_order,
        )

    if len(new_description) > 5000:

        return save_edit_state(
            "PDF notes description cannot exceed 5000 characters.",
            new_name,
            new_description,
            order_raw or old_order,
        )

    # ========================================================
    # ORDER
    # ========================================================

    if not order_raw:

        return save_edit_state(
            "PDF order is required.",
            new_name,
            new_description,
            order_raw,
        )

    try:

        new_order = int(
            order_raw
        )

    except (
        TypeError,
        ValueError,
    ):

        return save_edit_state(
            "PDF order must be a valid number.",
            new_name,
            new_description,
            order_raw,
        )

    if new_order <= 0:

        return save_edit_state(
            "PDF order must be greater than zero.",
            new_name,
            new_description,
            new_order,
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

        return save_edit_state(
            (
                f"PDF order must be between "
                f"1 and {current_count}."
            ),
            new_name,
            new_description,
            new_order,
        )

    # ========================================================
    # OPTIONAL PDF REPLACEMENT
    # ========================================================

    if replacement_file:

        replacement_name = (
            getattr(
                replacement_file,
                "name",
                "",
            )
            or ""
        ).strip()

        if getattr(
            replacement_file,
            "size",
            0,
        ) <= 0:

            return save_edit_state(
                "The replacement PDF file is empty.",
                new_name,
                new_description,
                new_order,
            )

        if not replacement_name.lower().endswith(
            ".pdf"
        ):

            return save_edit_state(
                "Invalid file format. Only PDF files are allowed.",
                new_name,
                new_description,
                new_order,
            )

        replacement_type = (
            getattr(
                replacement_file,
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

        if replacement_type in rejected_types:

            return save_edit_state(
                "The replacement file is not a valid PDF document.",
                new_name,
                new_description,
                new_order,
            )

    # ========================================================
    # OPTIONAL THUMBNAIL REPLACEMENT
    # ========================================================

    if replacement_thumbnail:

        thumbnail_name = (
            getattr(
                replacement_thumbnail,
                "name",
                "",
            )
            or ""
        ).strip().lower()

        extension = ""

        if "." in thumbnail_name:

            extension = (
                "."
                + thumbnail_name.rsplit(
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

            return save_edit_state(
                (
                    "Invalid thumbnail format. Only PNG, JPG, "
                    "JPEG, and WEBP images are allowed."
                ),
                new_name,
                new_description,
                new_order,
            )

        if getattr(
            replacement_thumbnail,
            "size",
            0,
        ) <= 0:

            return save_edit_state(
                "The replacement thumbnail image is empty.",
                new_name,
                new_description,
                new_order,
            )

        thumbnail_type = (
            getattr(
                replacement_thumbnail,
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
            thumbnail_type
            and thumbnail_type not in allowed_types
        ):

            return save_edit_state(
                (
                    "The replacement thumbnail is not a valid image. "
                    "Use PNG, JPG, JPEG, or WEBP."
                ),
                new_name,
                new_description,
                new_order,
            )

    # ========================================================
    # TRANSACTION
    # ========================================================

    try:

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

                return save_edit_state(
                    "The selected PDF no longer exists.",
                    new_name,
                    new_description,
                    new_order,
                )

            if new_order > len(locked_pdfs):

                return save_edit_state(
                    (
                        f"PDF order must be between "
                        f"1 and {len(locked_pdfs)}."
                    ),
                    new_name,
                    new_description,
                    new_order,
                )

            original_orders = {
                item.id: item.pdf_order
                for item in locked_pdfs
            }

            # Build final ordered list and insert the edited PDF.
            reordered_ids = [
                item.id
                for item in locked_pdfs
                if item.id != locked_pdf.id
            ]

            reordered_ids.insert(
                new_order - 1,
                locked_pdf.id,
            )

            # Assign the final continuous order.
            pdf_by_id = {
                item.id: item
                for item in locked_pdfs
            }

            for index, pdf_id_value in enumerate(
                reordered_ids,
                start=1,
            ):

                pdf_by_id[
                    pdf_id_value
                ].pdf_order = index

            # Update edited PDF fields.
            locked_pdf.pdf_name = new_name

            locked_pdf.pdf_description = (
                new_description
            )

            locked_pdf.updated_by = teacher

            if replacement_file:
                locked_pdf.pdf_file = replacement_file

            if replacement_thumbnail:
                locked_pdf.pdf_thumbnail = (
                    replacement_thumbnail
                )

            # Save everything that changed.
            for target in locked_pdfs:

                original_order = original_orders[
                    target.id
                ]

                order_changed = (
                    original_order
                    != target.pdf_order
                )

                if target.id == locked_pdf.id:

                    target.save()

                elif order_changed:

                    target.updated_by = teacher

                    target.save(
                        update_fields=[
                            "pdf_order",
                            "updated_by",
                            "updated_at",
                        ]
                    )

            # NAME
            if old_name != new_name:

                PDFChangeLog.objects.create(
                    pdf=locked_pdf,
                    changed_by=teacher,
                    action="name_changed",
                    field_name="pdf_name",
                    old_value=old_name,
                    new_value=new_name,
                    change_summary=(
                        "PDF notes name was updated."
                    ),
                )

            # DESCRIPTION
            if old_description != new_description:

                PDFChangeLog.objects.create(
                    pdf=locked_pdf,
                    changed_by=teacher,
                    action="description_changed",
                    field_name="pdf_description",
                    old_value=old_description,
                    new_value=new_description,
                    change_summary=(
                        "PDF notes description was updated."
                    ),
                )

            # ORDER
            for target in locked_pdfs:

                original_order = original_orders[
                    target.id
                ]

                if (
                    original_order
                    != target.pdf_order
                ):

                    PDFChangeLog.objects.create(
                        pdf=target,
                        changed_by=teacher,
                        action="order_changed",
                        field_name="pdf_order",
                        old_value=str(
                            original_order
                        ),
                        new_value=str(
                            target.pdf_order
                        ),
                        change_summary=(
                            f'PDF "{target.pdf_name}" order '
                            f"changed from {original_order} "
                            f"to {target.pdf_order}."
                        ),
                    )

            # FILE
            if replacement_file:

                PDFChangeLog.objects.create(
                    pdf=locked_pdf,
                    changed_by=teacher,
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

            # THUMBNAIL
            if replacement_thumbnail:

                PDFChangeLog.objects.create(
                    pdf=locked_pdf,
                    changed_by=teacher,
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

    except Exception as exc:

        print(
            "PDF edit error:",
            exc,
        )

        return save_edit_state(
            "The PDF could not be updated. Please try again.",
            new_name,
            new_description,
            new_order,
        )

    # Clear edit state.
    request.session.pop("pdf_edit_open", None)
    request.session.pop("pdf_edit_error", None)
    request.session.pop("pdf_edit_form", None)
    request.session.modified = True

    messages.success(
        request,
        f'PDF "{locked_pdf.pdf_name}" updated successfully.',
    )

    return redirect_to_builder()




# ============================================================
# PDF DELETE REQUEST
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_request_pdf_delete_view(
    request,
    subject_id,
    chapter_id,
    pdf_id,
):
    """
    Endpoint for the PDF Delete Request card icon.

    The confirmation form + admin approval workflow will be
    implemented in the dedicated PDF delete-request stage.
    """

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:

        messages.error(
            request,
            "You do not have permission to request PDF deletion.",
        )

        return redirect("teacher_login")

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    pdf = get_object_or_404(
        ChapterPDF,
        id=pdf_id,
        chapter=chapter,
    )

    messages.info(
        request,
        f'PDF "{pdf.pdf_name}" delete request form will be connected in the next PDF stage.',
    )

    return redirect(
        (
            f"{reverse('teacher_course_builder', kwargs={'subject_id': subject_id})}"
            f"?chapter={chapter.id}&view=pdfs"
        )
    )


# ============================================================
# CHAPTER → QUIZ WORKSPACE
#
# URL:
# subjects/<subject_id>/builder/chapter/<chapter_id>/quizzes/
#
# RESPONSIBILITY:
# Open the Quiz workspace for the selected chapter.
#
# QUIZ CREATION / QUESTIONS / RESULTS WILL BE ADDED LATER.
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_chapter_quizzes_view(
    request,
    subject_id,
    chapter_id,
):
    """
    Quiz workspace.

    Create flow:
        Quiz basics + all questions are submitted together.
        Questions are dynamically added in the same creation popup.

    Basic quiz fields:
        - quiz_name
        - quiz_description
        - attempt_limit

    Question fields:
        - question_text
        - option_a
        - option_b
        - option_c
        - option_d
        - correct_option
        - marks

    The complete Quiz + Questions + Options are saved atomically.

    Edit, Timeline and Delete Request are handled by their
    dedicated views.
    """

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:
        messages.error(
            request,
            "Access denied.",
        )
        return redirect("teacher_login")

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    builder_url = reverse(
        "teacher_course_builder",
        kwargs={"subject_id": subject_id},
    )

    def redirect_to_quizzes():
        return redirect(
            f"{builder_url}"
            f"?chapter={chapter.id}"
            f"&view=quizzes"
        )

    def save_create_error(
        error_message,
        form_data,
    ):
        request.session["quiz_create_open"] = True
        request.session["quiz_create_error"] = error_message
        request.session["quiz_create_form"] = form_data
        request.session.modified = True

        messages.error(
            request,
            error_message,
        )

        return redirect_to_quizzes()

    if request.method == "GET":
        return redirect_to_quizzes()

    if request.method != "POST":
        messages.error(
            request,
            "Invalid quiz request.",
        )
        return redirect_to_quizzes()

    action = (
        request.POST.get(
            "action",
            "",
        )
        or ""
    ).strip().lower()

    # ========================================================
    # CREATE COMPLETE QUIZ
    # ========================================================

    if action == "create_quiz":

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

        # ----------------------------------------------------
        # Read every dynamically generated question.
        # The HTML uses:
        # question_0_text, question_0_option_a, ...
        # ----------------------------------------------------

        questions = []

        if question_count_raw.isdigit():

            requested_question_count = int(
                question_count_raw
            )

        else:

            requested_question_count = 0

        # Keep the posted question cards bounded.
        if requested_question_count > 100:
            requested_question_count = 100

        for index in range(
            requested_question_count
        ):

            question_text = (
                request.POST.get(
                    f"question_{index}_text",
                    "",
                )
                or ""
            ).strip()

            option_a = (
                request.POST.get(
                    f"question_{index}_option_a",
                    "",
                )
                or ""
            ).strip()

            option_b = (
                request.POST.get(
                    f"question_{index}_option_b",
                    "",
                )
                or ""
            ).strip()

            option_c = (
                request.POST.get(
                    f"question_{index}_option_c",
                    "",
                )
                or ""
            ).strip()

            option_d = (
                request.POST.get(
                    f"question_{index}_option_d",
                    "",
                )
                or ""
            ).strip()

            correct_option = (
                request.POST.get(
                    f"question_{index}_correct",
                    "",
                )
                or ""
            ).strip().upper()

            marks_raw = (
                request.POST.get(
                    f"question_{index}_marks",
                    "",
                )
                or ""
            ).strip()

            questions.append(
                {
                    "question_text": question_text,
                    "option_a": option_a,
                    "option_b": option_b,
                    "option_c": option_c,
                    "option_d": option_d,
                    "correct_option": correct_option,
                    "marks": marks_raw,
                }
            )

        # ----------------------------------------------------
        # Preserve the exact submitted form.
        # ----------------------------------------------------

        form_data = {
            "quiz_name": quiz_name,
            "quiz_description": quiz_description,
            "attempt_limit": attempt_limit_raw,
            "questions": questions,
        }

        # ----------------------------------------------------
        # QUIZ NAME
        # ----------------------------------------------------

        if not quiz_name:
            return save_create_error(
                "Quiz name is required.",
                form_data,
            )

        if len(quiz_name) < 2:
            return save_create_error(
                "Quiz name must contain at least 2 characters.",
                form_data,
            )

        if len(quiz_name) > 255:
            return save_create_error(
                "Quiz name cannot exceed 255 characters.",
                form_data,
            )

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        if not quiz_description:
            return save_create_error(
                "Quiz description is required.",
                form_data,
            )

        if len(quiz_description) < 5:
            return save_create_error(
                "Quiz description must contain at least 5 characters.",
                form_data,
            )

        if len(quiz_description) > 5000:
            return save_create_error(
                "Quiz description cannot exceed 5000 characters.",
                form_data,
            )

        # ----------------------------------------------------
        # MAXIMUM ATTEMPTS
        # ----------------------------------------------------

        if not attempt_limit_raw:
            return save_create_error(
                "Maximum attempts is required.",
                form_data,
            )

        if not attempt_limit_raw.isdigit():
            return save_create_error(
                "Maximum attempts must be a positive whole number.",
                form_data,
            )

        attempt_limit = int(
            attempt_limit_raw
        )

        if attempt_limit <= 0:
            return save_create_error(
                "Maximum attempts must be greater than 0.",
                form_data,
            )

        if attempt_limit > 100:
            return save_create_error(
                "Maximum attempts cannot be greater than 100.",
                form_data,
            )

        # ----------------------------------------------------
        # AT LEAST ONE QUESTION
        # ----------------------------------------------------

        if not questions:
            return save_create_error(
                "Add at least one question before saving the quiz.",
                form_data,
            )

        if len(questions) > 100:
            return save_create_error(
                "A quiz cannot contain more than 100 questions.",
                form_data,
            )

        # ----------------------------------------------------
        # VALIDATE EVERY QUESTION BEFORE DATABASE WRITES
        # ----------------------------------------------------

        validated_questions = []

        for index, question_data in enumerate(
            questions,
            start=1,
        ):

            question_text = (
                question_data["question_text"]
            )

            option_a = question_data["option_a"]
            option_b = question_data["option_b"]
            option_c = question_data["option_c"]
            option_d = question_data["option_d"]

            correct_option = (
                question_data["correct_option"]
            )

            marks_raw = question_data["marks"]

            # -----------------------------------------------
            # QUESTION
            # -----------------------------------------------

            if not question_text:
                return save_create_error(
                    f"Question {index}: question text is required.",
                    form_data,
                )

            if len(question_text) < 3:
                return save_create_error(
                    f"Question {index}: question must contain at least 3 characters.",
                    form_data,
                )

            if len(question_text) > 10000:
                return save_create_error(
                    f"Question {index}: question cannot exceed 10000 characters.",
                    form_data,
                )

            # -----------------------------------------------
            # OPTIONS
            # -----------------------------------------------

            option_values = {
                "A": option_a,
                "B": option_b,
                "C": option_c,
                "D": option_d,
            }

            for label, option_text in option_values.items():

                if not option_text:
                    return save_create_error(
                        f"Question {index}: Option {label} is required.",
                        form_data,
                    )

                if len(option_text) > 500:
                    return save_create_error(
                        f"Question {index}: Option {label} cannot exceed 500 characters.",
                        form_data,
                    )

            # -----------------------------------------------
            # OPTIONS MUST DIFFER
            # -----------------------------------------------

            normalized_options = [
                option_values[label].casefold()
                for label in ("A", "B", "C", "D")
            ]

            if len(
                set(normalized_options)
            ) != 4:

                return save_create_error(
                    f"Question {index}: all four answer options must be different.",
                    form_data,
                )

            # -----------------------------------------------
            # CORRECT ANSWER
            # -----------------------------------------------

            if correct_option not in {
                "A",
                "B",
                "C",
                "D",
            }:

                return save_create_error(
                    f"Question {index}: select exactly one correct answer.",
                    form_data,
                )

            # -----------------------------------------------
            # MARKS
            # -----------------------------------------------

            if not marks_raw:
                return save_create_error(
                    f"Question {index}: marks are required.",
                    form_data,
                )

            if not marks_raw.isdigit():
                return save_create_error(
                    f"Question {index}: marks must be a positive whole number.",
                    form_data,
                )

            marks = int(
                marks_raw
            )

            if marks <= 0:
                return save_create_error(
                    f"Question {index}: marks must be greater than 0.",
                    form_data,
                )

            if marks > 1000:
                return save_create_error(
                    f"Question {index}: marks cannot be greater than 1000.",
                    form_data,
                )

            validated_questions.append(
                {
                    "question_text": question_text,
                    "marks": marks,
                    "options": option_values,
                    "correct_option": correct_option,
                }
            )

        # ----------------------------------------------------
        # DUPLICATE QUIZ NAME
        # ----------------------------------------------------

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
            return save_create_error(
                "A quiz with this name already exists in this chapter.",
                form_data,
            )

        # ----------------------------------------------------
        # ATOMIC SAVE
        #
        # If anything fails, Quiz + Questions + Options are
        # rolled back together.
        # ----------------------------------------------------

        try:

            with transaction.atomic():

                quiz = ChapterQuiz.objects.create(
                    chapter=chapter,
                    quiz_name=quiz_name,
                    quiz_description=quiz_description,
                    attempt_limit=attempt_limit,
                    created_by=teacher,
                    updated_by=teacher,
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

                    options = (
                        question_data["options"]
                    )

                    correct_option = (
                        question_data[
                            "correct_option"
                        ]
                    )

                    for label, option_text in (
                        options.items()
                    ):

                        QuizOption.objects.create(
                            question=question,
                            option_label=label,
                            option_text=option_text,
                            is_correct=(
                                label == correct_option
                            ),
                        )

                QuizChangeLog.objects.create(
                    quiz=quiz,
                    changed_by=teacher,
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
                        f'Quiz "{quiz.quiz_name}" was created '
                        f'with {len(validated_questions)} '
                        f'question'
                        f'{"s" if len(validated_questions) != 1 else ""}.'
                    ),
                )

        except Exception as exc:

            print(
                "Complete quiz creation error:",
                exc,
            )

            return save_create_error(
                "The quiz could not be saved. Your entered data is still preserved. Please try again.",
                form_data,
            )

        # ----------------------------------------------------
        # CLEAR CREATE STATE
        # ----------------------------------------------------

        for session_key in (
            "quiz_create_open",
            "quiz_create_error",
            "quiz_create_form",
            "quiz_question_open",
            "quiz_question_error",
            "quiz_question_form",
            "quiz_question_quiz_id",
        ):

            request.session.pop(
                session_key,
                None,
            )

        request.session.modified = True

        messages.success(
            request,
            (
                f'Quiz "{quiz.quiz_name}" created successfully '
                f'with {len(validated_questions)} question'
                f'{"s" if len(validated_questions) != 1 else ""}.'
            ),
        )

        return redirect_to_quizzes()

    # ========================================================
    # LEGACY ACTION GUARD
    #
    # A question is no longer created through a separate POST.
    # The single Quiz submission above creates everything.
    # ========================================================

    if action == "add_question":
        messages.error(
            request,
            "Questions are added inside the Create Quiz workspace.",
        )
        return redirect_to_quizzes()

    if action == "finish_quiz":
        messages.error(
            request,
            "Please save the complete quiz from the Create Quiz workspace.",
        )
        return redirect_to_quizzes()

    messages.error(
        request,
        "Invalid quiz action.",
    )

    return redirect_to_quizzes()


# ============================================================
# QUIZ EDIT
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_edit_quiz_view(
    request,
    subject_id,
    chapter_id,
    quiz_id,
):
    """
    Edit quiz details and manage its MCQ questions.

    Current editable fields:
        - quiz name
        - description
        - attempt limit
        - add question
        - edit question
        - delete question

    No quiz/question ordering is handled here.
    Student attempt/result logic is intentionally deferred.
    """

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:

        messages.error(
            request,
            "Access denied.",
        )

        return redirect("teacher_login")

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    quiz = get_object_or_404(
        ChapterQuiz.objects
        .select_related(
            "created_by",
            "updated_by",
        )
        .prefetch_related(
            "questions__options",
        ),
        id=quiz_id,
        chapter=chapter,
        is_deleted=False,
    )

    builder_url = reverse(
        "teacher_course_builder",
        kwargs={
            "subject_id": subject_id,
        },
    )

    def redirect_to_builder(
        mode="edit",
    ):

        return redirect(
            (
                f"{builder_url}"
                f"?chapter={chapter.id}"
                f"&view=quizzes"
                f"&quiz={quiz.id}"
                f"&quiz_mode={mode}"
            )
        )

    if request.method != "POST":

        return redirect_to_builder()

    action = (
        request.POST.get(
            "action",
            "",
        )
        or ""
    ).strip().lower()

    # ========================================================
    # UPDATE QUIZ BASIC INFORMATION
    # ========================================================

    if action == "update_quiz":

        new_name = (
            request.POST.get(
                "quiz_name",
                "",
            )
            or ""
        ).strip()

        new_description = (
            request.POST.get(
                "quiz_description",
                "",
            )
            or ""
        ).strip()

        new_attempt_limit_raw = (
            request.POST.get(
                "attempt_limit",
                "",
            )
            or ""
        ).strip()

        if not new_name:

            messages.error(
                request,
                "Quiz name is required.",
            )

            return redirect_to_builder()

        if len(new_name) > 255:

            messages.error(
                request,
                "Quiz name cannot exceed 255 characters.",
            )

            return redirect_to_builder()

        if not new_description:

            messages.error(
                request,
                "Quiz description is required.",
            )

            return redirect_to_builder()

        if len(new_description) > 5000:

            messages.error(
                request,
                "Quiz description cannot exceed 5000 characters.",
            )

            return redirect_to_builder()

        if not new_attempt_limit_raw:

            messages.error(
                request,
                "Attempt limit is required.",
            )

            return redirect_to_builder()

        try:

            new_attempt_limit = int(
                new_attempt_limit_raw
            )

        except (
            TypeError,
            ValueError,
        ):

            messages.error(
                request,
                "Attempt limit must be a whole number.",
            )

            return redirect_to_builder()

        if new_attempt_limit <= 0:

            messages.error(
                request,
                "Attempt limit must be greater than zero.",
            )

            return redirect_to_builder()

        if new_attempt_limit > 100:

            messages.error(
                request,
                "Attempt limit cannot be greater than 100.",
            )

            return redirect_to_builder()

        duplicate_quiz = (
            ChapterQuiz.objects
            .filter(
                chapter=chapter,
                quiz_name__iexact=new_name,
                is_deleted=False,
            )
            .exclude(
                id=quiz.id,
            )
            .exists()
        )

        if duplicate_quiz:

            messages.error(
                request,
                "Another quiz with this name already exists.",
            )

            return redirect_to_builder()

        old_name = quiz.quiz_name
        old_description = quiz.quiz_description
        old_attempt_limit = quiz.attempt_limit

        with transaction.atomic():

            quiz.quiz_name = new_name
            quiz.quiz_description = new_description
            quiz.attempt_limit = new_attempt_limit
            quiz.updated_by = teacher

            quiz.save()

            if old_name != new_name:

                QuizChangeLog.objects.create(
                    quiz=quiz,
                    changed_by=teacher,
                    action="name_changed",
                    field_name="quiz_name",
                    old_value=old_name,
                    new_value=new_name,
                    change_summary="Quiz name was updated.",
                )

            if old_description != new_description:

                QuizChangeLog.objects.create(
                    quiz=quiz,
                    changed_by=teacher,
                    action="description_changed",
                    field_name="quiz_description",
                    old_value=old_description,
                    new_value=new_description,
                    change_summary=(
                        "Quiz description was updated."
                    ),
                )

            if old_attempt_limit != new_attempt_limit:

                QuizChangeLog.objects.create(
                    quiz=quiz,
                    changed_by=teacher,
                    action="attempt_limit_changed",
                    field_name="attempt_limit",
                    old_value=str(old_attempt_limit),
                    new_value=str(new_attempt_limit),
                    change_summary=(
                        f"Attempt limit changed from "
                        f"{old_attempt_limit} to "
                        f"{new_attempt_limit}."
                    ),
                )

        messages.success(
            request,
            f'Quiz "{quiz.quiz_name}" updated successfully.',
        )

        return redirect_to_builder(
            mode="edit",
        )

    # ========================================================
    # ADD QUESTION WHILE EDITING
    # ========================================================

    if action == "add_question":

        return teacher_chapter_quizzes_view(
            request,
            subject_id,
            chapter_id,
        )

    # ========================================================
    # EDIT EXISTING QUESTION
    # ========================================================

    if action == "update_question":

        question_id_raw = (
            request.POST.get(
                "question_id",
                "",
            )
            or ""
        ).strip()

        if not question_id_raw.isdigit():

            messages.error(
                request,
                "Invalid question selected.",
            )

            return redirect_to_builder()

        question = get_object_or_404(
            QuizQuestion,
            id=int(question_id_raw),
            quiz=quiz,
        )

        question_text = (
            request.POST.get(
                "question_text",
                "",
            )
            or ""
        ).strip()

        marks_raw = (
            request.POST.get(
                "marks",
                "",
            )
            or ""
        ).strip()

        option_values = {
            "A": (
                request.POST.get(
                    "option_a",
                    "",
                )
                or ""
            ).strip(),
            "B": (
                request.POST.get(
                    "option_b",
                    "",
                )
                or ""
            ).strip(),
            "C": (
                request.POST.get(
                    "option_c",
                    "",
                )
                or ""
            ).strip(),
            "D": (
                request.POST.get(
                    "option_d",
                    "",
                )
                or ""
            ).strip(),
        }

        correct_option = (
            request.POST.get(
                "correct_option",
                "",
            )
            or ""
        ).strip().upper()

        if not question_text:

            messages.error(
                request,
                "Question is required.",
            )

            return redirect_to_builder()

        if len(question_text) > 10000:

            messages.error(
                request,
                "Question cannot exceed 10000 characters.",
            )

            return redirect_to_builder()

        if not marks_raw:

            messages.error(
                request,
                "Question marks are required.",
            )

            return redirect_to_builder()

        try:

            marks = int(
                marks_raw
            )

        except (
            TypeError,
            ValueError,
        ):

            messages.error(
                request,
                "Question marks must be a whole number.",
            )

            return redirect_to_builder()

        if marks <= 0:

            messages.error(
                request,
                "Question marks must be greater than zero.",
            )

            return redirect_to_builder()

        for label, value in option_values.items():

            if not value:

                messages.error(
                    request,
                    f"Option {label} is required.",
                )

                return redirect_to_builder()

            if len(value) > 500:

                messages.error(
                    request,
                    f"Option {label} cannot exceed 500 characters.",
                )

                return redirect_to_builder()

        if correct_option not in {
            "A",
            "B",
            "C",
            "D",
        }:

            messages.error(
                request,
                "Select exactly one correct answer.",
            )

            return redirect_to_builder()

        old_question_text = question.question_text
        old_marks = question.marks

        old_options = {
            option.option_label: (
                option.option_text,
                option.is_correct,
            )
            for option in question.options.all()
        }

        with transaction.atomic():

            question.question_text = question_text
            question.marks = marks
            question.save()

            current_options = {
                option.option_label: option
                for option in question.options.all()
            }

            for label, value in option_values.items():

                option = current_options.get(label)

                if option is None:

                    option = QuizOption.objects.create(
                        question=question,
                        option_label=label,
                        option_text=value,
                        is_correct=(
                            label == correct_option
                        ),
                    )

                else:

                    option.option_text = value
                    option.is_correct = (
                        label == correct_option
                    )

                    option.save()

            quiz.updated_by = teacher
            quiz.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            if old_question_text != question_text:

                QuizChangeLog.objects.create(
                    quiz=quiz,
                    changed_by=teacher,
                    action="question_updated",
                    field_name="question_text",
                    old_value=old_question_text,
                    new_value=question_text,
                    change_summary=(
                        f"Question {question.id} text was updated."
                    ),
                )

            if old_marks != marks:

                QuizChangeLog.objects.create(
                    quiz=quiz,
                    changed_by=teacher,
                    action="question_updated",
                    field_name="marks",
                    old_value=str(old_marks),
                    new_value=str(marks),
                    change_summary=(
                        f"Question {question.id} marks were updated."
                    ),
                )

            for label, new_value in option_values.items():

                old_value, old_correct = old_options.get(
                    label,
                    ("", False),
                )

                new_correct = (
                    label == correct_option
                )

                if old_value != new_value:

                    QuizChangeLog.objects.create(
                        quiz=quiz,
                        changed_by=teacher,
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
                        changed_by=teacher,
                        action="correct_answer_changed",
                        field_name=f"option_{label}_correct",
                        old_value=str(old_correct),
                        new_value=str(new_correct),
                        change_summary=(
                            f"Correct-answer selection for option "
                            f"{label} of question {question.id} changed."
                        ),
                    )

        messages.success(
            request,
            f"Question {question.id} updated successfully.",
        )

        return redirect_to_builder(
            mode="edit",
        )

    # ========================================================
    # DELETE QUESTION
    # ========================================================

    if action == "delete_question":

        question_id_raw = (
            request.POST.get(
                "question_id",
                "",
            )
            or ""
        ).strip()

        if not question_id_raw.isdigit():

            messages.error(
                request,
                "Invalid question selected.",
            )

            return redirect_to_builder()

        question = get_object_or_404(
            QuizQuestion,
            id=int(question_id_raw),
            quiz=quiz,
        )

        question_snapshot = question.question_text

        with transaction.atomic():

            question.delete()

            quiz.updated_by = teacher
            quiz.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            QuizChangeLog.objects.create(
                quiz=quiz,
                changed_by=teacher,
                action="question_deleted",
                field_name="question",
                old_value=question_snapshot,
                new_value="",
                change_summary=(
                    f"Question {question_id_raw} was deleted."
                ),
            )

        messages.success(
            request,
            "Quiz question deleted successfully.",
        )

        return redirect_to_builder(
            mode="edit",
        )

    messages.error(
        request,
        "Invalid quiz edit action.",
    )

    return redirect_to_builder()


# ============================================================
# QUIZ TIMELINE
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_quiz_timeline_view(
    request,
    subject_id,
    chapter_id,
    quiz_id,
):
    """
    Validate the teacher/chapter/quiz relationship and open the
    quiz timeline inside the unified Course Builder.
    """

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:

        messages.error(
            request,
            "You do not have permission to view quiz history.",
        )

        return redirect(
            "teacher_login"
        )

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    quiz = get_object_or_404(
        ChapterQuiz,
        id=quiz_id,
        chapter=chapter,
        is_deleted=False,
    )

    return redirect(
        (
            f"{reverse('teacher_course_builder', kwargs={'subject_id': subject_id})}"
            f"?chapter={chapter.id}"
            f"&view=quiz_timeline"
            f"&quiz={quiz.id}"
        )
    )


# ============================================================
# QUIZ DELETE REQUEST
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_request_quiz_delete_view(
    request,
    subject_id,
    chapter_id,
    quiz_id,
):
    """
    Teacher requests deletion.
    Actual deletion is handled later by the admin workflow.
    """

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None or assignment is None:

        messages.error(
            request,
            "You do not have permission to request quiz deletion.",
        )

        return redirect(
            "teacher_login"
        )

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    quiz = get_object_or_404(
        ChapterQuiz,
        id=quiz_id,
        chapter=chapter,
        is_deleted=False,
    )

    builder_url = reverse(
        "teacher_course_builder",
        kwargs={
            "subject_id": subject_id,
        },
    )

    if request.method != "POST":

        messages.error(
            request,
            "Invalid delete request.",
        )

        return redirect(
            (
                f"{builder_url}"
                f"?chapter={chapter.id}&view=quizzes"
            )
        )

    if (
        quiz.delete_requested
        and quiz.delete_status == "pending"
    ):

        messages.info(
            request,
            "A delete request for this quiz is already pending.",
        )

        return redirect(
            (
                f"{builder_url}"
                f"?chapter={chapter.id}&view=quizzes"
            )
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

        return redirect(
            (
                f"{builder_url}"
                f"?chapter={chapter.id}&view=quizzes"
            )
        )

    if len(delete_reason) > 2000:

        messages.error(
            request,
            "Delete reason cannot exceed 2000 characters.",
        )

        return redirect(
            (
                f"{builder_url}"
                f"?chapter={chapter.id}&view=quizzes"
            )
        )

    from django.utils import timezone

    quiz.delete_requested = True
    quiz.delete_requested_by = teacher
    quiz.delete_requested_at = timezone.now()
    quiz.delete_reason = delete_reason
    quiz.delete_status = "pending"
    quiz.updated_by = teacher

    quiz.save(
        update_fields=[
            "delete_requested",
            "delete_requested_by",
            "delete_requested_at",
            "delete_reason",
            "delete_status",
            "updated_by",
            "updated_at",
        ]
    )

    QuizChangeLog.objects.create(
        quiz=quiz,
        changed_by=teacher,
        action="delete_requested",
        field_name="delete_request",
        old_value="",
        new_value=delete_reason,
        change_summary="Quiz deletion was requested.",
    )

    messages.success(
        request,
        "Quiz deletion request submitted successfully.",
    )

    return redirect(
        (
            f"{builder_url}"
            f"?chapter={chapter.id}&view=quizzes"
        )
    )


@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_chapter_live_view(
    request,
    subject_id,
    chapter_id,
):

    teacher, assignment = (
        _get_teacher_subject_assignment(
            request,
            subject_id,
        )
    )

    if teacher is None:

        messages.error(
            request,
            "Access denied.",
        )

        return redirect(
            "teacher_login"
        )

    chapter = get_object_or_404(
        CourseChapter,
        id=chapter_id,
        batch=assignment.batch,
        subject=assignment.subject,
        is_deleted=False,
    )

    assigned_teachers = (
        TeacherSubject.objects
        .filter(
            subject=assignment.subject,
            is_active=True,
        )
        .select_related("teacher")
        .order_by(
            "teacher__full_name"
        )
    )

    chapters = (
        CourseChapter.objects
        .filter(
            batch=assignment.batch,
            subject=assignment.subject,
            is_deleted=False,
        )
        .order_by(
            "chapter_order",
            "id",
        )
    )

    context = {
        "teacher": teacher,
        "subject": assignment.subject,
        "batch": assignment.batch,
        "assignment": assignment,
        "assigned_teachers": assigned_teachers,
        "chapters": chapters,
        "chapter_count": chapters.count(),

        "selected_chapter": chapter,

        # Right-side workspace
        "selected_content": "live",
    }

    return render(
        request,
        "teachers/content_builder/course_builder.html",
        context,
    )