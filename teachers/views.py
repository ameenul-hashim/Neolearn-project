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
    ChapterVideo,
    ChapterPDF,
    ChapterQuiz,
    QuizQuestion,
)
from courses.forms import (
    ChapterCreateForm,
    ChapterEditForm,
    VideoUploadForm,
    VideoEditForm,
    PDFUploadForm,
    PDFEditForm,
    QuizForm,
    QuizQuestionForm,
    DeleteReasonForm,
)
from courses import services as course_services


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

            video_timeline_entries = [
                course_services.build_timeline_entry(log)
                for log in course_services.get_video_timeline(
                    selected_video
                )
            ]

    # ========================================================
    # SELECTED QUIZ FOR QUIZ WORKSPACE / EDIT / QUESTIONS
    # ========================================================
    # The unified Course Builder uses the same page for the
    # quiz list, question manager and quiz edit workspace.
    # Therefore selected_quiz must be resolved not only for the
    # dedicated timeline view, but also when ?view=quizzes is
    # combined with ?quiz=<id>.
    # ========================================================

    if (
        selected_chapter
        and selected_content == "quizzes"
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
            )
            .first()
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

            quiz_timeline_entries = [
                course_services.build_timeline_entry(log)
                for log in course_services.get_quiz_timeline(
                    selected_quiz
                )
            ]

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

            pdf_timeline_entries = [
                course_services.build_timeline_entry(log)
                for log in course_services.get_pdf_timeline(
                    selected_pdf
                )
            ]

    if selected_chapter and selected_content == "timeline":

        timeline_entries = [
            course_services.build_timeline_entry(log)
            for log in course_services.get_chapter_timeline(
                selected_chapter
            )
        ]

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
    # SHARED CHAPTER CREATE FORM
    #
    # Batch and Subject are supplied by the view so the form
    # can enforce the duplicate-name rule within the exact
    # batch + subject scope.
    # ========================================================

    form = ChapterCreateForm(
        request.POST,
        batch=assignment.batch,
        subject=assignment.subject,
    )

    if not form.is_valid():

        first_error = (
            next(
                iter(
                    form.errors.values()
                )
            )[0]
        )

        messages.error(
            request,
            first_error,
        )

        return redirect(
            "teacher_course_builder",
            subject_id=subject_id,
        )

    # ========================================================
    # CREATE CHAPTER VIA SHARED SERVICE
    #
    # The service calculates the automatic chapter order and
    # writes the change log.
    # ========================================================

    try:

        chapter = course_services.create_chapter(
            batch=assignment.batch,
            subject=assignment.subject,
            actor=teacher,
            chapter_name=(
                form.cleaned_data["chapter_name"]
            ),
            chapter_description=(
                form.cleaned_data["chapter_description"]
            ),
            status=(
                form.cleaned_data["status"]
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
    # SHARED CHAPTER EDIT FORM
    # ========================================================

    form = ChapterEditForm(
        request.POST,
        batch=assignment.batch,
        subject=assignment.subject,
        instance=chapter,
    )

    form_data = {
        "chapter_id": chapter.id,
        "chapter_name": (
            form.data.get("chapter_name", "") or ""
        ),
        "chapter_description": (
            form.data.get("chapter_description", "") or ""
        ),
        "chapter_order": (
            form.data.get("chapter_order", "") or ""
        ),
        "status": (
            form.data.get("status", "") or ""
        ),
    }

    if not form.is_valid():

        first_error = (
            next(
                iter(
                    form.errors.values()
                )
            )[0]
        )

        return open_edit_popup(
            first_error,
            form_data,
        )

    # ========================================================
    # UPDATE VIA SHARED SERVICE
    #
    # The service validates the order against the active
    # chapter count, repositions siblings, and writes the
    # timeline entries.
    # ========================================================

    try:

        course_services.update_chapter(
            chapter=chapter,
            actor=teacher,
            chapter_name=(
                form.cleaned_data["chapter_name"]
            ),
            chapter_description=(
                form.cleaned_data["chapter_description"]
            ),
            chapter_order=(
                form.cleaned_data["chapter_order"]
            ),
            status=(
                form.cleaned_data["status"]
            ),
        )

    except ValueError as exc:

        return open_edit_popup(
            str(exc),
            form_data,
        )

    except Exception as exc:

        print(
            "Chapter update error:",
            exc,
        )

        return open_edit_popup(
            "The chapter could not be updated. Please try again.",
            form_data,
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

    form = DeleteReasonForm(
        request.POST
    )

    if not form.is_valid():

        first_error = (
            next(
                iter(
                    form.errors.values()
                )
            )[0]
        )

        messages.error(
            request,
            first_error,
        )

        return redirect(
            "teacher_chapter",
            subject_id=subject_id,
            chapter_id=chapter.id,
        )

    # ========================================================
    # SAVE DELETE REQUEST VIA SHARED SERVICE
    # ========================================================

    course_services.request_delete(
        "chapter",
        chapter,
        teacher,
        form.cleaned_data["delete_reason"],
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

        form = VideoUploadForm(
            request.POST,
            request.FILES,
            chapter=chapter,
        )

        if not form.is_valid():

            first_error = (
                next(
                    iter(
                        form.errors.values()
                    )
                )[0]
            )

            return upload_error(
                first_error,
                form.data.get("video_name", "") or "",
                form.data.get("video_description", "") or "",
            )

        try:

            video = course_services.create_video(
                chapter=chapter,
                actor=teacher,
                video_name=(
                    form.cleaned_data["video_name"]
                ),
                video_description=(
                    form.cleaned_data["video_description"]
                ),
                video_file=(
                    form.cleaned_data["video_file"]
                ),
            )

        except ValueError as exc:

            return upload_error(
                str(exc),
                form.data.get("video_name", "") or "",
                form.data.get("video_description", "") or "",
            )

        except Exception as exc:

            print("Video upload error:", exc)

            return upload_error(
                "The video could not be uploaded. Please try again.",
                form.data.get("video_name", "") or "",
                form.data.get("video_description", "") or "",
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

        old_file_name = (
            getattr(video.video_file, "name", "") or ""
        )

        form = VideoEditForm(
            request.POST,
            request.FILES,
            chapter=chapter,
            instance=video,
        )

        form_data = {
            "video_id": video.id,
            "video_name": (
                form.data.get("video_name", "") or ""
            ),
            "video_description": (
                form.data.get("video_description", "") or ""
            ),
            "video_order": (
                form.data.get("video_order", "") or ""
            ),
            "current_file_name": old_file_name,
        }

        if not form.is_valid():

            first_error = (
                next(
                    iter(
                        form.errors.values()
                    )
                )[0]
            )

            return edit_error(
                first_error,
                video.id,
                form_data["video_name"],
                form_data["video_description"],
                form_data["video_order"] or video.video_order,
                old_file_name,
            )

        try:

            course_services.update_video(
                video=video,
                actor=teacher,
                video_name=(
                    form.cleaned_data["video_name"]
                ),
                video_description=(
                    form.cleaned_data["video_description"]
                ),
                video_order=(
                    form.cleaned_data["video_order"]
                ),
                replacement_file=(
                    form.cleaned_data.get("video_file")
                ),
            )

        except ValueError as exc:

            return edit_error(
                str(exc),
                video.id,
                form_data["video_name"],
                form_data["video_description"],
                form_data["video_order"] or video.video_order,
                old_file_name,
            )

        except Exception as exc:

            print("Video edit error:", exc)

            return edit_error(
                "The video could not be updated. Please try again.",
                video.id,
                form_data["video_name"],
                form_data["video_description"],
                form_data["video_order"] or video.video_order,
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
    # SHARED PDF UPLOAD FORM
    # ========================================================

    form = PDFUploadForm(
        request.POST,
        request.FILES,
        chapter=chapter,
    )

    if not form.is_valid():

        first_error = (
            next(
                iter(
                    form.errors.values()
                )
            )[0]
        )

        return validation_error(
            first_error,
            form.data.get("pdf_name", "") or "",
            form.data.get("pdf_description", "") or "",
        )

    # ========================================================
    # CREATE PDF VIA SHARED SERVICE
    #
    # The service assigns the automatic order and writes the
    # PDF timeline entry.
    # ========================================================

    try:

        pdf = course_services.create_pdf(
            chapter=chapter,
            actor=teacher,
            pdf_name=(
                form.cleaned_data["pdf_name"]
            ),
            pdf_description=(
                form.cleaned_data["pdf_description"]
            ),
            pdf_file=(
                form.cleaned_data["pdf_file"]
            ),
            pdf_thumbnail=(
                form.cleaned_data.get("pdf_thumbnail")
            ),
        )

    except ValueError as exc:

        return validation_error(
            str(exc),
            form.data.get("pdf_name", "") or "",
            form.data.get("pdf_description", "") or "",
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
            form.data.get("pdf_name", "") or "",
            form.data.get("pdf_description", "") or "",
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
    # SHARED PDF EDIT FORM
    # ========================================================

    form = PDFEditForm(
        request.POST,
        request.FILES,
        chapter=chapter,
        instance=pdf,
    )

    form_data = {
        "pdf_id": pdf.id,
        "pdf_name": (
            form.data.get("pdf_name", "") or ""
        ),
        "pdf_description": (
            form.data.get("pdf_description", "") or ""
        ),
        "pdf_order": (
            form.data.get("pdf_order", "") or ""
        ),
    }

    if not form.is_valid():

        first_error = (
            next(
                iter(
                    form.errors.values()
                )
            )[0]
        )

        return save_edit_state(
            first_error,
            form_data["pdf_name"],
            form_data["pdf_description"],
            form_data["pdf_order"] or pdf.pdf_order,
        )

    # ========================================================
    # UPDATE VIA SHARED SERVICE
    #
    # The service validates the order against the active PDF
    # count, repositions siblings, and writes the timeline.
    # ========================================================

    try:

        course_services.update_pdf(
            pdf=pdf,
            actor=teacher,
            pdf_name=(
                form.cleaned_data["pdf_name"]
            ),
            pdf_description=(
                form.cleaned_data["pdf_description"]
            ),
            pdf_order=(
                form.cleaned_data["pdf_order"]
            ),
            replacement_file=(
                form.cleaned_data.get("pdf_file")
            ),
            replacement_thumbnail=(
                form.cleaned_data.get("pdf_thumbnail")
            ),
        )

    except ValueError as exc:

        return save_edit_state(
            str(exc),
            form_data["pdf_name"],
            form_data["pdf_description"],
            form_data["pdf_order"] or pdf.pdf_order,
        )

    except Exception as exc:

        print(
            "PDF edit error:",
            exc,
        )

        return save_edit_state(
            "The PDF could not be updated. Please try again.",
            form_data["pdf_name"],
            form_data["pdf_description"],
            form_data["pdf_order"] or pdf.pdf_order,
        )

    # Clear edit state.
    request.session.pop("pdf_edit_open", None)
    request.session.pop("pdf_edit_error", None)
    request.session.pop("pdf_edit_form", None)
    request.session.modified = True

    messages.success(
        request,
        f'PDF "{pdf.pdf_name}" updated successfully.',
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
    Teacher requests deletion of a PDF note.

    Only a POST with a valid delete reason is accepted. The
    shared request_delete service marks the PDF as pending and
    writes the timeline entry. The actual delete is performed
    by an admin after approval.
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
        is_deleted=False,
    )

    def redirect_to_builder():
        return redirect(
            (
                f"{reverse('teacher_course_builder', kwargs={'subject_id': subject_id})}"
                f"?chapter={chapter.id}&view=pdfs"
            )
        )

    # ========================================================
    # DELETE REQUEST MUST BE POST
    # ========================================================

    if request.method != "POST":

        messages.error(
            request,
            "Invalid delete request.",
        )

        return redirect_to_builder()

    # ========================================================
    # ALREADY PENDING
    # ========================================================

    if (
        pdf.delete_requested
        and pdf.delete_status == "pending"
    ):

        messages.info(
            request,
            "A delete request for this PDF is already pending.",
        )

        return redirect_to_builder()

    # ========================================================
    # DELETE REASON
    # ========================================================

    form = DeleteReasonForm(
        request.POST
    )

    if not form.is_valid():

        first_error = (
            next(
                iter(
                    form.errors.values()
                )
            )[0]
        )

        messages.error(
            request,
            first_error,
        )

        return redirect_to_builder()

    # ========================================================
    # SAVE DELETE REQUEST VIA SHARED SERVICE
    # ========================================================

    course_services.request_delete(
        "pdf",
        pdf,
        teacher,
        form.cleaned_data["delete_reason"],
    )

    messages.success(
        request,
        "PDF deletion request submitted successfully.",
    )

    return redirect_to_builder()


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
    Quiz workspace handler.

    Handles complete quiz creation. An existing quiz's Add Question form
    is routed to teacher_edit_quiz_view so question persistence has one
    source of truth.

    IMPORTANT: this uses the current teacher models:
      ChapterQuiz: quiz_name, quiz_description, attempt_limit
      QuizQuestion: question_text, marks
      QuizOption: option_label (A-D), option_text, is_correct
    """
    teacher, assignment = _get_teacher_subject_assignment(
        request,
        subject_id,
    )

    if teacher is None or assignment is None:
        messages.error(request, "Access denied.")
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
            f"{builder_url}?chapter={chapter.id}&view=quizzes"
        )

    def save_create_error(message_text, form_data):
        request.session["quiz_create_open"] = True
        request.session["quiz_create_error"] = message_text
        request.session["quiz_create_form"] = form_data
        request.session.modified = True
        messages.error(request, message_text)
        return redirect_to_quizzes()

    if request.method == "GET":
        return redirect_to_quizzes()

    if request.method != "POST":
        messages.error(request, "Invalid quiz request.")
        return redirect_to_quizzes()

    action = (request.POST.get("action", "") or "").strip().lower()

    # --------------------------------------------------------
    # ADD QUESTION TO AN EXISTING QUIZ
    # --------------------------------------------------------
    if action == "add_question":
        quiz_id_raw = (request.POST.get("quiz_id", "") or "").strip()

        if not quiz_id_raw.isdigit():
            messages.error(request, "Invalid quiz selected.")
            return redirect_to_quizzes()

        quiz = get_object_or_404(
            ChapterQuiz,
            id=int(quiz_id_raw),
            chapter=chapter,
            is_deleted=False,
        )

        return teacher_edit_quiz_view(
            request,
            subject_id,
            chapter_id,
            quiz.id,
        )

    # --------------------------------------------------------
    # COMPLETE QUIZ CREATION
    # --------------------------------------------------------
    if action == "create_quiz":
        quiz_name = (request.POST.get("quiz_name", "") or "").strip()
        quiz_description = (
            request.POST.get("quiz_description", "") or ""
        ).strip()
        attempt_limit_raw = (
            request.POST.get("attempt_limit", "") or ""
        ).strip()
        question_count_raw = (
            request.POST.get("question_count", "") or ""
        ).strip()

        requested_question_count = (
            int(question_count_raw)
            if question_count_raw.isdigit()
            else 0
        )
        requested_question_count = min(
            max(requested_question_count, 0),
            100,
        )

        questions = []
        for index in range(requested_question_count):
            questions.append({
                "question_text": (
                    request.POST.get(f"question_{index}_text", "") or ""
                ).strip(),
                "option_a": (
                    request.POST.get(f"question_{index}_option_a", "") or ""
                ).strip(),
                "option_b": (
                    request.POST.get(f"question_{index}_option_b", "") or ""
                ).strip(),
                "option_c": (
                    request.POST.get(f"question_{index}_option_c", "") or ""
                ).strip(),
                "option_d": (
                    request.POST.get(f"question_{index}_option_d", "") or ""
                ).strip(),
                "correct_option": (
                    request.POST.get(f"question_{index}_correct", "") or ""
                ).strip().upper(),
                "marks": (
                    request.POST.get(f"question_{index}_marks", "") or ""
                ).strip(),
            })

        form_data = {
            "quiz_name": quiz_name,
            "quiz_description": quiz_description,
            "attempt_limit": attempt_limit_raw,
            "questions": questions,
        }

        # ----------------------------------------------------
        # SHARED QUIZ BASIC FORM
        # ----------------------------------------------------

        form = QuizForm(
            request.POST,
            chapter=chapter,
        )

        if not form.is_valid():

            first_error = (
                next(
                    iter(
                        form.errors.values()
                    )
                )[0]
            )

            return save_create_error(
                first_error,
                form_data,
            )

        if not questions:
            return save_create_error(
                "Add at least one question before saving the quiz.",
                form_data,
            )

        # ----------------------------------------------------
        # SHARED QUESTION FORM — ONE PER QUESTION
        # ----------------------------------------------------

        validated_questions = []
        for index, question_data in enumerate(questions, start=1):
            question_form = QuizQuestionForm(question_data)

            if not question_form.is_valid():

                first_error = (
                    next(
                        iter(
                            question_form.errors.values()
                        )
                    )[0]
                )

                return save_create_error(
                    f"Question {index}: {first_error}",
                    form_data,
                )

            validated_questions.append({
                "question_text": (
                    question_form.cleaned_data["question_text"]
                ),
                "marks": (
                    question_form.cleaned_data["marks"]
                ),
                "options": {
                    "A": question_form.cleaned_data["option_a"],
                    "B": question_form.cleaned_data["option_b"],
                    "C": question_form.cleaned_data["option_c"],
                    "D": question_form.cleaned_data["option_d"],
                },
                "correct_option": (
                    question_form.cleaned_data["correct_option"]
                ),
            })

        # ----------------------------------------------------
        # CREATE QUIZ VIA SHARED SERVICE
        # ----------------------------------------------------

        try:
            quiz = course_services.create_quiz(
                chapter=chapter,
                actor=teacher,
                quiz_name=(
                    form.cleaned_data["quiz_name"]
                ),
                quiz_description=(
                    form.cleaned_data["quiz_description"]
                ),
                attempt_limit=(
                    form.cleaned_data["attempt_limit"]
                ),
                questions=validated_questions,
            )
        except ValueError as exc:
            return save_create_error(
                str(exc),
                form_data,
            )
        except Exception as exc:
            print("Complete quiz creation error:", repr(exc))
            return save_create_error(
                "The quiz could not be saved. Your entered data is still preserved. Please try again.",
                form_data,
            )

        for session_key in (
            "quiz_create_open",
            "quiz_create_error",
            "quiz_create_form",
            "quiz_question_open",
            "quiz_question_error",
            "quiz_question_form",
            "quiz_question_quiz_id",
        ):
            request.session.pop(session_key, None)
        request.session.modified = True

        messages.success(
            request,
            f'Quiz "{quiz.quiz_name}" created successfully with '
            f"{len(validated_questions)} question"
            f'{"s" if len(validated_questions) != 1 else ""}.',
        )
        return redirect_to_quizzes()

    messages.error(request, "Invalid quiz action.")
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
    Unified Teacher Quiz Edit handler.

    ONE SAVE workflow:
        - Quiz name
        - Quiz description
        - Maximum attempts
        - Existing question edits
        - New question creation
        - Existing question removal
        - Options A-D
        - Correct answer
        - Marks
        - Timeline entries

    The current database schema is used exactly:
        QuizQuestion:
            quiz, question_text, marks, created_at, updated_at

        QuizOption:
            question, option_label, option_text, is_correct,
            created_at, updated_at

    There is intentionally no question_order / option_order field.
    """

    teacher, assignment = _get_teacher_subject_assignment(
        request,
        subject_id,
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

    def redirect_to_builder():
        return redirect(
            (
                f"{builder_url}"
                f"?chapter={chapter.id}"
                f"&view=quizzes"
                f"&quiz={quiz.id}"
                f"&quiz_mode=edit"
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
    # ONLY THE MASTER EDIT SAVE IS USED HERE
    # ========================================================

    if action != "update_complete_quiz":
        messages.error(
            request,
            "Invalid quiz edit request.",
        )
        return redirect_to_builder()

    # ========================================================
    # SHARED QUIZ FORM — BASIC FIELDS
    # ========================================================

    form = QuizForm(
        request.POST,
        chapter=chapter,
        instance=quiz,
    )

    validation_errors = []

    if not form.is_valid():

        for field_errors in form.errors.values():

            for error in field_errors:

                validation_errors.append(
                    error
                )

    quiz_name = (
        form.data.get("quiz_name", "") or ""
    ).strip()

    quiz_description = (
        form.data.get("quiz_description", "") or ""
    ).strip()

    attempt_limit_raw = (
        form.data.get("attempt_limit", "") or ""
    ).strip()

    # ========================================================
    # READ ALL QUESTION CARDS
    #
    # The HTML sends:
    #
    # question_count
    # question_0_id
    # question_0_text
    # question_0_option_a
    # question_0_option_b
    # question_0_option_c
    # question_0_option_d
    # question_0_correct
    # question_0_marks
    #
    # and so on.
    # ========================================================

    question_count_raw = (
        request.POST.get(
            "question_count",
            "",
        )
        or ""
    ).strip()

    if not question_count_raw.isdigit():
        question_count = 0
        validation_errors.append(
            "The question list is invalid."
        )
    else:
        question_count = int(
            question_count_raw
        )

    if question_count > 100:
        validation_errors.append(
            "A quiz cannot contain more than 100 questions."
        )
        question_count = 100

    submitted_questions = []
    submitted_existing_ids = set()

    for index in range(question_count):

        question_id = (
            request.POST.get(
                f"question_{index}_id",
                "",
            )
            or ""
        ).strip()

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

        question_number = index + 1

        # ----------------------------------------------------
        # QUESTION ID
        # ----------------------------------------------------

        if question_id:
            if not question_id.isdigit():
                validation_errors.append(
                    f"Question {question_number}: invalid question ID."
                )
                parsed_question_id = None
            else:
                parsed_question_id = int(question_id)

                if parsed_question_id in submitted_existing_ids:
                    validation_errors.append(
                        f"Question {question_number}: duplicate question submitted."
                    )

                submitted_existing_ids.add(
                    parsed_question_id
                )
        else:
            parsed_question_id = None

        # ----------------------------------------------------
        # SHARED QUESTION FORM VALIDATION
        # ----------------------------------------------------

        question_form = QuizQuestionForm(
            {
                "question_text": question_text,
                "marks": marks_raw,
                "option_a": option_a,
                "option_b": option_b,
                "option_c": option_c,
                "option_d": option_d,
                "correct_option": correct_option,
            }
        )

        if not question_form.is_valid():

            for field_errors in question_form.errors.values():

                for error in field_errors:

                    validation_errors.append(
                        f"Question {question_number}: {error}"
                    )

        submitted_questions.append(
            {
                "index": index,
                "question_id": parsed_question_id,
                "question_text": question_text,
                "option_a": option_a,
                "option_b": option_b,
                "option_c": option_c,
                "option_d": option_d,
                "correct_option": correct_option,
                "marks": (
                    question_form.cleaned_data.get("marks")
                    if question_form.is_valid()
                    else None
                ),
            }
        )

    # ========================================================
    # DELETED EXISTING QUESTION IDS
    #
    # JavaScript places removed database question IDs here.
    # New unsaved cards have no ID and therefore need no entry.
    # ========================================================

    deleted_ids_raw = (
        request.POST.getlist(
            "deleted_question_ids"
        )
    )

    deleted_ids = set()

    for raw_id in deleted_ids_raw:

        raw_id = (
            raw_id
            or ""
        ).strip()

        if not raw_id:
            continue

        if not raw_id.isdigit():
            validation_errors.append(
                "One or more deleted question references are invalid."
            )
            continue

        deleted_ids.add(
            int(raw_id)
        )

    # A question cannot be both submitted and deleted.
    overlap = (
        submitted_existing_ids
        & deleted_ids
    )

    if overlap:
        validation_errors.append(
            "The same question cannot be updated and deleted in one save."
        )

    # ========================================================
    # FETCH EXISTING QUESTIONS
    # ========================================================

    existing_questions = {
        question.id: question
        for question in (
            QuizQuestion.objects
            .filter(
                quiz=quiz,
                id__in=submitted_existing_ids | deleted_ids,
            )
            .prefetch_related("options")
        )
    }

    unknown_ids = (
        submitted_existing_ids | deleted_ids
    ) - set(existing_questions.keys())

    if unknown_ids:
        validation_errors.append(
            "One or more questions no longer belong to this quiz."
        )

    # ========================================================
    # ENSURE THERE IS AT LEAST ONE QUESTION AFTER REMOVALS
    # ========================================================

    saved_question_ids = set(
        QuizQuestion.objects
        .filter(
            quiz=quiz,
        )
        .values_list(
            "id",
            flat=True,
        )
    )

    final_existing_ids = (
        saved_question_ids
        - deleted_ids
    )

    final_existing_ids &= submitted_existing_ids

    new_question_count = sum(
        1
        for item in submitted_questions
        if item["question_id"] is None
    )

    # Any existing question not included in the submitted form is
    # considered invalid rather than silently deleting it.
    missing_existing_ids = (
        saved_question_ids
        - deleted_ids
        - submitted_existing_ids
    )

    if missing_existing_ids:
        validation_errors.append(
            "The edit form is missing one or more existing questions. Please reload the quiz and try again."
        )

    final_question_count = (
        len(final_existing_ids)
        + new_question_count
    )

    if final_question_count < 1:
        validation_errors.append(
            "A quiz must contain at least one question."
        )

    if final_question_count > 100:
        validation_errors.append(
            "A quiz cannot contain more than 100 questions."
        )

    # ========================================================
    # STOP BEFORE ANY DATABASE WRITE
    # ========================================================

    if validation_errors:

        # Keep a compact server-side copy for debugging/reload
        # and show every validation result through Django messages.
        request.session["quiz_edit_validation_errors"] = (
            validation_errors[:30]
        )
        request.session.modified = True

        for error in validation_errors[:30]:
            messages.error(
                request,
                error,
            )

        return redirect_to_builder()

    # ========================================================
    # SAVE EVERYTHING IN ONE TRANSACTION
    # ========================================================

    try:

        with transaction.atomic():

            # ------------------------------------------------
            # BASIC QUIZ UPDATE VIA SHARED SERVICE
            # ------------------------------------------------

            course_services.update_quiz(
                quiz=quiz,
                actor=teacher,
                quiz_name=form.cleaned_data["quiz_name"],
                quiz_description=form.cleaned_data["quiz_description"],
                attempt_limit=form.cleaned_data["attempt_limit"],
            )

            # ------------------------------------------------
            # DELETE REMOVED EXISTING QUESTIONS
            # ------------------------------------------------

            for question_id in deleted_ids:

                question = existing_questions.get(
                    question_id
                )

                if question is None:
                    continue

                course_services.delete_quiz_question(
                    question=question,
                    actor=teacher,
                )

            # ------------------------------------------------
            # UPDATE EXISTING + CREATE NEW QUESTIONS
            # ------------------------------------------------

            for item in submitted_questions:

                question_id = item["question_id"]

                if question_id is None:

                    course_services.create_quiz_question(
                        quiz=quiz,
                        actor=teacher,
                        question_text=item["question_text"],
                        marks=item["marks"],
                        options={
                            "A": item["option_a"],
                            "B": item["option_b"],
                            "C": item["option_c"],
                            "D": item["option_d"],
                        },
                        correct_option=item["correct_option"],
                    )

                    continue

                question = existing_questions.get(
                    question_id
                )

                if question is None:
                    raise ValueError(
                        "An existing question could not be found during save."
                    )

                course_services.update_quiz_question(
                    question=question,
                    actor=teacher,
                    question_text=item["question_text"],
                    marks=item["marks"],
                    options={
                        "A": item["option_a"],
                        "B": item["option_b"],
                        "C": item["option_c"],
                        "D": item["option_d"],
                    },
                    correct_option=item["correct_option"],
                )

    except Exception as exc:

        print(
            "Complete quiz edit save error:",
            repr(exc),
        )

        messages.error(
            request,
            "Quiz could not be saved. No changes were saved.",
        )

        return redirect_to_builder()

    request.session.pop(
        "quiz_edit_validation_errors",
        None,
    )
    request.session.modified = True

    messages.success(
        request,
        (
            f'Quiz "{quiz.quiz_name}" and all question changes '
            "were saved successfully."
        ),
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

    form = DeleteReasonForm(
        request.POST
    )

    if not form.is_valid():

        messages.error(
            request,
            next(
                iter(
                    form.errors.values()
                )
            )[0],
        )

        return redirect(
            (
                f"{builder_url}"
                f"?chapter={chapter.id}&view=quizzes"
            )
        )

    delete_reason = (
        form.cleaned_data["delete_reason"]
    )

    course_services.request_delete(
        content_type="quiz",
        obj=quiz,
        actor=teacher,
        delete_reason=delete_reason,
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