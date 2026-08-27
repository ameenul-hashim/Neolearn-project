from django.shortcuts import render, redirect
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q, F
from django.db import transaction
from .decorators import admin_required
from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.core.mail import send_mail
from admins.models import (
    Teacher,
    Batch,
    Subject,
    TeacherBatch,
    TeacherSubject,
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
    DeletionAudit,
)
from django.http import JsonResponse
from datetime import datetime
from django.utils import timezone
from .validators import (validate_create_batch,validate_edit_batch,)
from .helpers import (create_batch,update_batch,build_batch_context,can_delete_batch,can_archive_batch,can_publish_batch,can_edit_batch,)
from cloudinary.uploader import destroy


@cache_control(no_cache=True,must_revalidate=True,no_store=True)
def admin_signin_view(request):

    # IF ALREADY LOGGED IN
    if request.user.is_authenticated:
        if (request.user.is_staff or request.user.is_superuser):
            return redirect('admin_dashboard')

    # POST METHOD

    if request.method == 'POST':
        email=request.POST.get('email')
        password=request.POST.get('password')

        # EMPTY FIELD CHECK
        if not email or not password:
            messages.error(request,'All fields are required.')
            return redirect('admin_signin')

        # EMAIL FORMAT CHECK
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request,'Enter a valid email address.')
            return redirect('admin_signin')

        # USER EXIST CHECK
        try:
            existing_user=User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request,'Admin account not found.')
            return redirect('admin_signin')

        # AUTHENTICATION
        user=authenticate(request,username=existing_user.username,password=password)

        # PASSWORD ERROR
        if user is None:
            messages.error(request,'Incorrect password.')
            return redirect('admin_signin')

        # STAFF / SUPERUSER CHECK
        if (not user.is_staff and  not user.is_superuser):
            messages.error(request,('Access denied. ''Admin login only.'))
            return redirect('admin_signin')

        # LOGIN
        login(request,user)
        messages.success(request,'Admin login successful.')
        return redirect('admin_dashboard')
    return render(request, "admins/admin_signin.html")


@cache_control(no_cache=True,must_revalidate=True,no_store=True)
@admin_required
def admin_dashboard_view(request):

    # BLOCK NORMAL USERS
    if (not request.user.is_staff and not request.user.is_superuser):
        messages.error(request,'Access denied.')
        return redirect('admin_signin')

    response = render(request, 'admins/dashboard/dashboard.html')

    response['Cache-Control']=('no-cache, no-store, must-revalidate')

    response['Pragma']='no-cache'

    response['Expires']='0'

    return response


@login_required(login_url='admin_signin')
def admin_logout_view(request):

    logout(request)

    request.session.flush()

    response = redirect('admin_signin')

    response.delete_cookie('sessionid')

    response.delete_cookie('csrftoken')

    messages.success(request,'Logged out successfully.')

    return response      


@cache_control(no_cache=True,must_revalidate=True,no_store=True)
@admin_required
def admin_students_view(request):

    # ADMIN CHECK
    if (not request.user.is_staff and not request.user.is_superuser):
        messages.error(request,'Access denied.')
        return redirect('admin_signin')
    # SEARCH

    search=request.GET.get('search','')

    # FILTER

    status=request.GET.get('status','all')

    # SORT

    sort=request.GET.get('sort','newest')

    students = User.objects.filter(is_staff=False,is_superuser=False,teacher_profile__isnull=True)

    # SEARCH FILTER

    if search:
        students=students.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search))

    # ACTIVE / INACTIVE

    if status=='active':
        students=students.filter(is_active=True)
    elif status=='inactive':
        students=students.filter(is_active=False)

    # SORTING

    if sort=='oldest':
        students=students.order_by('date_joined')
    elif sort=='a-z':
        students=students.order_by('username')
    elif sort=='z-a':
        students=students.order_by('-username')
    else:
        students=students.order_by('-date_joined')

    # PAGINATION

    paginator=Paginator(students,10)
    page_number=request.GET.get('page')
    page_obj=paginator.get_page(page_number)
    context={
        'page_obj':page_obj,
        'search':search,
        'status':status,
        'sort':sort,
    }

    return render(request, 'admins/students/students.html', context)



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def block_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.is_active=False
        user.save()
        messages.success(request,'Student blocked successfully.')
        return redirect('admin_students')
    return render(request,'admins/students/block_student.html',{'student': user})



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def unblock_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.is_active=True
        user.save()
        messages.success(request,'Student unblocked successfully.')
        return redirect('admin_students')

    return render(request,'admins/students/unblock_student.html',{'student': user})



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def delete_student_view(request,user_id):
    user=User.objects.get(id=user_id)
    if request.method=='POST':
        user.delete()
        messages.success(request,'Student deleted successfully.')
        return redirect('admin_students')

    return render(request,'admins/students/delete_student.html',{'student': user})



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def admin_batches_view(request):

    search = request.GET.get("search", "").strip()

    batches = Batch.objects.all().order_by("-id")

    if search:

        batches = batches.filter(
            Q(batch_name__icontains=search) |
            Q(batch_description__icontains=search))

    context = {"batches": batches,}

    return render(request,"admins/batches/batches.html",context,)


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def create_batch_view(request):

    context = build_batch_context()

    if request.method == "POST":

        try:

            cleaned_data = validate_create_batch(request)

            create_batch(cleaned_data)

            messages.success(
                request,
                "Batch created successfully."
            )

            return redirect(
                "admin_batches"
            )
        
        except ValidationError as e:

            messages.error(
                request,
                e.messages[0]
            )

            context["form_data"] = request.POST

            return render(
                request,
                "admins/batches/create_batch.html",
                context,
            )

        except Exception as e:

            import traceback
            traceback.print_exc()

            messages.error(
                request,
                str(e)
            )

            context["form_data"] = request.POST

            return render(
                request,
                "admins/batches/create_batch.html",
                context,
            )

    context["form_data"] = {}

    return render(
        request,
        "admins/batches/create_batch.html",
        context,
    )

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def edit_batch_view(request, batch_id):

    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    # ==========================================================
    # Temporary Student Count
    # Replace with actual enrollment count later
    # ==========================================================

    student_count = 0

    context = build_batch_context(
        batch=batch,
        extra_context={
            "student_count": student_count,
            "editable_fields": can_edit_batch(
                batch,
                student_count,
            ),
        },
    )

    if request.method == "POST":

        try:

            cleaned_data = validate_edit_batch(
                request=request,
                batch=batch,
                student_count=student_count,
            )

            update_batch(
                batch=batch,
                cleaned_data=cleaned_data,
            )

            messages.success(
                request,
                "Batch updated successfully.",
            )

            return redirect(
                "admin_batches",
            )

        except ValidationError as e:

            messages.error(
                request,
                e.messages[0],
            )

            context["form_data"] = request.POST

            return render(
                request,
                "admins/batches/edit_batch.html",
                context,
            )

        except Exception as e:

            import traceback
            traceback.print_exc()

            messages.error(
                request,
                str(e),
            )

            context["form_data"] = request.POST

            return render(
                request,
                "admins/batches/edit_batch.html",
                context,
            )

    context["form_data"] = batch

    return render(
        request,
        "admins/batches/edit_batch.html",
        context,
    )

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def batch_subjects(request, batch_id):

    batch = get_object_or_404(
        Batch,
        id=batch_id
    )

    search = request.GET.get("search", "").strip()

    subjects = Subject.objects.filter(
        batch=batch
    ).order_by("subject_name")

    if search:

        subjects = subjects.filter(
            subject_name__icontains=search
        )

    context = {

        "batch": batch,
        "subjects": subjects,
        "search": search,

    }

    return render(request,"admins/subjects/batch_subjects.html",context)



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def delete_batch_view(request, batch_id):

    batch = get_object_or_404(Batch, id=batch_id)

    if request.method == "POST":

        confirm_name = request.POST.get("confirm_name", "").strip()

        # =====================================================
        # Empty Validation
        # =====================================================

        if not confirm_name:

            messages.error(
                request,
                "Please enter the batch name to confirm deletion."
            )

            return render(
                request,
                "admins/batches/delete_batch.html",
                {
                    "batch": batch,
                },
            )

        # =====================================================
        # Batch Name Validation
        # =====================================================

        if confirm_name != batch.batch_name:

            messages.error(
                request,
                "Batch name does not match."
            )

            return render(
                request,
                "admins/batches/delete_batch.html",
                {
                    "batch": batch,
                },
            )

        # =====================================================
        # Archived Batch Validation
        # =====================================================

        if batch.batch_status == "archived":

            messages.error(
                request,
                "Archived batches cannot be deleted."
            )

            return redirect("admin_batches")

        # =====================================================
        # Student Enrollment Validation
        # =====================================================
        #
        # Add your enrollment/purchase check here later.
        #
        # Example:
        #
        # if StudentEnrollment.objects.filter(batch=batch).exists():
        #
        #     messages.error(
        #         request,
        #         "Students are already enrolled in this batch. Deletion is not allowed."
        #     )
        #
        #     return redirect("admin_batches")
        #
        # =====================================================

        # =====================================================
        # Delete Cloudinary Image (Safe)
        # =====================================================

        try:

            if batch.batch_thumbnail:

                public_id = getattr(
                    batch.batch_thumbnail,
                    "public_id",
                    None,
                )

                if public_id:
                    destroy(public_id)

        except Exception:
            # Ignore Cloudinary errors and continue deleting batch
            pass

        # =====================================================
        # Delete Batch
        # =====================================================

        batch.delete()

        messages.success(
            request,
            "Batch deleted successfully."
        )

        return redirect("admin_batches")

    return render(
        request,
        "admins/batches/delete_batch.html",
        {
            "batch": batch,
        },
    )


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def admin_subjects_view(request):

    search = request.GET.get("search", "").strip()
    selected_batch = request.GET.get("batch", "")
    batches = Batch.objects.order_by("batch_name")
    subjects = Subject.objects.select_related("batch").all()

    # Search
    if search:
        subjects = subjects.filter(
            subject_name__icontains=search
        )

    # Batch Filter
    if selected_batch:
        subjects = subjects.filter(
            batch_id=selected_batch
        )

    context = {
        "subjects": subjects,
        "batches": batches,
        "selected_batch": selected_batch,
        "search": search,
    }

    return render(request,"admins/subjects/subjects.html",context)


# ==========================================================
# ADMIN SUBJECT COURSE BUILDER
# ==========================================================

def _admin_builder_url(
    subject_id,
    chapter_id=None,
    view="overview",
    extra_params=None,
):
    """
    Build a URL back to the unified Admin Course Builder.
    """
    url = reverse(
        "admin_subject_course_builder",
        kwargs={"subject_id": subject_id},
    )

    params = []

    if chapter_id is not None:
        params.append(f"chapter={int(chapter_id)}")

    if view:
        params.append(f"view={view}")

    if extra_params:
        for key, value in extra_params.items():
            if value is not None:
                params.append(f"{key}={value}")

    return f"{url}?{'&'.join(params)}" if params else url


def _admin_actor_name(user):
    if not user:
        return "Admin"

    return (
        user.get_full_name().strip()
        or getattr(user, "username", "")
        or getattr(user, "email", "")
        or "Admin"
    )


def _teacher_actor_name(teacher):
    if not teacher:
        return "Teacher"

    return (
        getattr(teacher, "full_name", "")
        or getattr(getattr(teacher, "user", None), "username", "")
        or getattr(teacher, "email", "")
        or "Teacher"
    )


def _admin_display_actor(teacher=None, admin_user=None):
    if admin_user:
        return _admin_actor_name(admin_user), "admin"

    return _teacher_actor_name(teacher), "teacher"


def _get_admin_subject(subject_id):
    return get_object_or_404(
        Subject.objects.select_related("batch"),
        id=subject_id,
    )


def _get_admin_chapter(subject_id, chapter_id, include_deleted=False):
    subject = _get_admin_subject(subject_id)

    filters = {
        "id": chapter_id,
        "batch": subject.batch,
        "subject": subject,
    }

    if not include_deleted:
        filters["is_deleted"] = False

    chapter = get_object_or_404(
        CourseChapter,
        **filters,
    )

    return subject, subject.batch, chapter


def _get_admin_video(subject_id, chapter_id, video_id):
    subject, batch, chapter = _get_admin_chapter(
        subject_id,
        chapter_id,
    )

    video = get_object_or_404(
        ChapterVideo,
        id=video_id,
        chapter=chapter,
        is_deleted=False,
    )

    return subject, batch, chapter, video


def _get_admin_pdf(subject_id, chapter_id, pdf_id):
    subject, batch, chapter = _get_admin_chapter(
        subject_id,
        chapter_id,
    )

    pdf = get_object_or_404(
        ChapterPDF,
        id=pdf_id,
        chapter=chapter,
        is_deleted=False,
    )

    return subject, batch, chapter, pdf


def _get_admin_quiz(subject_id, chapter_id, quiz_id):
    subject, batch, chapter = _get_admin_chapter(
        subject_id,
        chapter_id,
    )

    quiz = get_object_or_404(
        ChapterQuiz.objects.prefetch_related("questions__options"),
        id=quiz_id,
        chapter=chapter,
        is_deleted=False,
    )

    return subject, batch, chapter, quiz


def _chapter_edit_state(request, chapter, error="", **overrides):
    request.session["chapter_edit_open"] = True
    request.session["chapter_edit_error"] = error
    request.session["chapter_edit_form"] = {
        "chapter_id": chapter.id,
        "chapter_name": overrides.get(
            "chapter_name",
            chapter.chapter_name or "",
        ),
        "chapter_description": overrides.get(
            "chapter_description",
            chapter.chapter_description or "",
        ),
        "status": overrides.get(
            "status",
            chapter.status or "",
        ),
    }
    request.session.modified = True


def _video_edit_state(request, video, error="", **overrides):
    request.session["video_edit_open"] = True
    request.session["video_edit_error"] = error
    request.session["video_edit_form"] = {
        "video_id": video.id,
        "video_name": overrides.get(
            "video_name",
            video.video_name or "",
        ),
        "video_description": overrides.get(
            "video_description",
            video.video_description or "",
        ),
        "video_order": str(
            overrides.get(
                "video_order",
                video.video_order,
            )
        ),
        "current_file_name": (
            getattr(video.video_file, "name", "") or ""
        ),
    }
    request.session.modified = True


def _pdf_thumbnail_url(pdf):
    if not pdf.pdf_thumbnail:
        return ""

    try:
        return pdf.pdf_thumbnail.url
    except Exception:
        return ""


def _pdf_edit_state(request, pdf, error="", **overrides):
    request.session["pdf_edit_open"] = True
    request.session["pdf_edit_error"] = error
    request.session["pdf_edit_form"] = {
        "pdf_id": pdf.id,
        "pdf_name": overrides.get(
            "pdf_name",
            pdf.pdf_name or "",
        ),
        "pdf_description": overrides.get(
            "pdf_description",
            pdf.pdf_description or "",
        ),
        "pdf_order": str(
            overrides.get(
                "pdf_order",
                pdf.pdf_order,
            )
        ),
        "current_file_name": (
            getattr(pdf.pdf_file, "name", "") or ""
        ),
        "current_thumbnail_url": _pdf_thumbnail_url(pdf),
    }
    request.session.modified = True


def _clear_session_keys(request, *keys):
    for key in keys:
        request.session.pop(key, None)
    request.session.modified = True


def _validate_mp4(video_file):
    if not video_file:
        return False, "Please select a valid MP4 video file."

    if getattr(video_file, "size", 0) <= 0:
        return False, "The selected video file is empty."

    filename = (
        getattr(video_file, "name", "") or ""
    ).strip().lower()

    if not filename.endswith(".mp4"):
        return False, "Invalid video format. Only MP4 video files are allowed."

    content_type = (
        getattr(video_file, "content_type", "") or ""
    ).strip().lower()

    rejected = {
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

    if content_type in rejected:
        return False, "The selected file is not a valid MP4 video."

    return True, ""


def _validate_pdf_file(pdf_file):
    if not pdf_file:
        return False, "Please select a PDF file."

    if getattr(pdf_file, "size", 0) <= 0:
        return False, "The selected PDF file is empty."

    filename = (
        getattr(pdf_file, "name", "") or ""
    ).strip().lower()

    if not filename.endswith(".pdf"):
        return False, "Invalid PDF format. Only PDF files are allowed."

    content_type = (
        getattr(pdf_file, "content_type", "") or ""
    ).strip().lower()

    rejected = {
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

    if content_type in rejected:
        return False, "The selected file is not a valid PDF document."

    return True, ""


def _validate_pdf_thumbnail(pdf_thumbnail):
    if not pdf_thumbnail:
        return True, ""

    filename = (
        getattr(pdf_thumbnail, "name", "") or ""
    ).strip().lower()

    extension = (
        "." + filename.rsplit(".", 1)[1]
        if "." in filename
        else ""
    )

    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        return False, (
            "Invalid thumbnail format. Only PNG, JPG, JPEG, and WEBP images are allowed."
        )

    if getattr(pdf_thumbnail, "size", 0) <= 0:
        return False, "The selected thumbnail image is empty."

    content_type = (
        getattr(pdf_thumbnail, "content_type", "") or ""
    ).strip().lower()

    if content_type and content_type not in {
        "image/png",
        "image/jpeg",
        "image/webp",
    }:
        return False, (
            "The selected thumbnail is not a valid image. Use PNG, JPG, JPEG, or WEBP."
        )

    return True, ""


def _record_chapter_admin_log(
    chapter,
    action,
    field_name,
    old_value,
    new_value,
    summary,
    admin_user,
):
    ChapterChangeLog.objects.create(
        chapter=chapter,
        changed_by=None,
        changed_by_admin=admin_user,
        action=action,
        field_name=field_name,
        old_value=str(old_value or ""),
        new_value=str(new_value or ""),
        change_summary=summary,
    )


def _record_video_admin_log(
    video,
    action,
    field_name,
    old_value,
    new_value,
    summary,
    admin_user,
):
    VideoChangeLog.objects.create(
        video=video,
        changed_by=None,
        changed_by_admin=admin_user,
        action=action,
        field_name=field_name,
        old_value=str(old_value or ""),
        new_value=str(new_value or ""),
        change_summary=summary,
    )


def _record_pdf_admin_log(
    pdf,
    action,
    field_name,
    old_value,
    new_value,
    summary,
    admin_user,
):
    PDFChangeLog.objects.create(
        pdf=pdf,
        changed_by=None,
        changed_by_admin=admin_user,
        action=action,
        field_name=field_name,
        old_value=str(old_value or ""),
        new_value=str(new_value or ""),
        change_summary=summary,
    )


def _record_quiz_admin_log(
    quiz,
    action,
    field_name,
    old_value,
    new_value,
    summary,
    admin_user,
):
    QuizChangeLog.objects.create(
        quiz=quiz,
        changed_by=None,
        changed_by_admin=admin_user,
        action=action,
        field_name=field_name,
        old_value=str(old_value or ""),
        new_value=str(new_value or ""),
        change_summary=summary,
    )

# ==========================================================
# ADMIN COURSE BUILDER — MANAGEMENT ONLY
# ==========================================================
#
# Admin is NOT a content creator in this workspace.
#
# Allowed:
#   - View teacher-created content
#   - Edit existing content
#   - View shared timelines
#   - Directly delete content with a required reason
#   - Review teacher delete requests
#   - Approve / reject teacher delete requests
#   - View the common permanent Deletion Audit
#
# Not allowed from this workspace:
#   - Create chapter
#   - Upload/create video
#   - Upload/create PDF
#   - Create quiz
#   - Schedule live class
#
# ==========================================================


def _admin_builder_url(subject_id, chapter_id=None, view="overview", extra_params=None):
    url = reverse("admin_subject_course_builder", kwargs={"subject_id": subject_id})
    params = []
    if chapter_id is not None:
        params.append(f"chapter={int(chapter_id)}")
    if view:
        params.append(f"view={view}")
    if extra_params:
        for key, value in extra_params.items():
            if value is not None and value != "":
                params.append(f"{key}={value}")
    return f"{url}?{'&'.join(params)}" if params else url


def _admin_actor_name(user):
    if not user:
        return "Admin"
    return user.get_full_name().strip() or getattr(user, "username", "") or getattr(user, "email", "") or "Admin"


def _teacher_actor_name(teacher):
    if not teacher:
        return "Teacher"
    return getattr(teacher, "full_name", "") or getattr(getattr(teacher, "user", None), "username", "") or getattr(teacher, "email", "") or "Teacher"


def _admin_display_actor(teacher=None, admin_user=None):
    if admin_user:
        return _admin_actor_name(admin_user), "admin"
    return _teacher_actor_name(teacher), "teacher"


def _get_admin_subject(subject_id):
    return get_object_or_404(Subject.objects.select_related("batch"), id=subject_id)


def _get_admin_chapter(subject_id, chapter_id, include_deleted=False):
    subject = _get_admin_subject(subject_id)
    filters = {"id": chapter_id, "batch": subject.batch, "subject": subject}
    if not include_deleted:
        filters["is_deleted"] = False
    return subject, subject.batch, get_object_or_404(CourseChapter, **filters)


def _get_admin_video(subject_id, chapter_id, video_id, include_deleted=False):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id, include_deleted=False)
    filters = {"id": video_id, "chapter": chapter}
    if not include_deleted:
        filters["is_deleted"] = False
    return subject, batch, chapter, get_object_or_404(ChapterVideo, **filters)


def _get_admin_pdf(subject_id, chapter_id, pdf_id, include_deleted=False):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id, include_deleted=False)
    filters = {"id": pdf_id, "chapter": chapter}
    if not include_deleted:
        filters["is_deleted"] = False
    return subject, batch, chapter, get_object_or_404(ChapterPDF, **filters)


def _get_admin_quiz(subject_id, chapter_id, quiz_id, include_deleted=False):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id, include_deleted=False)
    filters = {"id": quiz_id, "chapter": chapter}
    if not include_deleted:
        filters["is_deleted"] = False
    quiz = get_object_or_404(ChapterQuiz.objects.prefetch_related("questions__options"), **filters)
    return subject, batch, chapter, quiz


def _chapter_edit_state(request, chapter, error="", **overrides):
    request.session["chapter_edit_open"] = True
    request.session["chapter_edit_error"] = error
    request.session["chapter_edit_form"] = {
        "chapter_id": chapter.id,
        "chapter_name": overrides.get("chapter_name", chapter.chapter_name or ""),
        "chapter_description": overrides.get("chapter_description", chapter.chapter_description or ""),
        "status": overrides.get("status", chapter.status or ""),
    }
    request.session.modified = True


def _video_edit_state(request, video, error="", **overrides):
    request.session["video_edit_open"] = True
    request.session["video_edit_error"] = error
    request.session["video_edit_form"] = {
        "video_id": video.id,
        "video_name": overrides.get("video_name", video.video_name or ""),
        "video_description": overrides.get("video_description", video.video_description or ""),
        "video_order": str(overrides.get("video_order", video.video_order)),
        "current_file_name": getattr(video.video_file, "name", "") or "",
    }
    request.session.modified = True


def _pdf_thumbnail_url(pdf):
    if not pdf.pdf_thumbnail:
        return ""
    try:
        return pdf.pdf_thumbnail.url
    except Exception:
        return ""


def _pdf_edit_state(request, pdf, error="", **overrides):
    request.session["pdf_edit_open"] = True
    request.session["pdf_edit_error"] = error
    request.session["pdf_edit_form"] = {
        "pdf_id": pdf.id,
        "pdf_name": overrides.get("pdf_name", pdf.pdf_name or ""),
        "pdf_description": overrides.get("pdf_description", pdf.pdf_description or ""),
        "pdf_order": str(overrides.get("pdf_order", pdf.pdf_order)),
        "current_file_name": getattr(pdf.pdf_file, "name", "") or "",
        "current_thumbnail_url": _pdf_thumbnail_url(pdf),
    }
    request.session.modified = True


def _clear_session_keys(request, *keys):
    for key in keys:
        request.session.pop(key, None)
    request.session.modified = True


def _validate_mp4(video_file):
    if not video_file or getattr(video_file, "size", 0) <= 0:
        return False, "Please select a valid MP4 video file."
    filename = (getattr(video_file, "name", "") or "").strip().lower()
    if not filename.endswith(".mp4"):
        return False, "Invalid video format. Only MP4 video files are allowed."
    content_type = (getattr(video_file, "content_type", "") or "").strip().lower()
    if content_type in {"text/plain", "text/html", "application/pdf", "application/zip", "image/jpeg", "image/png", "image/gif", "audio/mpeg", "audio/mp3", "audio/wav"}:
        return False, "The selected file is not a valid MP4 video."
    return True, ""


def _validate_pdf_file(pdf_file):
    if not pdf_file or getattr(pdf_file, "size", 0) <= 0:
        return False, "Please select a PDF file."
    filename = (getattr(pdf_file, "name", "") or "").strip().lower()
    if not filename.endswith(".pdf"):
        return False, "Invalid PDF format. Only PDF files are allowed."
    content_type = (getattr(pdf_file, "content_type", "") or "").strip().lower()
    if content_type in {"image/jpeg", "image/png", "image/gif", "image/webp", "video/mp4", "audio/mpeg", "audio/wav", "application/zip", "application/x-zip-compressed", "text/plain", "text/html"}:
        return False, "The selected file is not a valid PDF document."
    return True, ""


def _validate_pdf_thumbnail(pdf_thumbnail):
    if not pdf_thumbnail:
        return True, ""
    filename = (getattr(pdf_thumbnail, "name", "") or "").strip().lower()
    extension = "." + filename.rsplit(".", 1)[1] if "." in filename else ""
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        return False, "Invalid thumbnail format. Only PNG, JPG, JPEG, and WEBP images are allowed."
    if getattr(pdf_thumbnail, "size", 0) <= 0:
        return False, "The selected thumbnail image is empty."
    return True, ""


def _record_chapter_admin_log(chapter, action, field_name, old_value, new_value, summary, admin_user):
    return ChapterChangeLog.objects.create(
        chapter=chapter, changed_by=None, changed_by_admin=admin_user,
        action=action, field_name=field_name,
        old_value=str(old_value or ""), new_value=str(new_value or ""),
        change_summary=summary,
    )


def _record_video_admin_log(video, action, field_name, old_value, new_value, summary, admin_user):
    return VideoChangeLog.objects.create(
        video=video, changed_by=None, changed_by_admin=admin_user,
        action=action, field_name=field_name,
        old_value=str(old_value or ""), new_value=str(new_value or ""),
        change_summary=summary,
    )


def _record_pdf_admin_log(pdf, action, field_name, old_value, new_value, summary, admin_user):
    return PDFChangeLog.objects.create(
        pdf=pdf, changed_by=None, changed_by_admin=admin_user,
        action=action, field_name=field_name,
        old_value=str(old_value or ""), new_value=str(new_value or ""),
        change_summary=summary,
    )


def _record_quiz_admin_log(quiz, action, field_name, old_value, new_value, summary, admin_user):
    return QuizChangeLog.objects.create(
        quiz=quiz, changed_by=None, changed_by_admin=admin_user,
        action=action, field_name=field_name,
        old_value=str(old_value or ""), new_value=str(new_value or ""),
        change_summary=summary,
    )


# ==========================================================
# DELETION AUDIT HELPERS
# ==========================================================

def _content_snapshot(content_type, obj):
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


def _sync_pending_deletion_audits(subject):
    batch = subject.batch
    audits = []

    chapters = CourseChapter.objects.filter(
        batch=batch, subject=subject, is_deleted=False,
        delete_requested=True, delete_status="pending",
    ).select_related("created_by", "created_by_admin", "delete_requested_by")
    for obj in chapters:
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


def _delete_storage_file(field):
    try:
        if field:
            field.delete(save=False)
    except Exception as exc:
        print("Storage cleanup warning:", exc)


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


def _get_admin_subject_by_names(subject_name, batch_name):
    if not subject_name:
        return None
    return Subject.objects.select_related("batch").filter(subject_name=subject_name, batch__batch_name=batch_name).first()


def _get_admin_subject_from_object(obj, content_type):
    chapter = obj if content_type == "chapter" else getattr(obj, "chapter", None)
    if chapter:
        return Subject.objects.select_related("batch").get(id=chapter.subject_id)
    return None


def _timeline_entry(log, teacher_attr="changed_by", admin_attr="changed_by_admin"):
    teacher = getattr(log, teacher_attr, None)
    admin_user = getattr(log, admin_attr, None)
    actor_name, actor_type = _admin_display_actor(teacher, admin_user)
    return {
        "id": log.id,
        "actor_name": actor_name,
        "actor_type": actor_type,
        "action": log.get_action_display(),
        "action_key": log.action,
        "field_name": log.field_name,
        "old_value": log.old_value,
        "new_value": log.new_value,
        "summary": log.change_summary,
        "changed_at": log.changed_at,
    }


# ==========================================================
# ADMIN SUBJECT COURSE BUILDER
# ==========================================================

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def admin_subject_course_builder_view(request, subject_id):
    subject = _get_admin_subject(subject_id)
    batch = subject.batch

    allowed_views = {
        "overview", "videos", "pdfs", "quizzes", "live",
        "delete_requests", "audit", "chapter_timeline",
        "video_timeline", "pdf_timeline", "quiz_timeline",
    }
    selected_content = (request.GET.get("view") or request.GET.get("content") or "overview").strip().lower()
    if selected_content not in allowed_views:
        selected_content = "overview"

    chapters = CourseChapter.objects.filter(batch=batch, subject=subject, is_deleted=False).select_related("created_by", "created_by_admin", "updated_by", "updated_by_admin").order_by("chapter_order", "id")
    selected_chapter = None
    raw_chapter = (request.GET.get("chapter") or "").strip()
    if raw_chapter.isdigit():
        selected_chapter = chapters.filter(id=int(raw_chapter)).first()
    if selected_chapter is None:
        selected_chapter = chapters.first()

    videos = ChapterVideo.objects.none()
    pdfs = ChapterPDF.objects.none()
    quizzes = ChapterQuiz.objects.none()
    if selected_chapter:
        videos = ChapterVideo.objects.filter(chapter=selected_chapter, is_deleted=False).select_related("created_by", "created_by_admin", "updated_by", "updated_by_admin").order_by("video_order", "id")
        pdfs = ChapterPDF.objects.filter(chapter=selected_chapter, is_deleted=False).select_related("created_by", "created_by_admin", "updated_by", "updated_by_admin").order_by("pdf_order", "id")
        quizzes = ChapterQuiz.objects.filter(chapter=selected_chapter, is_deleted=False).select_related("created_by", "created_by_admin", "updated_by", "updated_by_admin").prefetch_related("questions__options").order_by("created_at", "id")

    raw_video = (request.GET.get("video") or "").strip()
    raw_pdf = (request.GET.get("pdf") or "").strip()
    raw_quiz = (request.GET.get("quiz") or "").strip()
    selected_video = videos.filter(id=int(raw_video)).first() if raw_video.isdigit() else None
    selected_pdf = pdfs.filter(id=int(raw_pdf)).first() if raw_pdf.isdigit() else None
    selected_quiz = quizzes.filter(id=int(raw_quiz)).first() if raw_quiz.isdigit() else None

    chapter_timeline_entries = []
    video_timeline_entries = []
    pdf_timeline_entries = []
    quiz_timeline_entries = []
    if selected_chapter and selected_content == "chapter_timeline":
        chapter_timeline_entries = [_timeline_entry(x) for x in ChapterChangeLog.objects.filter(chapter=selected_chapter).select_related("changed_by", "changed_by_admin").order_by("-changed_at", "-id")]
    if selected_video and selected_content == "video_timeline":
        video_timeline_entries = [_timeline_entry(x) for x in VideoChangeLog.objects.filter(video=selected_video).select_related("changed_by", "changed_by_admin").order_by("-changed_at", "-id")]
    if selected_pdf and selected_content == "pdf_timeline":
        pdf_timeline_entries = [_timeline_entry(x) for x in PDFChangeLog.objects.filter(pdf=selected_pdf).select_related("changed_by", "changed_by_admin").order_by("-changed_at", "-id")]
    if selected_quiz and selected_content == "quiz_timeline":
        quiz_timeline_entries = [_timeline_entry(x) for x in QuizChangeLog.objects.filter(quiz=selected_quiz).select_related("changed_by", "changed_by_admin").order_by("-changed_at", "-id")]

    _sync_pending_deletion_audits(subject)
    audit_qs = DeletionAudit.objects.filter(batch_name=batch.batch_name, subject_name=subject.subject_name).select_related("created_by_teacher", "created_by_admin", "delete_requested_by_teacher", "decision_by_admin", "deleted_by_admin").order_by("-created_at", "-id")

    audit_type = (request.GET.get("audit_type") or "all").strip().lower()
    audit_status = (request.GET.get("audit_status") or "all").strip().lower()
    audit_search = (request.GET.get("audit_search") or "").strip()
    if audit_type in {"chapter", "video", "pdf", "quiz"}:
        audit_qs = audit_qs.filter(content_type=audit_type)
    if audit_status in {"pending", "approved", "rejected", "deleted"}:
        audit_qs = audit_qs.filter(status=audit_status)
    if audit_search:
        audit_qs = audit_qs.filter(Q(content_name__icontains=audit_search) | Q(chapter_name__icontains=audit_search))

    delete_requests = list(audit_qs.filter(status="pending"))
    all_audits = list(audit_qs)

    assigned_teachers = TeacherSubject.objects.filter(batch=batch, subject=subject, is_active=True).select_related("teacher").order_by("teacher__full_name", "teacher__id")

    context = {
        "subject": subject, "batch": batch,
        "chapters": chapters, "selected_chapter": selected_chapter,
        "videos": videos, "pdfs": pdfs, "quizzes": quizzes,
        "selected_video": selected_video, "selected_pdf": selected_pdf, "selected_quiz": selected_quiz,
        "assigned_teachers": assigned_teachers,
        "selected_content": selected_content,
        "selected_content_title": selected_content.replace("_", " ").title(),
        "chapter_count": chapters.count(), "video_count": videos.count(), "pdf_count": pdfs.count(), "quiz_count": quizzes.count(),
        "subject_chapter_count": chapters.count(),
        "subject_video_count": ChapterVideo.objects.filter(chapter__batch=batch, chapter__subject=subject, chapter__is_deleted=False, is_deleted=False).count(),
        "subject_pdf_count": ChapterPDF.objects.filter(chapter__batch=batch, chapter__subject=subject, chapter__is_deleted=False, is_deleted=False).count(),
        "subject_quiz_count": ChapterQuiz.objects.filter(chapter__batch=batch, chapter__subject=subject, chapter__is_deleted=False, is_deleted=False).count(),
        "quiz_question_count": QuizQuestion.objects.filter(quiz__chapter=selected_chapter, quiz__is_deleted=False).count() if selected_chapter else 0,
        "chapter_creator_name": _admin_display_actor(selected_chapter.created_by, selected_chapter.created_by_admin)[0] if selected_chapter else "",
        "chapter_updater_name": _admin_display_actor(selected_chapter.updated_by, selected_chapter.updated_by_admin)[0] if selected_chapter else "",
        "video_creator_names": {x.id: _admin_display_actor(x.created_by, x.created_by_admin)[0] for x in videos},
        "video_updater_names": {x.id: _admin_display_actor(x.updated_by, x.updated_by_admin)[0] for x in videos},
        "pdf_creator_names": {x.id: _admin_display_actor(x.created_by, x.created_by_admin)[0] for x in pdfs},
        "pdf_updater_names": {x.id: _admin_display_actor(x.updated_by, x.updated_by_admin)[0] for x in pdfs},
        "quiz_creator_names": {x.id: _admin_display_actor(x.created_by, x.created_by_admin)[0] for x in quizzes},
        "quiz_updater_names": {x.id: _admin_display_actor(x.updated_by, x.updated_by_admin)[0] for x in quizzes},
        "chapter_timeline_entries": chapter_timeline_entries,
        "video_timeline_entries": video_timeline_entries,
        "pdf_timeline_entries": pdf_timeline_entries,
        "quiz_timeline_entries": quiz_timeline_entries,
        "timeline_entries": chapter_timeline_entries or video_timeline_entries or pdf_timeline_entries or quiz_timeline_entries,
        "timeline_count": len(chapter_timeline_entries or video_timeline_entries or pdf_timeline_entries or quiz_timeline_entries),
        "delete_requests": delete_requests,
        "pending_delete_count": len(delete_requests),
        "audit_entries": all_audits,
        "audit_count": len(all_audits),
        "audit_type": audit_type,
        "audit_status": audit_status,
        "audit_search": audit_search,
        "admin_user": request.user,
        # Existing edit UI state remains compatible with the current template.
        "chapter_edit_open": request.session.pop("chapter_edit_open", False),
        "chapter_edit_error": request.session.pop("chapter_edit_error", ""),
        "chapter_edit_form": request.session.pop("chapter_edit_form", {}),
        "video_edit_open": request.session.pop("video_edit_open", False),
        "video_edit_error": request.session.pop("video_edit_error", ""),
        "video_edit_form": request.session.pop("video_edit_form", {}),
        "pdf_edit_open": request.session.pop("pdf_edit_open", False),
        "pdf_edit_error": request.session.pop("pdf_edit_error", ""),
        "pdf_edit_form": request.session.pop("pdf_edit_form", {}),
        # Creation state is intentionally disabled.
        "video_upload_open": False, "video_upload_error": "", "video_upload_form": {},
        "pdf_upload_open": False, "pdf_upload_error": "", "pdf_upload_form": {},
        "quiz_create_open": False, "quiz_create_error": "", "quiz_create_form": {},
        "quiz_question_open": False, "quiz_question_error": "", "quiz_question_form": {}, "quiz_question_quiz_id": "",
    }
    request.session.modified = True
    return render(request, "admins/course_builder/admin_course_builder.html", context)


# ==========================================================
# ADMIN CREATION ENDPOINTS — HARD DISABLED
# ==========================================================
# Kept temporarily so old URLs cannot accidentally create content.
# They will be removed from admin/urls.py in the next stage.

@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_create_chapter_view(request, subject_id):
    messages.error(request, "Admin chapter creation is disabled. Chapters are created by teachers.")
    return redirect(_admin_builder_url(subject_id, view="overview"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_upload_video_view(request, subject_id, chapter_id):
    messages.error(request, "Admin video upload is disabled. Videos are added by teachers.")
    return redirect(_admin_builder_url(subject_id, chapter_id, view="videos"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_upload_pdf_view(request, subject_id, chapter_id):
    messages.error(request, "Admin PDF upload is disabled. PDFs are added by teachers.")
    return redirect(_admin_builder_url(subject_id, chapter_id, view="pdfs"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_create_quiz_view(request, subject_id, chapter_id):
    messages.error(request, "Admin quiz creation is disabled. Quizzes are created by teachers.")
    return redirect(_admin_builder_url(subject_id, chapter_id, view="quizzes"))


# ==========================================================
# ADMIN CHAPTER — EDIT
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_edit_chapter_view(request, subject_id, chapter_id):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id)
    if request.method == "GET":
        _chapter_edit_state(request, chapter)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))
    if request.method != "POST":
        messages.error(request, "Invalid chapter edit request.")
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))

    new_name = (request.POST.get("chapter_name") or "").strip()
    new_description = (request.POST.get("chapter_description") or "").strip()
    new_status = (request.POST.get("status") or "").strip().lower()
    if not new_name or len(new_name) > 255:
        _chapter_edit_state(request, chapter, "Chapter name is required and must be 255 characters or fewer.", chapter_name=new_name, chapter_description=new_description, status=new_status)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))
    if not new_description or len(new_description) > 255:
        _chapter_edit_state(request, chapter, "Chapter description is required and must be 255 characters or fewer.", chapter_name=new_name, chapter_description=new_description, status=new_status)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))
    if new_status not in {value for value, _ in CourseChapter.STATUS_CHOICES}:
        _chapter_edit_state(request, chapter, "Invalid chapter status selected.", chapter_name=new_name, chapter_description=new_description, status=new_status)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))
    if CourseChapter.objects.filter(batch=batch, subject=subject, chapter_name__iexact=new_name, is_deleted=False).exclude(id=chapter.id).exists():
        _chapter_edit_state(request, chapter, "A chapter with this name already exists in this subject.", chapter_name=new_name, chapter_description=new_description, status=new_status)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))

    old_name, old_description, old_status = chapter.chapter_name or "", chapter.chapter_description or "", chapter.status or ""
    with transaction.atomic():
        chapter.chapter_name = new_name
        chapter.chapter_description = new_description
        chapter.status = new_status
        chapter.updated_by = None
        chapter.updated_by_admin = request.user
        chapter.save()
        if old_name != new_name:
            _record_chapter_admin_log(chapter, "name_changed", "chapter_name", old_name, new_name, "Chapter name was updated by Admin.", request.user)
        if old_description != new_description:
            _record_chapter_admin_log(chapter, "updated", "chapter_description", old_description, new_description, "Chapter description was updated by Admin.", request.user)
        if old_status != new_status:
            _record_chapter_admin_log(chapter, "status_changed", "status", old_status, new_status, "Chapter status was updated by Admin.", request.user)
    _clear_session_keys(request, "chapter_edit_open", "chapter_edit_error", "chapter_edit_form")
    messages.success(request, f'Chapter "{chapter.chapter_name}" updated successfully.')
    return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))


# ==========================================================
# ADMIN VIDEO — VIEW / PLAY
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
def admin_play_video_view(request, subject_id, chapter_id, video_id):
    subject, batch, chapter, video = _get_admin_video(subject_id, chapter_id, video_id)
    return redirect(_admin_builder_url(subject.id, chapter.id, view="videos", extra_params={"video": video.id}))


# ==========================================================
# ADMIN VIDEO — EDIT
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_edit_video_view(request, subject_id, chapter_id, video_id):
    subject, batch, chapter, video = _get_admin_video(subject_id, chapter_id, video_id)
    if request.method == "GET":
        _video_edit_state(request, video)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="videos", extra_params={"video": video.id}))
    if request.method != "POST":
        messages.error(request, "Invalid video edit request.")
        return redirect(_admin_builder_url(subject.id, chapter.id, view="videos"))

    old_name, old_description, old_order = video.video_name or "", video.video_description or "", video.video_order
    old_file_name = getattr(video.video_file, "name", "") or ""
    new_name = (request.POST.get("video_name") or "").strip()
    new_description = (request.POST.get("video_description") or "").strip()
    order_raw = (request.POST.get("video_order") or "").strip()
    replacement_file = request.FILES.get("video_file")
    def error(message):
        _video_edit_state(request, video, message, video_name=new_name, video_description=new_description, video_order=order_raw or old_order)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="videos", extra_params={"video": video.id}))
    if not new_name or len(new_name) > 255:
        return error("Video name is required and must be 255 characters or fewer.")
    if ChapterVideo.objects.filter(chapter=chapter, video_name__iexact=new_name, is_deleted=False).exclude(id=video.id).exists():
        return error("A video with this name already exists in this chapter.")
    if not new_description or len(new_description) > 5000:
        return error("Video description is required and must be 5000 characters or fewer.")
    if not order_raw.isdigit() or int(order_raw) <= 0:
        return error("Video order must be a positive whole number.")
    new_order = int(order_raw)
    current_count = ChapterVideo.objects.filter(chapter=chapter, is_deleted=False).count()
    if new_order > current_count:
        return error(f"Video order must be between 1 and {current_count}.")
    if replacement_file:
        valid, msg = _validate_mp4(replacement_file)
        if not valid:
            return error(msg)

    with transaction.atomic():
        video.video_name = new_name
        video.video_description = new_description
        video.video_order = new_order
        video.updated_by = None
        video.updated_by_admin = request.user
        if replacement_file:
            video.video_file = replacement_file
        video.save()
        if old_name != new_name:
            _record_video_admin_log(video, "name_changed", "video_name", old_name, new_name, "Video name was updated by Admin.", request.user)
        if old_description != new_description:
            _record_video_admin_log(video, "description_changed", "video_description", old_description, new_description, "Video description was updated by Admin.", request.user)
        if old_order != new_order:
            _record_video_admin_log(video, "order_changed", "video_order", old_order, new_order, "Video order was updated by Admin.", request.user)
        if replacement_file:
            _record_video_admin_log(video, "file_changed", "video_file", old_file_name, getattr(video.video_file, "name", ""), "Video file was replaced by Admin.", request.user)
    _clear_session_keys(request, "video_edit_open", "video_edit_error", "video_edit_form")
    messages.success(request, f'Video "{video.video_name}" updated successfully.')
    return redirect(_admin_builder_url(subject.id, chapter.id, view="videos", extra_params={"video": video.id}))


# ==========================================================
# ADMIN PDF — VIEW / OPEN
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
def admin_open_pdf_view(request, subject_id, chapter_id, pdf_id):
    subject, batch, chapter, pdf = _get_admin_pdf(subject_id, chapter_id, pdf_id)
    return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs", extra_params={"pdf": pdf.id}))


# ==========================================================
# ADMIN PDF — EDIT
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_edit_pdf_view(request, subject_id, chapter_id, pdf_id):
    subject, batch, chapter, pdf = _get_admin_pdf(subject_id, chapter_id, pdf_id)
    if request.method == "GET":
        _pdf_edit_state(request, pdf)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs", extra_params={"pdf": pdf.id}))
    if request.method != "POST":
        messages.error(request, "Invalid PDF edit request.")
        return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs"))

    old_name, old_description, old_order = pdf.pdf_name or "", pdf.pdf_description or "", pdf.pdf_order
    old_file_name = getattr(pdf.pdf_file, "name", "") or ""
    old_thumbnail_name = getattr(pdf.pdf_thumbnail, "name", "") or ""
    new_name = (request.POST.get("pdf_name") or "").strip()
    new_description = (request.POST.get("pdf_description") or "").strip()
    order_raw = (request.POST.get("pdf_order") or "").strip()
    replacement_file = request.FILES.get("pdf_file")
    replacement_thumbnail = request.FILES.get("pdf_thumbnail")
    def error(message):
        _pdf_edit_state(request, pdf, message, pdf_name=new_name, pdf_description=new_description, pdf_order=order_raw or old_order)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs", extra_params={"pdf": pdf.id}))
    if not new_name or len(new_name) > 255:
        return error("PDF name is required and must be 255 characters or fewer.")
    if ChapterPDF.objects.filter(chapter=chapter, pdf_name__iexact=new_name, is_deleted=False).exclude(id=pdf.id).exists():
        return error("A PDF with this name already exists in this chapter.")
    if not new_description or len(new_description) > 5000:
        return error("PDF description is required and must be 5000 characters or fewer.")
    if not order_raw.isdigit() or int(order_raw) <= 0:
        return error("PDF order must be a positive whole number.")
    new_order = int(order_raw)
    current_count = ChapterPDF.objects.filter(chapter=chapter, is_deleted=False).count()
    if new_order > current_count:
        return error(f"PDF order must be between 1 and {current_count}.")
    if replacement_file:
        valid, msg = _validate_pdf_file(replacement_file)
        if not valid:
            return error(msg)
    if replacement_thumbnail:
        valid, msg = _validate_pdf_thumbnail(replacement_thumbnail)
        if not valid:
            return error(msg)

    with transaction.atomic():
        pdf.pdf_name = new_name
        pdf.pdf_description = new_description
        pdf.pdf_order = new_order
        pdf.updated_by = None
        pdf.updated_by_admin = request.user
        if replacement_file:
            pdf.pdf_file = replacement_file
        if replacement_thumbnail:
            pdf.pdf_thumbnail = replacement_thumbnail
        pdf.save()
        if old_name != new_name:
            _record_pdf_admin_log(pdf, "name_changed", "pdf_name", old_name, new_name, "PDF name was updated by Admin.", request.user)
        if old_description != new_description:
            _record_pdf_admin_log(pdf, "description_changed", "pdf_description", old_description, new_description, "PDF description was updated by Admin.", request.user)
        if old_order != new_order:
            _record_pdf_admin_log(pdf, "order_changed", "pdf_order", old_order, new_order, "PDF order was updated by Admin.", request.user)
        if replacement_file:
            _record_pdf_admin_log(pdf, "file_changed", "pdf_file", old_file_name, getattr(pdf.pdf_file, "name", ""), "PDF file was replaced by Admin.", request.user)
        if replacement_thumbnail:
            _record_pdf_admin_log(pdf, "thumbnail_changed", "pdf_thumbnail", old_thumbnail_name, getattr(pdf.pdf_thumbnail, "name", ""), "PDF thumbnail was replaced by Admin.", request.user)
    _clear_session_keys(request, "pdf_edit_open", "pdf_edit_error", "pdf_edit_form")
    messages.success(request, f'PDF "{pdf.pdf_name}" updated successfully.')
    return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs", extra_params={"pdf": pdf.id}))


# ==========================================================
# ADMIN QUIZ — VIEW
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
def admin_view_quiz_view(request, subject_id, chapter_id, quiz_id):
    subject, batch, chapter, quiz = _get_admin_quiz(subject_id, chapter_id, quiz_id)
    return redirect(_admin_builder_url(subject.id, chapter.id, view="quizzes", extra_params={"quiz": quiz.id}))


# ==========================================================
# ADMIN QUIZ — EDIT EXISTING QUIZ
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_edit_quiz_view(request, subject_id, chapter_id, quiz_id):
    subject, batch, chapter, quiz = _get_admin_quiz(subject_id, chapter_id, quiz_id)
    base = {"chapter": chapter.id, "view": "quizzes", "quiz": quiz.id, "quiz_mode": "edit"}
    if request.method == "GET":
        return redirect(_admin_builder_url(subject.id, extra_params=base))
    if request.method != "POST":
        messages.error(request, "Invalid quiz edit request.")
        return redirect(_admin_builder_url(subject.id, extra_params=base))

    action = (request.POST.get("action") or "update_quiz").strip().lower()
    if action == "update_quiz":
        new_name = (request.POST.get("quiz_name") or "").strip()
        new_description = (request.POST.get("quiz_description") or "").strip()
        attempt_raw = (request.POST.get("attempt_limit") or "").strip()
        if not new_name or len(new_name) > 255:
            messages.error(request, "Quiz name is required and must be 255 characters or fewer.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        if not new_description or len(new_description) > 5000:
            messages.error(request, "Quiz description is required and must be 5000 characters or fewer.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        if not attempt_raw.isdigit() or not (1 <= int(attempt_raw) <= 100):
            messages.error(request, "Attempt limit must be between 1 and 100.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        if ChapterQuiz.objects.filter(chapter=chapter, quiz_name__iexact=new_name, is_deleted=False).exclude(id=quiz.id).exists():
            messages.error(request, "Another quiz with this name already exists.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        new_attempt = int(attempt_raw)
        old_name, old_description, old_attempt = quiz.quiz_name, quiz.quiz_description, quiz.attempt_limit
        with transaction.atomic():
            quiz.quiz_name = new_name
            quiz.quiz_description = new_description
            quiz.attempt_limit = new_attempt
            quiz.updated_by = None
            quiz.updated_by_admin = request.user
            quiz.save()
            if old_name != new_name:
                _record_quiz_admin_log(quiz, "name_changed", "quiz_name", old_name, new_name, "Quiz name was updated by Admin.", request.user)
            if old_description != new_description:
                _record_quiz_admin_log(quiz, "description_changed", "quiz_description", old_description, new_description, "Quiz description was updated by Admin.", request.user)
            if old_attempt != new_attempt:
                _record_quiz_admin_log(quiz, "attempt_limit_changed", "attempt_limit", old_attempt, new_attempt, "Quiz attempt limit was updated by Admin.", request.user)
        messages.success(request, f'Quiz "{quiz.quiz_name}" updated successfully.')
        return redirect(_admin_builder_url(subject.id, extra_params=base))

    if action == "update_question":
        qid = (request.POST.get("question_id") or "").strip()
        if not qid.isdigit():
            messages.error(request, "Invalid question selected.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        question = get_object_or_404(QuizQuestion, id=int(qid), quiz=quiz)
        text_value = (request.POST.get("question_text") or "").strip()
        marks_raw = (request.POST.get("marks") or "").strip()
        options = {label: (request.POST.get(f"option_{label.lower()}") or "").strip() for label in "ABCD"}
        correct = (request.POST.get("correct_option") or "").strip().upper()
        if not text_value or not marks_raw.isdigit() or int(marks_raw) <= 0 or any(not options[x] for x in "ABCD") or len({options[x].casefold() for x in "ABCD"}) != 4 or correct not in set("ABCD"):
            messages.error(request, "Question, four different options, marks and exactly one correct answer are required.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        old_text, old_marks = question.question_text, question.marks
        old_options = {x.option_label: x for x in question.options.all()}
        with transaction.atomic():
            question.question_text = text_value
            question.marks = int(marks_raw)
            question.save()
            for label, value in options.items():
                option = old_options.get(label)
                if option:
                    old_text_value, old_correct = option.option_text, option.is_correct
                    option.option_text = value
                    option.is_correct = label == correct
                    option.save()
                    if old_text_value != value:
                        _record_quiz_admin_log(quiz, "option_changed", f"option_{label}", old_text_value, value, f"Option {label} was updated by Admin.", request.user)
                    if old_correct != option.is_correct:
                        _record_quiz_admin_log(quiz, "correct_answer_changed", f"option_{label}_correct", old_correct, option.is_correct, f"Correct answer for option {label} was changed by Admin.", request.user)
                else:
                    QuizOption.objects.create(question=question, option_label=label, option_text=value, is_correct=(label == correct))
            quiz.updated_by = None
            quiz.updated_by_admin = request.user
            quiz.save(update_fields=["updated_by", "updated_by_admin", "updated_at"])
            if old_text != question.question_text:
                _record_quiz_admin_log(quiz, "question_updated", "question", old_text, question.question_text, "Quiz question was updated by Admin.", request.user)
            if old_marks != question.marks:
                _record_quiz_admin_log(quiz, "question_updated", "marks", old_marks, question.marks, "Question marks were updated by Admin.", request.user)
        messages.success(request, "Quiz question updated successfully.")
        return redirect(_admin_builder_url(subject.id, extra_params=base))

    if action == "delete_question":
        qid = (request.POST.get("question_id") or "").strip()
        if not qid.isdigit():
            messages.error(request, "Invalid question selected.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        question = get_object_or_404(QuizQuestion, id=int(qid), quiz=quiz)
        old_text = question.question_text
        with transaction.atomic():
            question.delete()
            quiz.updated_by = None
            quiz.updated_by_admin = request.user
            quiz.save(update_fields=["updated_by", "updated_by_admin", "updated_at"])
            _record_quiz_admin_log(quiz, "question_deleted", "question", old_text, "", "Quiz question was deleted by Admin.", request.user)
        messages.success(request, "Quiz question deleted successfully.")
        return redirect(_admin_builder_url(subject.id, extra_params=base))

    messages.error(request, "Invalid quiz edit action.")
    return redirect(_admin_builder_url(subject.id, extra_params=base))


# ==========================================================
# ADMIN TIMELINE ROUTES
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
def admin_chapter_timeline_view(request, subject_id, chapter_id):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id)
    return redirect(_admin_builder_url(subject.id, chapter.id, view="chapter_timeline"))


@login_required(login_url="admin_signin")
@admin_required
def admin_video_timeline_view(request, subject_id, chapter_id, video_id):
    subject, batch, chapter, video = _get_admin_video(subject_id, chapter_id, video_id)
    return redirect(_admin_builder_url(subject.id, chapter.id, view="video_timeline", extra_params={"video": video.id}))


@login_required(login_url="admin_signin")
@admin_required
def admin_pdf_timeline_view(request, subject_id, chapter_id, pdf_id):
    subject, batch, chapter, pdf = _get_admin_pdf(subject_id, chapter_id, pdf_id)
    return redirect(_admin_builder_url(subject.id, chapter.id, view="pdf_timeline", extra_params={"pdf": pdf.id}))


@login_required(login_url="admin_signin")
@admin_required
def admin_quiz_timeline_view(request, subject_id, chapter_id, quiz_id):
    subject, batch, chapter, quiz = _get_admin_quiz(subject_id, chapter_id, quiz_id)
    return redirect(_admin_builder_url(subject.id, chapter.id, view="quiz_timeline", extra_params={"quiz": quiz.id}))


# ==========================================================
# ADMIN DIRECT DELETE — COMMON AUDIT
# ==========================================================

def _require_delete_reason(request):
    reason = (request.POST.get("reason") or request.POST.get("delete_reason") or request.POST.get("admin_delete_reason") or "").strip()
    if not reason:
        return None, "Deletion reason is required."
    if len(reason) < 3:
        return None, "Deletion reason must contain at least 3 characters."
    if len(reason) > 5000:
        return None, "Deletion reason cannot exceed 5000 characters."
    return reason, ""


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_delete_chapter_view(request, subject_id, chapter_id):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id)
    reason, error = _require_delete_reason(request)
    if error:
        messages.error(request, error)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))
    with transaction.atomic():
        # Preserve individual child audits before chapter cascade deletion.
        children = list(chapter.videos.filter(is_deleted=False).select_related("created_by", "created_by_admin"))
        children += list(chapter.pdfs.filter(is_deleted=False).select_related("created_by", "created_by_admin"))
        children += list(chapter.quizzes.filter(is_deleted=False).select_related("created_by", "created_by_admin").prefetch_related("questions__options"))
        for child in children:
            child_type = "video" if isinstance(child, ChapterVideo) else "pdf" if isinstance(child, ChapterPDF) else "quiz"
            _delete_one_content(child_type, child, subject, batch, request.user, reason, "admin_direct")
        _delete_one_content("chapter", chapter, subject, batch, request.user, reason, "admin_direct")
    messages.success(request, "Chapter and its child content were deleted and recorded in the Content Deletion Audit.")
    return redirect(_admin_builder_url(subject.id, view="overview"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_delete_video_view(request, subject_id, chapter_id, video_id):
    subject, batch, chapter, video = _get_admin_video(subject_id, chapter_id, video_id)
    reason, error = _require_delete_reason(request)
    if error:
        messages.error(request, error)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="videos", extra_params={"video": video.id}))
    with transaction.atomic():
        _delete_one_content("video", video, subject, batch, request.user, reason, "admin_direct")
    messages.success(request, "Video deleted and recorded in the Content Deletion Audit.")
    return redirect(_admin_builder_url(subject.id, chapter.id, view="videos"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_delete_pdf_view(request, subject_id, chapter_id, pdf_id):
    subject, batch, chapter, pdf = _get_admin_pdf(subject_id, chapter_id, pdf_id)
    reason, error = _require_delete_reason(request)
    if error:
        messages.error(request, error)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs", extra_params={"pdf": pdf.id}))
    with transaction.atomic():
        _delete_one_content("pdf", pdf, subject, batch, request.user, reason, "admin_direct")
    messages.success(request, "PDF deleted and recorded in the Content Deletion Audit.")
    return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_delete_quiz_view(request, subject_id, chapter_id, quiz_id):
    subject, batch, chapter, quiz = _get_admin_quiz(subject_id, chapter_id, quiz_id)
    reason, error = _require_delete_reason(request)
    if error:
        messages.error(request, error)
        return redirect(_admin_builder_url(subject.id, chapter.id, view="quizzes", extra_params={"quiz": quiz.id}))
    with transaction.atomic():
        _delete_one_content("quiz", quiz, subject, batch, request.user, reason, "admin_direct")
    messages.success(request, "Quiz deleted and recorded in the Content Deletion Audit.")
    return redirect(_admin_builder_url(subject.id, chapter.id, view="quizzes"))


# ==========================================================
# ADMIN DELETE REQUESTS
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_delete_requests_view(request, subject_id):
    subject = _get_admin_subject(subject_id)
    _sync_pending_deletion_audits(subject)
    return redirect(_admin_builder_url(subject.id, view="delete_requests"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_approve_delete_request_view(request, subject_id, request_id):
    subject = _get_admin_subject(subject_id)
    audit = get_object_or_404(DeletionAudit, id=request_id, batch_name=subject.batch.batch_name, subject_name=subject.subject_name, status="pending")
    response = (request.POST.get("admin_response") or request.POST.get("response") or "").strip()
    if len(response) > 5000:
        messages.error(request, "Admin response cannot exceed 5000 characters.")
        return redirect(_admin_builder_url(subject.id, view="delete_requests"))
    ok, message = _approve_audit(audit, request.user)
    if response:
        # The audit survives even if the content was deleted.
        DeletionAudit.objects.filter(id=audit.id).update(admin_response=response)
    messages.success(request, message) if ok else messages.warning(request, message)
    return redirect(_admin_builder_url(subject.id, view="delete_requests"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_reject_delete_request_view(request, subject_id, request_id):
    subject = _get_admin_subject(subject_id)
    audit = get_object_or_404(DeletionAudit, id=request_id, batch_name=subject.batch.batch_name, subject_name=subject.subject_name, status="pending")
    response = (request.POST.get("admin_response") or request.POST.get("response") or request.POST.get("reason") or "").strip()
    if not response:
        messages.error(request, "Admin response/reason is required when rejecting a deletion request.")
        return redirect(_admin_builder_url(subject.id, view="delete_requests"))
    if len(response) > 5000:
        messages.error(request, "Admin response cannot exceed 5000 characters.")
        return redirect(_admin_builder_url(subject.id, view="delete_requests"))

    content_type = audit.content_type
    obj = None
    try:
        if content_type == "chapter":
            obj = CourseChapter.objects.get(id=audit.object_id, is_deleted=False)
        elif content_type == "video":
            obj = ChapterVideo.objects.get(id=audit.object_id, is_deleted=False)
        elif content_type == "pdf":
            obj = ChapterPDF.objects.get(id=audit.object_id, is_deleted=False)
        elif content_type == "quiz":
            obj = ChapterQuiz.objects.get(id=audit.object_id, is_deleted=False)
    except Exception:
        obj = None

    with transaction.atomic():
        if obj is not None:
            obj.delete_requested = False
            obj.delete_status = "rejected"
            obj.delete_reason = audit.delete_request_reason
            obj.save(update_fields=["delete_requested", "delete_status", "delete_reason"])
            if content_type == "chapter":
                _record_chapter_admin_log(obj, "delete_rejected", "delete_reason", audit.delete_request_reason, response, "Teacher deletion request was rejected by Admin.", request.user)
            elif content_type == "video":
                _record_video_admin_log(obj, "delete_rejected", "delete_reason", audit.delete_request_reason, response, "Teacher deletion request was rejected by Admin.", request.user)
            elif content_type == "pdf":
                _record_pdf_admin_log(obj, "delete_rejected", "delete_reason", audit.delete_request_reason, response, "Teacher deletion request was rejected by Admin.", request.user)
            elif content_type == "quiz":
                _record_quiz_admin_log(obj, "delete_rejected", "delete_reason", audit.delete_request_reason, response, "Teacher deletion request was rejected by Admin.", request.user)
        audit.admin_decision = "rejected"
        audit.decision_by_admin = request.user
        audit.decision_at = timezone.now()
        audit.admin_response = response
        audit.status = "rejected"
        audit.save()
    messages.success(request, "Delete request rejected. The content remains available and the decision is recorded in the shared audit.")
    return redirect(_admin_builder_url(subject.id, view="delete_requests"))


# ==========================================================
# COMMON CONTENT DELETION AUDIT
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_course_audit_view(request, subject_id):
    subject = _get_admin_subject(subject_id)
    _sync_pending_deletion_audits(subject)
    return redirect(_admin_builder_url(subject.id, view="audit", extra_params={
        "audit_type": request.GET.get("audit_type", "all"),
        "audit_status": request.GET.get("audit_status", "all"),
        "audit_search": request.GET.get("audit_search", ""),
    }))

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def create_subject_view(request):

    batches = Batch.objects.order_by("batch_name")

    if request.method == "POST":

        batch_id = request.POST.get("batch", "").strip()
        subject_name = request.POST.get("subject_name", "").strip()
        subject_description = request.POST.get("subject_description", "").strip()
        subject_status = request.POST.get("subject_status", "").strip()
        subject_thumbnail = request.FILES.get("subject_thumbnail")

        context = {
            "batches": batches,
        }

        # ---------------- Batch ----------------

        if not batch_id:

            messages.error(request, "Please select a batch.")

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        try:

            batch = Batch.objects.get(id=batch_id)

        except Batch.DoesNotExist:

            messages.error(request, "Selected batch does not exist.")

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        # ---------------- Subject Name ----------------

        if not subject_name:

            messages.error(request, "Subject name is required.")

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        # Duplicate inside same batch

        if Subject.objects.filter(
            batch=batch,
            subject_name__iexact=subject_name
        ).exists():

            messages.error(
                request,
                "This subject already exists in the selected batch."
            )

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        # ---------------- Description ----------------

        if not subject_description:

            messages.error(
                request,
                "Subject description is required."
            )

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        # ---------------- Status ----------------

        if subject_status not in ["draft", "published"]:

            messages.error(
                request,
                "Invalid subject status."
            )

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        # ---------------- Thumbnail ----------------

        if not subject_thumbnail:

            messages.error(
                request,
                "Subject thumbnail is required."
            )

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        allowed_extensions = [
            "jpg",
            "jpeg",
            "png",
            "webp"
        ]

        extension = subject_thumbnail.name.split(".")[-1].lower()

        if extension not in allowed_extensions:

            messages.error(
                request,
                "Only JPG, JPEG, PNG and WEBP images are allowed."
            )

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        if subject_thumbnail.size > 5 * 1024 * 1024:

            messages.error(
                request,
                "Thumbnail must be less than 5 MB."
            )

            return render(
                request,
                "admins/subjects/create_subject.html",
                context,
            )

        # ---------------- Save ----------------

        Subject.objects.create(

            batch=batch,

            subject_name=subject_name,

            subject_description=subject_description,

            subject_thumbnail=subject_thumbnail,

            subject_status=subject_status,

        )

        messages.success(request,"Subject created successfully.")

        return redirect("admin_subjects")
    context = {"batches": batches}
    return render(request,"admins/subjects/create_subject.html",context)


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def edit_subject_view(request, subject_id):

    subject = get_object_or_404(
        Subject,
        id=subject_id
    )

    batches = Batch.objects.order_by("batch_name")

    if request.method == "POST":
        batch_id = request.POST.get("batch", "").strip()
        subject_name = request.POST.get("subject_name", "").strip()
        subject_description = request.POST.get("subject_description", "").strip()
        subject_status = request.POST.get("subject_status", "").strip()
        new_thumbnail = request.FILES.get("subject_thumbnail")

        context = {
            "subject": subject,
            "batches": batches,
        }

        # ---------------- Batch ----------------

        if not batch_id:

            messages.error(request, "Please select a batch.")

            return render(
                request,
                "admins/subjects/edit_subject.html",
                context,
            )

        try:

            batch = Batch.objects.get(id=batch_id)

        except Batch.DoesNotExist:

            messages.error(request, "Invalid batch selected.")

            return render(
                request,
                "admins/subjects/edit_subject.html",
                context,
            )

        # ---------------- Subject Name ----------------

        if not subject_name:

            messages.error(request, "Subject name is required.")

            return render(
                request,
                "admins/subjects/edit_subject.html",
                context,
            )

        duplicate = Subject.objects.filter(
            batch=batch,
            subject_name__iexact=subject_name
        ).exclude(id=subject.id)

        if duplicate.exists():

            messages.error(
                request,
                "A subject with this name already exists in the selected batch."
            )

            return render(
                request,
                "admins/subjects/edit_subject.html",
                context,
            )

        # ---------------- Description ----------------

        if not subject_description:

            messages.error(
                request,
                "Description is required."
            )

            return render(
                request,
                "admins/subjects/edit_subject.html",
                context,
            )

        # ---------------- Status ----------------

        if subject_status not in ["draft", "published"]:

            messages.error(
                request,
                "Invalid subject status."
            )

            return render(
                request,
                "admins/subjects/edit_subject.html",
                context,
            )

        # ---------------- Thumbnail Validation ----------------

        if new_thumbnail:

            allowed_extensions = [
                "jpg",
                "jpeg",
                "png",
                "webp",
            ]

            extension = new_thumbnail.name.split(".")[-1].lower()

            if extension not in allowed_extensions:

                messages.error(
                    request,
                    "Only JPG, JPEG, PNG and WEBP images are allowed."
                )

                return render(
                    request,
                    "admins/subjects/edit_subject.html",
                    context,
                )

            if new_thumbnail.size > 5 * 1024 * 1024:

                messages.error(
                    request,
                    "Thumbnail must be less than 5 MB."
                )

                return render(
                    request,
                    "admins/subjects/edit_subject.html",
                    context,
                )

            subject.subject_thumbnail = new_thumbnail

        # ---------------- Update ----------------

        subject.batch = batch
        subject.subject_name = subject_name
        subject.subject_description = subject_description
        subject.subject_status = subject_status

        subject.save()

        messages.success(request,"Subject updated successfully.")

        return redirect("admin_subjects")
    context = {"subject": subject,"batches": batches,}
    return render(request,"admins/subjects/edit_subject.html",context,)


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def delete_subject_view(request, subject_id):

    subject = get_object_or_404(
        Subject,
        id=subject_id
    )

    if request.method == "POST":

        confirm_name = request.POST.get(
            "confirm_name",
            ""
        ).strip()

        # Subject name confirmation

        if confirm_name != subject.subject_name:

            messages.error(request,"Subject name does not match.")
            return render(request,"admins/subjects/delete_subject.html",{"subject": subject,},)

        # Delete Subject

        subject.delete()

        messages.success(request,"Subject deleted successfully.")

        return redirect("admin_subjects")

    return render(request,"admins/subjects/delete_subject.html",{"subject": subject})



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def admin_teachers(request):
    search = request.GET.get("search", "").strip()

    teachers = (Teacher.objects.select_related("user").order_by("-created_at"))

    if search:
        teachers = teachers.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone_number__icontains=search) |
            Q(user__username__icontains=search))

    total_teachers = Teacher.objects.count()
    active_teachers = Teacher.objects.filter(is_blocked=False).count()
    blocked_teachers = Teacher.objects.filter(is_blocked=True).count()
    pending_profiles = Teacher.objects.filter(profile_completed=False).count()
    context = {
        "teachers": teachers,
        "search": search,
        "total_teachers": total_teachers,
        "active_teachers": active_teachers,
        "blocked_teachers": blocked_teachers,
        "pending_profiles": pending_profiles,
    }

    return render(request,"admins/teachers/teachers.html",context)


@cache_control(no_cache=True,must_revalidate=True,no_store=True)
@admin_required
def create_teacher_view(request):

    if request.method == "POST":
        email = request.POST.get("email","").strip().lower()
        phone = request.POST.get("phone_number","").strip()


        # Empty validation
        if not email or not phone:
            messages.error(request,"Email and phone number required.")
            return redirect("create_teacher")

        # Already exists
        if User.objects.filter(email=email).exists():

            messages.error(request,"Teacher already exists.")
            return redirect("create_teacher")


        # Generate password
        password = f"Neo{phone}*#"
        # Create auth user

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password)


        # Create teacher
        Teacher.objects.create(user=user,full_name=email.split("@")[0],email=email,phone_number=phone,created_by=request.user)

        # Email send using existing SMTP
        send_mail(

            "NeoLearn Teacher Login Details",


            f"""

Welcome to NeoLearn Teacher Portal


Login URL:
http://127.0.0.1:8000/teacher/login/


Username:
{email}


Password:
{password}


Please change password after first login.


            """,


            None,


            [email],


            fail_silently=False

        )


        messages.success(request,"Teacher created successfully.")
        return redirect("admin_teachers")

    return render(request,"admins/teachers/create_teacher.html")


@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_assign_teacher_batch(request, teacher_id):

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id
    )

    batches = Batch.objects.filter(
        batch_status="published"
    ).order_by("batch_name")

    selected_batch = None
    subjects = Subject.objects.none()
    assigned_subject_ids = []

    # =====================================================
    # SAVE ASSIGNMENT
    # =====================================================

    if request.method == "POST":

        batch_id = request.POST.get("batch")
        subject_ids = request.POST.getlist("subjects")

        # -------------------------------
        # Batch Validation
        # -------------------------------

        if not batch_id:

            messages.error(
                request,
                "Please select a batch."
            )

            return redirect(
                "admin_assign_teacher_batch",
                teacher_id=teacher.id
            )

        # -------------------------------
        # Subject Validation
        # -------------------------------

        if len(subject_ids) == 0:

            messages.error(
                request,
                "Please select at least one subject."
            )

            return redirect(
                "admin_assign_teacher_batch",
                teacher_id=teacher.id
            )

        selected_batch = get_object_or_404(
            Batch,
            id=batch_id,
            batch_status="published"
        )

        # -------------------------------
        # Validate Selected Subjects
        # -------------------------------

        selected_subjects = Subject.objects.filter(
            id__in=subject_ids,
            batch=selected_batch,
            subject_status="published"
        )

        if selected_subjects.count() != len(subject_ids):

            messages.error(
                request,
                "Invalid subject selection."
            )

            return redirect(
                "admin_assign_teacher_batch",
                teacher_id=teacher.id
            )

        # -------------------------------
        # Save / Reactivate Teacher Batch
        # -------------------------------

        TeacherBatch.objects.update_or_create(
            teacher=teacher,
            batch=selected_batch,
            defaults={
                "assigned_by": request.user,
                "is_active": True,
            }
        )

        # -------------------------------
        # Save / Reactivate Subjects
        # -------------------------------

        for subject in selected_subjects:

            TeacherSubject.objects.update_or_create(
                teacher=teacher,
                batch=selected_batch,
                subject=subject,
                defaults={
                    "assigned_by": request.user,
                    "is_active": True,
                }
            )

        # -------------------------------
        # Deactivate Unchecked Subjects
        # -------------------------------

        TeacherSubject.objects.filter(
            teacher=teacher,
            batch=selected_batch,
            is_active=True
        ).exclude(
            subject_id__in=subject_ids
        ).update(
            is_active=False
        )

        messages.success(
            request,
            "Batch and subjects assigned successfully."
        )

        return redirect(
            "admin_teacher_assignments",
            teacher_id=teacher.id
        )

    # =====================================================
    # LOAD SUBJECTS
    # =====================================================

    batch_id = request.GET.get("batch")

    if batch_id:

        selected_batch = get_object_or_404(
            Batch,
            id=batch_id,
            batch_status="published"
        )

        subjects = Subject.objects.filter(
            batch=selected_batch,
            subject_status="published"
        ).order_by("subject_name")

        assigned_subject_ids = list(
            TeacherSubject.objects.filter(
                teacher=teacher,
                batch=selected_batch,
                is_active=True
            ).values_list(
                "subject_id",
                flat=True
            )
        )

    context = {
        "teacher": teacher,
        "batches": batches,
        "selected_batch": selected_batch,
        "subjects": subjects,
        "assigned_subject_ids": assigned_subject_ids,
    }

    return render(
        request,
        "admins/teachers/assign_batch.html",
        context,
    )


@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_teacher_assignments(request, teacher_id):

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id,
    )

    teacher_batches = (
        TeacherBatch.objects.filter(
            teacher=teacher,
            is_active=True,
        )
        .select_related("batch")
        .order_by("-assigned_at")
    )

    total_subjects = 0

    for assignment in teacher_batches:

        assignment.subject_count = TeacherSubject.objects.filter(
            teacher=teacher,
            batch=assignment.batch,
            is_active=True,
        ).count()

        assignment.teacher_count = TeacherBatch.objects.filter(
            batch=assignment.batch,
            is_active=True,
        ).count()

        total_subjects += assignment.subject_count

    context = {
        "teacher": teacher,
        "teacher_batches": teacher_batches,
        "total_subjects": total_subjects,
    }

    return render(
        request,
        "admins/teachers/manage_assignments.html",
        context,
    )
    

@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_view_teacher_subjects(request, teacher_id, batch_id):

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id,
    )

    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    assigned_subjects = (
        TeacherSubject.objects.filter(
            teacher=teacher,
            batch=batch,
            is_active=True,
        )
        .select_related("subject")
        .order_by("subject__subject_name")
    )

    for assignment in assigned_subjects:

        assignment.teacher_count = TeacherSubject.objects.filter(
            subject=assignment.subject,
            is_active=True,
        ).count()

    subject_count = assigned_subjects.count()

    batch_teacher_count = TeacherBatch.objects.filter(
        batch=batch,
        is_active=True,
    ).count()

    published_subject_count = Subject.objects.filter(
        batch=batch,
        subject_status="published",
    ).count()

    context = {
        "teacher": teacher,
        "batch": batch,
        "assigned_subjects": assigned_subjects,
        "subject_count": subject_count,
        "batch_teacher_count": batch_teacher_count,
        "published_subject_count": published_subject_count,
    }

    return render(
        request,
        "admins/teachers/view_subjects.html",
        context,
    )
@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_remove_teacher_subject(request, assignment_id):

    assignment = get_object_or_404(
        TeacherSubject,
        id=assignment_id,
        is_active=True,
    )

    teacher_id = assignment.teacher.id
    batch_id = assignment.batch.id

    assignment.delete()

    messages.success(
        request,
        "Subject access removed successfully.",
    )

    return redirect(
        "admin_view_teacher_subjects",
        teacher_id=teacher_id,
        batch_id=batch_id,
    )
    
    
@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_remove_teacher_batch(request, assignment_id):

    assignment = get_object_or_404(
        TeacherBatch,
        id=assignment_id,
        is_active=True,
    )

    teacher_id = assignment.teacher.id

    TeacherSubject.objects.filter(
        teacher=assignment.teacher,
        batch=assignment.batch,
        is_active=True,
    ).delete()

    assignment.delete()

    messages.success(
        request,
        "Batch access removed successfully.",
    )

    return redirect(
        "admin_teacher_assignments",
        teacher_id=teacher_id,
    )
    
# ======================================================
# BLOCK TEACHER
# ======================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_block_teacher(request, teacher_id):

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id,
    )

    teacher.is_blocked = True
    teacher.save(update_fields=["is_blocked"])

    messages.success(
        request,
        f"{teacher.full_name} has been blocked successfully.",
    )

    return redirect("admin_teachers")


# ======================================================
# UNBLOCK TEACHER
# ======================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_unblock_teacher(request, teacher_id):

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id,
    )

    teacher.is_blocked = False
    teacher.save(update_fields=["is_blocked"])

    messages.success(
        request,
        f"{teacher.full_name} has been unblocked successfully.",
    )

    return redirect("admin_teachers")


# ======================================================
# DELETE TEACHER
# ======================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_delete_teacher(request, teacher_id):

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id,
    )

    teacher_name = teacher.full_name
    user = teacher.user

    teacher.delete()

    if user:
        user.delete()

    messages.success(
        request,
        f"{teacher_name} has been deleted successfully.",
    )

    return redirect("admin_teachers")

@login_required(login_url="admin_signin")
@admin_required
def get_teacher_batches_data(request, teacher_id):
    """Get teacher's assigned batches and subjects"""
    teacher = get_object_or_404(Teacher, id=teacher_id)
    
    teacher_batches = TeacherBatch.objects.filter(
        teacher=teacher,
        is_active=True
    ).select_related('batch')
    
    data = {
        'batches': []
    }
    
    for tb in teacher_batches:
        subjects = TeacherSubject.objects.filter(
            teacher=teacher,
            batch=tb.batch,
            is_active=True
        ).select_related('subject')
        
        batch_data = {
            'batch_name': tb.batch.batch_name,
            'subject_count': subjects.count(),
            'student_count': 0,
            'subjects': [s.subject.subject_name for s in subjects]
        }
        data['batches'].append(batch_data)
    
    return JsonResponse(data)
