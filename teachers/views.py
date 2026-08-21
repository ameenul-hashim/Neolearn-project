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
from teachers.models import (CourseChapter,ChapterChangeLog,ChapterVideo,VideoChangeLog)


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

        # Chapter timeline.
        "timeline_entries": timeline_entries,
        "timeline_count": len(timeline_entries),

        # Video timeline.
        "selected_video": selected_video,
        "video_timeline_entries": video_timeline_entries,
        "video_timeline_count": len(video_timeline_entries),
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
        "selected_content": "pdfs",
    }

    return render(
        request,
        "teachers/content_builder/course_builder.html",
        context,
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
        "selected_content": "quizzes",
    }

    return render(
        request,
        "teachers/content_builder/course_builder.html",
        context,
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