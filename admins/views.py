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
from django.db.models import Count,Q
from .decorators import admin_required
from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from admins.models import (Teacher,Batch,Subject,TeacherBatch,TeacherSubject)
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


from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Batch, Subject


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