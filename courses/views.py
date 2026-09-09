from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from admins.models import Batch, Subject

from .helpers import get_next_order
from .models import CourseChapter, ChapterChangeLog


@login_required
def course_builder_view(request, batch_id, subject_id):
    """
    Common Course Builder entry point.

    Receives the selected Batch and Subject and opens
    the common Course Builder template.

    Handles Create Chapter form submissions.
    """

    # ---------------------------------------------------------
    # 1. Get the selected Batch
    # ---------------------------------------------------------

    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    # ---------------------------------------------------------
    # 2. Get the selected Subject inside that Batch
    # ---------------------------------------------------------

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    # ---------------------------------------------------------
    # 3. Identify the logged-in user's role
    # ---------------------------------------------------------

    is_admin = (
        request.user.is_staff
        or request.user.is_superuser
    )

    is_teacher = hasattr(
        request.user,
        "teacher_profile",
    )

    teacher = None

    if is_teacher:
        teacher = request.user.teacher_profile

    # ---------------------------------------------------------
    # 4. Handle POST requests
    # ---------------------------------------------------------

    if request.method == "POST":

        # -----------------------------------------------------
        # Create Chapter
        # -----------------------------------------------------

        if request.POST.get("action") == "create_chapter":

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
                "draft",
            )

            # -------------------------------------------------
            # Check permission
            # -------------------------------------------------

            if not is_admin and not is_teacher:

                messages.error(
                    request,
                    "You do not have permission to create a chapter.",
                    extra_tags="chapter-create",
                )

                return redirect(
                    "course_builder",
                    batch_id=batch.id,
                    subject_id=subject.id,
                )

            # -------------------------------------------------
            # Validate Chapter Name
            # -------------------------------------------------

            if not chapter_name:

                messages.error(
                    request,
                    "Chapter name is required.",
                    extra_tags="chapter-create",
                )

                return redirect(
                    "course_builder",
                    batch_id=batch.id,
                    subject_id=subject.id,
                )

            if len(chapter_name) > 255:

                messages.error(
                    request,
                    "Chapter name cannot exceed 255 characters.",
                    extra_tags="chapter-create",
                )

                return redirect(
                    "course_builder",
                    batch_id=batch.id,
                    subject_id=subject.id,
                )

            # -------------------------------------------------
            # Validate Chapter Description
            # -------------------------------------------------

            if not chapter_description:

                messages.error(
                    request,
                    "Chapter description is required.",
                    extra_tags="chapter-create",
                )

                return redirect(
                    "course_builder",
                    batch_id=batch.id,
                    subject_id=subject.id,
                )

            if len(chapter_description) > 255:

                messages.error(
                    request,
                    "Chapter description cannot exceed 255 characters.",
                    extra_tags="chapter-create",
                )

                return redirect(
                    "course_builder",
                    batch_id=batch.id,
                    subject_id=subject.id,
                )

            # -------------------------------------------------
            # Validate Status
            # -------------------------------------------------

            if status not in {
                "draft",
                "published",
            }:

                messages.error(
                    request,
                    "Invalid chapter status.",
                    extra_tags="chapter-create",
                )

                return redirect(
                    "course_builder",
                    batch_id=batch.id,
                    subject_id=subject.id,
                )

            # -------------------------------------------------
            # Get the next chapter order
            # -------------------------------------------------

            existing_chapters = CourseChapter.objects.filter(
                batch=batch,
                subject=subject,
                is_deleted=False,
            )

            chapter_order = get_next_order(
                existing_chapters,
                order_field="chapter_order",
                deleted_field="is_deleted",
            )

            # -------------------------------------------------
            # Set the creator and updater
            # -------------------------------------------------

            created_by = teacher if is_teacher else None
            created_by_admin = (
                request.user
                if is_admin
                else None
            )

            # -------------------------------------------------
            # Create the chapter
            # -------------------------------------------------

            chapter = CourseChapter.objects.create(
                batch=batch,
                subject=subject,

                chapter_name=chapter_name,
                chapter_description=chapter_description,
                chapter_order=chapter_order,
                status=status,

                created_by=created_by,
                created_by_admin=created_by_admin,

                updated_by=teacher if is_teacher else None,
                updated_by_admin=(
                    request.user
                    if is_admin
                    else None
                ),

                is_deleted=False,
            )

            # -------------------------------------------------
            # Create chapter timeline entry
            # -------------------------------------------------

            if is_teacher:

                changed_by = teacher
                changed_by_admin = None

                actor_name = (
                    teacher.full_name
                    or teacher.user.get_username()
                )

            else:

                changed_by = None
                changed_by_admin = request.user

                actor_name = (
                    request.user.get_full_name().strip()
                    or request.user.get_username()
                )

            ChapterChangeLog.objects.create(
                chapter=chapter,

                changed_by=changed_by,
                changed_by_admin=changed_by_admin,

                action="created",
                field_name="",

                old_value="",

                new_value=(
                    f"Chapter Name: {chapter.chapter_name}; "
                    f"Description: {chapter.chapter_description}; "
                    f"Order: {chapter.chapter_order}; "
                    f"Status: {chapter.status}"
                ),

                change_summary=(
                    f"{actor_name} created chapter "
                    f"'{chapter.chapter_name}' "
                    f"at order {chapter.chapter_order}."
                ),
            )

            # -------------------------------------------------
            # Success message
            # -------------------------------------------------

            messages.success(
                request,
                f"Chapter '{chapter.chapter_name}' "
                f"created successfully.",
            )

            # -------------------------------------------------
            # Redirect back to Course Builder
            # -------------------------------------------------

            return redirect(
                "course_builder",
                batch_id=batch.id,
                subject_id=subject.id,
            )

    # ---------------------------------------------------------
    # 5. Get active chapters
    # ---------------------------------------------------------

    chapters = CourseChapter.objects.filter(
        batch=batch,
        subject=subject,
        is_deleted=False,
    ).order_by(
        "chapter_order",
        "id",
    )

    # ---------------------------------------------------------
    # 6. Page context
    # ---------------------------------------------------------

    context = {
        "batch": batch,
        "subject": subject,

        "chapters": chapters,
        "chapter_count": chapters.count(),

        "is_admin": is_admin,
        "is_teacher": is_teacher,

        "teacher": teacher,
    }

    # ---------------------------------------------------------
    # 7. Render Course Builder
    # ---------------------------------------------------------

    return render(
        request,
        "courses/course_builder.html",
        context,
    )