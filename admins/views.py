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
from django.db.models import Count, Q
from django.db import transaction
from .decorators import admin_required
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
    ChapterVideo,
    ChapterPDF,
    ChapterQuiz,
    QuizQuestion,
    DeletionAudit,
)
from django.http import JsonResponse
from datetime import datetime
from .validators import (validate_create_batch,validate_edit_batch,)
from .helpers import (create_batch,update_batch,build_batch_context,can_delete_batch,can_archive_batch,can_publish_batch,can_edit_batch,)
from cloudinary.uploader import destroy
from courses import services as course_services
from courses.forms import (
    ChapterCreateForm,
    ChapterEditForm,
    VideoUploadForm,
    VideoEditForm,
    PDFUploadForm,
    PDFEditForm,
    QuizForm,
    QuizQuestionForm,
)


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
#
# Admin manages teacher-created content in this workspace:
#   - View teacher-created content
#   - Edit existing content
#   - Create chapters / upload videos / upload PDFs / create quizzes
#   - View shared timelines
#   - Directly delete content with a required reason
#   - Review teacher delete requests
#   - Approve / reject teacher delete requests
#   - View the common permanent Deletion Audit
#
# All create/edit/delete/approve/reject logic is shared with the
# Teacher Course Builder via courses/forms.py + courses/services.py.
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
        chapter_timeline_entries = [course_services.build_timeline_entry(x) for x in course_services.get_chapter_timeline(selected_chapter)]
    if selected_video and selected_content == "video_timeline":
        video_timeline_entries = [course_services.build_timeline_entry(x) for x in course_services.get_video_timeline(selected_video)]
    if selected_pdf and selected_content == "pdf_timeline":
        pdf_timeline_entries = [course_services.build_timeline_entry(x) for x in course_services.get_pdf_timeline(selected_pdf)]
    if selected_quiz and selected_content == "quiz_timeline":
        quiz_timeline_entries = [course_services.build_timeline_entry(x) for x in course_services.get_quiz_timeline(selected_quiz)]

    course_services.sync_pending_deletion_audits(subject)
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
# ADMIN CREATION ENDPOINTS
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_create_chapter_view(request, subject_id):
    subject = _get_admin_subject(subject_id)
    form = ChapterCreateForm(
        request.POST,
        batch=subject.batch,
        subject=subject,
    )
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect(_admin_builder_url(subject_id, view="overview"))
    try:
        chapter = course_services.create_chapter(
            batch=subject.batch,
            subject=subject,
            admin_actor=request.user,
            chapter_name=form.cleaned_data["chapter_name"],
            chapter_description=form.cleaned_data["chapter_description"],
            status=form.cleaned_data["status"],
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_admin_builder_url(subject_id, view="overview"))
    messages.success(request, f'Chapter "{chapter.chapter_name}" created successfully.')
    return redirect(_admin_builder_url(subject_id, chapter.id, view="overview"))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_upload_video_view(request, subject_id, chapter_id):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id)
    form = VideoUploadForm(
        request.POST,
        request.FILES,
        chapter=chapter,
    )
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect(_admin_builder_url(subject_id, chapter_id, view="videos"))
    try:
        video = course_services.create_video(
            chapter=chapter,
            admin_actor=request.user,
            video_name=form.cleaned_data["video_name"],
            video_description=form.cleaned_data["video_description"],
            video_file=form.cleaned_data["video_file"],
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_admin_builder_url(subject_id, chapter_id, view="videos"))
    messages.success(request, f'Video "{video.video_name}" uploaded successfully.')
    return redirect(_admin_builder_url(subject_id, chapter_id, view="videos", extra_params={"video": video.id}))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_upload_pdf_view(request, subject_id, chapter_id):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id)
    form = PDFUploadForm(
        request.POST,
        request.FILES,
        chapter=chapter,
    )
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect(_admin_builder_url(subject_id, chapter_id, view="pdfs"))
    try:
        pdf = course_services.create_pdf(
            chapter=chapter,
            admin_actor=request.user,
            pdf_name=form.cleaned_data["pdf_name"],
            pdf_description=form.cleaned_data["pdf_description"],
            pdf_file=form.cleaned_data["pdf_file"],
            pdf_thumbnail=form.cleaned_data.get("pdf_thumbnail"),
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_admin_builder_url(subject_id, chapter_id, view="pdfs"))
    messages.success(request, f'PDF "{pdf.pdf_name}" uploaded successfully.')
    return redirect(_admin_builder_url(subject_id, chapter_id, view="pdfs", extra_params={"pdf": pdf.id}))


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_create_quiz_view(request, subject_id, chapter_id):
    subject, batch, chapter = _get_admin_chapter(subject_id, chapter_id)
    form = QuizForm(
        request.POST,
        chapter=chapter,
    )
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect(_admin_builder_url(subject_id, chapter_id, view="quizzes"))

    question_count_raw = (request.POST.get("question_count", "") or "").strip()
    requested_question_count = int(question_count_raw) if question_count_raw.isdigit() else 0
    requested_question_count = min(max(requested_question_count, 0), 100)

    questions = []
    for index in range(requested_question_count):
        question_data = {
            "question_text": (request.POST.get(f"question_{index}_text", "") or "").strip(),
            "marks": (request.POST.get(f"question_{index}_marks", "") or "").strip(),
            "option_a": (request.POST.get(f"question_{index}_option_a", "") or "").strip(),
            "option_b": (request.POST.get(f"question_{index}_option_b", "") or "").strip(),
            "option_c": (request.POST.get(f"question_{index}_option_c", "") or "").strip(),
            "option_d": (request.POST.get(f"question_{index}_option_d", "") or "").strip(),
            "correct_option": (request.POST.get(f"question_{index}_correct", "") or "").strip().upper(),
        }
        question_form = QuizQuestionForm(question_data)
        if not question_form.is_valid():
            messages.error(request, f"Question {index + 1}: {next(iter(question_form.errors.values()))[0]}")
            return redirect(_admin_builder_url(subject_id, chapter_id, view="quizzes"))
        questions.append({
            "question_text": question_form.cleaned_data["question_text"],
            "marks": question_form.cleaned_data["marks"],
            "options": {
                "A": question_form.cleaned_data["option_a"],
                "B": question_form.cleaned_data["option_b"],
                "C": question_form.cleaned_data["option_c"],
                "D": question_form.cleaned_data["option_d"],
            },
            "correct_option": question_form.cleaned_data["correct_option"],
        })

    if not questions:
        messages.error(request, "Add at least one question before saving the quiz.")
        return redirect(_admin_builder_url(subject_id, chapter_id, view="quizzes"))

    try:
        quiz = course_services.create_quiz(
            chapter=chapter,
            admin_actor=request.user,
            quiz_name=form.cleaned_data["quiz_name"],
            quiz_description=form.cleaned_data["quiz_description"],
            attempt_limit=form.cleaned_data["attempt_limit"],
            questions=questions,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_admin_builder_url(subject_id, chapter_id, view="quizzes"))
    messages.success(request, f'Quiz "{quiz.quiz_name}" created successfully.')
    return redirect(_admin_builder_url(subject_id, chapter_id, view="quizzes", extra_params={"quiz": quiz.id}))


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

    form = ChapterEditForm(
        {
            **request.POST,
            "chapter_order": chapter.chapter_order,
        },
        batch=batch,
        subject=subject,
        instance=chapter,
    )

    if not form.is_valid():
        _chapter_edit_state(
            request,
            chapter,
            next(iter(form.errors.values()))[0],
            chapter_name=form.data.get("chapter_name", ""),
            chapter_description=form.data.get("chapter_description", ""),
            status=form.data.get("status", ""),
        )
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))

    try:
        course_services.update_chapter(
            chapter=chapter,
            admin_actor=request.user,
            chapter_name=form.cleaned_data["chapter_name"],
            chapter_description=form.cleaned_data["chapter_description"],
            chapter_order=chapter.chapter_order,
            status=form.cleaned_data["status"],
        )
    except ValueError as exc:
        _chapter_edit_state(
            request,
            chapter,
            str(exc),
            chapter_name=form.data.get("chapter_name", ""),
            chapter_description=form.data.get("chapter_description", ""),
            status=form.data.get("status", ""),
        )
        return redirect(_admin_builder_url(subject.id, chapter.id, view="overview"))

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

    form = VideoEditForm(
        request.POST,
        request.FILES,
        chapter=chapter,
        instance=video,
    )

    if not form.is_valid():
        _video_edit_state(
            request,
            video,
            next(iter(form.errors.values()))[0],
            video_name=form.data.get("video_name", ""),
            video_description=form.data.get("video_description", ""),
            video_order=form.data.get("video_order", "") or video.video_order,
        )
        return redirect(_admin_builder_url(subject.id, chapter.id, view="videos", extra_params={"video": video.id}))

    try:
        course_services.update_video(
            video=video,
            admin_actor=request.user,
            video_name=form.cleaned_data["video_name"],
            video_description=form.cleaned_data["video_description"],
            video_order=form.cleaned_data["video_order"],
            replacement_file=form.cleaned_data.get("video_file"),
        )
    except ValueError as exc:
        _video_edit_state(
            request,
            video,
            str(exc),
            video_name=form.data.get("video_name", ""),
            video_description=form.data.get("video_description", ""),
            video_order=form.data.get("video_order", "") or video.video_order,
        )
        return redirect(_admin_builder_url(subject.id, chapter.id, view="videos", extra_params={"video": video.id}))

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

    form = PDFEditForm(
        request.POST,
        request.FILES,
        chapter=chapter,
        instance=pdf,
    )

    if not form.is_valid():
        _pdf_edit_state(
            request,
            pdf,
            next(iter(form.errors.values()))[0],
            pdf_name=form.data.get("pdf_name", ""),
            pdf_description=form.data.get("pdf_description", ""),
            pdf_order=form.data.get("pdf_order", "") or pdf.pdf_order,
        )
        return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs", extra_params={"pdf": pdf.id}))

    try:
        course_services.update_pdf(
            pdf=pdf,
            admin_actor=request.user,
            pdf_name=form.cleaned_data["pdf_name"],
            pdf_description=form.cleaned_data["pdf_description"],
            pdf_order=form.cleaned_data["pdf_order"],
            replacement_file=form.cleaned_data.get("pdf_file"),
            replacement_thumbnail=form.cleaned_data.get("pdf_thumbnail"),
        )
    except ValueError as exc:
        _pdf_edit_state(
            request,
            pdf,
            str(exc),
            pdf_name=form.data.get("pdf_name", ""),
            pdf_description=form.data.get("pdf_description", ""),
            pdf_order=form.data.get("pdf_order", "") or pdf.pdf_order,
        )
        return redirect(_admin_builder_url(subject.id, chapter.id, view="pdfs", extra_params={"pdf": pdf.id}))

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
        form = QuizForm(
            request.POST,
            chapter=chapter,
            instance=quiz,
        )
        if not form.is_valid():
            messages.error(request, next(iter(form.errors.values()))[0])
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        try:
            course_services.update_quiz(
                quiz=quiz,
                admin_actor=request.user,
                quiz_name=form.cleaned_data["quiz_name"],
                quiz_description=form.cleaned_data["quiz_description"],
                attempt_limit=form.cleaned_data["attempt_limit"],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        messages.success(request, f'Quiz "{quiz.quiz_name}" updated successfully.')
        return redirect(_admin_builder_url(subject.id, extra_params=base))

    if action == "update_question":
        qid = (request.POST.get("question_id") or "").strip()
        if not qid.isdigit():
            messages.error(request, "Invalid question selected.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        question = get_object_or_404(QuizQuestion, id=int(qid), quiz=quiz)
        question_form = QuizQuestionForm(request.POST)
        if not question_form.is_valid():
            messages.error(request, next(iter(question_form.errors.values()))[0])
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        course_services.update_quiz_question(
            question=question,
            admin_actor=request.user,
            question_text=question_form.cleaned_data["question_text"],
            marks=question_form.cleaned_data["marks"],
            options={
                "A": question_form.cleaned_data["option_a"],
                "B": question_form.cleaned_data["option_b"],
                "C": question_form.cleaned_data["option_c"],
                "D": question_form.cleaned_data["option_d"],
            },
            correct_option=question_form.cleaned_data["correct_option"],
        )
        messages.success(request, "Quiz question updated successfully.")
        return redirect(_admin_builder_url(subject.id, extra_params=base))

    if action == "delete_question":
        qid = (request.POST.get("question_id") or "").strip()
        if not qid.isdigit():
            messages.error(request, "Invalid question selected.")
            return redirect(_admin_builder_url(subject.id, extra_params=base))
        question = get_object_or_404(QuizQuestion, id=int(qid), quiz=quiz)
        course_services.delete_quiz_question(
            question=question,
            admin_actor=request.user,
        )
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
            course_services.direct_delete(child_type, child, subject, batch, request.user, reason)
        course_services.direct_delete("chapter", chapter, subject, batch, request.user, reason)
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
        course_services.direct_delete("video", video, subject, batch, request.user, reason)
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
        course_services.direct_delete("pdf", pdf, subject, batch, request.user, reason)
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
        course_services.direct_delete("quiz", quiz, subject, batch, request.user, reason)
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
    course_services.sync_pending_deletion_audits(subject)
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
    ok, message = course_services.approve_delete_request(audit, request.user, response)
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
    ok, message = course_services.reject_delete_request(audit, request.user, response)
    messages.success(request, message) if ok else messages.warning(request, message)
    return redirect(_admin_builder_url(subject.id, view="delete_requests"))


# ==========================================================
# COMMON CONTENT DELETION AUDIT
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_course_audit_view(request, subject_id):
    subject = _get_admin_subject(subject_id)
    course_services.sync_pending_deletion_audits(subject)
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
