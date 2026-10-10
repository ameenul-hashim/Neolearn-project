from django.shortcuts import render, redirect
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Q, Count
from django.db.models.deletion import ProtectedError
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.contrib.auth.password_validation import validate_password
from orders.models import StudentBatchPurchase
from orders.helpers import (
    execute_refund,
    create_order_timeline_event,
)
from .decorators import admin_required
from .helpers import (
    create_batch,
    update_batch,
    build_batch_context,
    can_delete_batch,
    can_archive_batch,
    can_publish_batch,
    can_edit_batch,

    # Coupon helpers
    build_coupon_form_context,
    parse_and_validate_coupon,
    save_coupon_batch_rules,
    create_coupon_instance,
    update_coupon_instance,
    add_coupon_errors_to_messages,
    get_coupon_listing_context,
    toggle_coupon_status,
    can_delete_coupon,
    delete_coupon,

    # Order Management helpers
    get_admin_order_listing_context,
    get_admin_order_detail,
    save_admin_order_selection,
    remove_admin_order_selection,
    clear_admin_order_selections,

    # Refund Management helpers
    get_admin_refund_listing_context,
    get_admin_refund_detail,
    get_admin_refund_summary,
    get_admin_refund_type,
    get_admin_refund_item_count,
    get_admin_refund_amount,

)


from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from admins.models import (Batch,Subject,Coupon)
from django.db import models,transaction
from teachers.models import (Teacher,TeacherBatch,TeacherSubject,)
from decimal import Decimal
from django.http import JsonResponse
from django.utils import timezone
from .validators import (validate_create_batch,validate_edit_batch,)
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


# ==========================================================
# ADMIN STUDENT LISTING
# ==========================================================

@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
@admin_required
def admin_students_view(request):
    """
    Admin student listing.

    Features:
    - Search by username, email, first name, last name,
      and NeoLearn Student ID.
    - Filter by account status.
    - Filter by purchased batch.
    - Sort students.
    - Paginate students.
    - Show active purchase count and purchase history.
    """

    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect("admin_signin")

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "all")
    sort = request.GET.get("sort", "newest")
    selected_batch = request.GET.get("batch", "").strip()

    students = (
        User.objects
        .filter(
            is_staff=False,
            is_superuser=False,
            teacher_profile__isnull=True,
        )
        .select_related("studentprofile")
        .annotate(
            enrolled_courses=Count(
                "purchased_batches",
                filter=Q(purchased_batches__status="active"),
                distinct=True,
            )
        )
    )

    # ------------------------------------------------------
    # SEARCH
    # ------------------------------------------------------

    if search:
        students = students.filter(
            Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(studentprofile__neo_student_id__icontains=search)
        ).distinct()

    # ------------------------------------------------------
    # ACCOUNT STATUS FILTER
    # ------------------------------------------------------

    if status == "active":
        students = students.filter(is_active=True)

    elif status == "inactive":
        students = students.filter(is_active=False)

    # ------------------------------------------------------
    # PURCHASED BATCH FILTER
    # ------------------------------------------------------

    if selected_batch:
        if selected_batch.isdigit():
            students = students.filter(
                purchased_batches__batch_id=int(selected_batch)
            ).distinct()
        else:
            selected_batch = ""

    # ------------------------------------------------------
    # SORTING
    # ------------------------------------------------------

    if sort == "oldest":
        students = students.order_by("date_joined", "id")

    elif sort == "a-z":
        students = students.order_by("username", "id")

    elif sort == "z-a":
        students = students.order_by("-username", "id")

    else:
        sort = "newest"
        students = students.order_by("-date_joined", "-id")

    # ------------------------------------------------------
    # PAGINATION
    # ------------------------------------------------------

    paginator = Paginator(students, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ------------------------------------------------------
    # PREPARE STUDENT DETAILS AND PURCHASE HISTORY
    # FOR THE CURRENT PAGE ONLY
    # ------------------------------------------------------

    student_list = list(page_obj.object_list)
    student_ids = [student.id for student in student_list]

    purchases_by_student = {
        student_id: []
        for student_id in student_ids
    }

    if student_ids:
        purchases = (
            StudentBatchPurchase.objects
            .filter(student_id__in=student_ids)
            .select_related("batch", "order", "order_item")
            .order_by("-purchased_at", "-id")
        )

        for purchase in purchases:
            purchases_by_student[purchase.student_id].append(purchase)

    for student in student_list:
        profile = getattr(student, "studentprofile", None)

        student.neo_student_id_display = (
            profile.neo_student_id
            if profile
            else ""
        )

        student.batch_purchases_list = (
            purchases_by_student.get(student.id, [])
        )

    # ------------------------------------------------------
    # FILTER DROPDOWN DATA
    # ------------------------------------------------------

    batches = Batch.objects.order_by("batch_name")

    context = {
        "page_obj": page_obj,
        "students": student_list,
        "search": search,
        "status": status,
        "sort": sort,
        "batches": batches,
        "selected_batch": selected_batch,
    }

    return render(
        request,
        "admins/students/students.html",
        context,
    )


# ==========================================================
# EDIT STUDENT
# ==========================================================

@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
@admin_required
@require_POST
def edit_student_view(request, user_id):
    """
    Update a student's username and optionally their password.

    Email is intentionally read-only.
    An empty password field keeps the existing password.
    """

    student = get_object_or_404(
        User.objects.filter(
            is_staff=False,
            is_superuser=False,
            teacher_profile__isnull=True,
        ),
        id=user_id,
    )

    username = request.POST.get("username", "").strip()
    new_password = request.POST.get("new_password", "")

    # ------------------------------------------------------
    # USERNAME VALIDATION
    # ------------------------------------------------------

    if not username:
        messages.error(request, "Username is required.")
        return redirect("admin_students")

    if User.objects.filter(
        username__iexact=username
    ).exclude(
        id=student.id
    ).exists():
        messages.error(request, "That username is already in use.")
        return redirect("admin_students")

    # ------------------------------------------------------
    # PASSWORD VALIDATION
    # ------------------------------------------------------

    if new_password:
        try:
            validate_password(new_password, user=student)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("admin_students")

    # ------------------------------------------------------
    # SAVE
    # ------------------------------------------------------

    student.username = username

    if new_password:
        student.set_password(new_password)

    student.save()

    messages.success(
        request,
        f"Student '{student.username}' updated successfully.",
    )

    return redirect("admin_students")


# ==========================================================
# BLOCK STUDENT
# ==========================================================

@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
@admin_required
@require_POST
def block_student_view(request, user_id):

    student = get_object_or_404(
        User.objects.filter(
            is_staff=False,
            is_superuser=False,
            teacher_profile__isnull=True,
        ),
        id=user_id,
    )

    student.is_active = False
    student.save(update_fields=["is_active"])

    messages.success(
        request,
        f"Student '{student.username}' blocked successfully.",
    )

    return redirect("admin_students")


# ==========================================================
# UNBLOCK STUDENT
# ==========================================================

@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
@admin_required
@require_POST
def unblock_student_view(request, user_id):

    student = get_object_or_404(
        User.objects.filter(
            is_staff=False,
            is_superuser=False,
            teacher_profile__isnull=True,
        ),
        id=user_id,
    )

    student.is_active = True
    student.save(update_fields=["is_active"])

    messages.success(
        request,
        f"Student '{student.username}' unblocked successfully.",
    )

    return redirect("admin_students")


# ==========================================================
# DELETE STUDENT
# ==========================================================

@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
@admin_required
@require_POST
def delete_student_view(request, user_id):

    student = get_object_or_404(
        User.objects.filter(
            is_staff=False,
            is_superuser=False,
            teacher_profile__isnull=True,
        ),
        id=user_id,
    )

    username = student.username

    try:
        student.delete()

    except ProtectedError:
        messages.error(
            request,
            (
                f"Student '{username}' has purchase or order "
                "records that protect this account from deletion. "
                "Keep the account and block it if access must stop."
            ),
        )
        return redirect("admin_students")

    messages.success(
        request,
        f"Student '{username}' deleted successfully.",
    )

    return redirect("admin_students")


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

# ==========================================================
# COUPON MANAGEMENT
# ==========================================================
# Multi Checkout pricing/eligibility is calculated in helpers.py.
# Views only receive validated data and save/update the coupon.


# ==========================================================
# COUPON LISTING
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_coupons_view(request):
    """
    Display the Admin Coupons page.

    Search, filtering, sorting, pagination and statistics
    are handled by helpers.py.
    """

    context = get_coupon_listing_context(
        request
    )

    return render(
        request,
        "admins/coupons/coupons.html",
        context,
    )


# ==========================================================
# CREATE COUPON
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def create_coupon_view(request):
    """
    Create a new coupon.

    Validation and data preparation are handled by
    helpers.py.
    """

    # ------------------------------------------------------
    # GET
    # ------------------------------------------------------

    if request.method == "GET":

        context = build_coupon_form_context(
            request=request,
            coupon=None,
            form_data=None,
        )

        return render(
            request,
            "admins/coupons/create_coupon.html",
            context,
        )

    # ------------------------------------------------------
    # POST VALIDATION
    # ------------------------------------------------------

    data, errors = parse_and_validate_coupon(
        request=request,
        coupon=None,
    )

    # ------------------------------------------------------
    # VALIDATION ERRORS
    # ------------------------------------------------------

    if errors:

        add_coupon_errors_to_messages(
            request,
            errors,
        )

        context = build_coupon_form_context(
            request=request,
            coupon=None,
            form_data=request.POST,
        )

        return render(
            request,
            "admins/coupons/create_coupon.html",
            context,
        )

    # ------------------------------------------------------
    # SAVE
    # ------------------------------------------------------

    try:

        with transaction.atomic():

            coupon = create_coupon_instance(
                data
            )

            save_coupon_batch_rules(
                coupon=coupon,
                coupon_type=data["coupon_type"],
                selected_batch=data.get(
                    "selected_batch"
                ),
                enabled_batch_ids=data.get(
                    "enabled_batch_ids"
                ),
            )

        messages.success(
            request,
            f"Coupon {coupon.code} created successfully.",
        )

        return redirect(
            "admin_coupons"
        )

    except ValidationError as exc:

        add_coupon_errors_to_messages(
            request,
            exc.messages,
        )

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            "Unable to create coupon. Please try again.",
        )

    # ------------------------------------------------------
    # RE-RENDER AFTER SAVE ERROR
    # ------------------------------------------------------

    context = build_coupon_form_context(
        request=request,
        coupon=None,
        form_data=request.POST,
    )

    return render(
        request,
        "admins/coupons/create_coupon.html",
        context,
    )


# ==========================================================
# EDIT COUPON
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def edit_coupon_view(request, coupon_id):
    """
    Edit an existing coupon.

    Existing usage information is preserved.
    """

    # ------------------------------------------------------
    # GET COUPON
    # ------------------------------------------------------

    coupon = get_object_or_404(
        Coupon,
        id=coupon_id,
    )

    # ------------------------------------------------------
    # GET
    # ------------------------------------------------------

    if request.method == "GET":

        context = build_coupon_form_context(
            request=request,
            coupon=coupon,
            form_data=None,
        )

        return render(
            request,
            "admins/coupons/edit_coupon.html",
            context,
        )

    # ------------------------------------------------------
    # POST VALIDATION
    # ------------------------------------------------------

    data, errors = parse_and_validate_coupon(
        request=request,
        coupon=coupon,
    )

    # ------------------------------------------------------
    # VALIDATION ERRORS
    # ------------------------------------------------------

    if errors:

        add_coupon_errors_to_messages(
            request,
            errors,
        )

        context = build_coupon_form_context(
            request=request,
            coupon=coupon,
            form_data=request.POST,
        )

        return render(
            request,
            "admins/coupons/edit_coupon.html",
            context,
        )

    # ------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------

    try:

        with transaction.atomic():

            locked_coupon = (
                Coupon.objects
                .select_for_update()
                .get(
                    id=coupon.id
                )
            )

            update_coupon_instance(
                locked_coupon,
                data,
            )

            save_coupon_batch_rules(
                coupon=locked_coupon,
                coupon_type=data["coupon_type"],
                selected_batch=data.get(
                    "selected_batch"
                ),
                enabled_batch_ids=data.get(
                    "enabled_batch_ids"
                ),
            )

            coupon = locked_coupon

        messages.success(
            request,
            f"Coupon {coupon.code} updated successfully.",
        )

        return redirect(
            "admin_coupons"
        )

    except ValidationError as exc:

        add_coupon_errors_to_messages(
            request,
            exc.messages,
        )

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            "Unable to update coupon. Please try again.",
        )

    # ------------------------------------------------------
    # RE-RENDER AFTER UPDATE ERROR
    # ------------------------------------------------------

    context = build_coupon_form_context(
        request=request,
        coupon=coupon,
        form_data=request.POST,
    )

    return render(
        request,
        "admins/coupons/edit_coupon.html",
        context,
    )


# ==========================================================
# ACTIVATE / DEACTIVATE COUPON
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def toggle_coupon_status_view(
    request,
    coupon_id,
):
    """
    Activate or deactivate a coupon.

    POST only.
    """

    try:

        with transaction.atomic():

            coupon = (
                Coupon.objects
                .select_for_update()
                .get(
                    id=coupon_id
                )
            )

            toggle_coupon_status(
                coupon
            )

            coupon.refresh_from_db()

        if coupon.is_active:

            messages.success(
                request,
                f"Coupon {coupon.code} activated successfully.",
            )

        else:

            messages.success(
                request,
                f"Coupon {coupon.code} deactivated successfully.",
            )

    except Coupon.DoesNotExist:

        messages.error(
            request,
            "Coupon not found.",
        )

    except ValidationError as exc:

        add_coupon_errors_to_messages(
            request,
            exc.messages,
        )

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            "Unable to change coupon status.",
        )

    return redirect(
        "admin_coupons"
    )


# ==========================================================
# DELETE COUPON
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def delete_coupon_view(
    request,
    coupon_id,
):
    """
    Permanently delete a coupon only when it has never
    been used.

    Used coupons are retained for historical integrity.
    """

    coupon = get_object_or_404(
        Coupon,
        id=coupon_id,
    )

    # ------------------------------------------------------
    # DELETE PERMISSION CHECK
    # ------------------------------------------------------

    if not can_delete_coupon(
        coupon
    ):

        messages.error(
            request,
            (
                f"Coupon {coupon.code} has already been "
                f"used {coupon.used_count} time(s) and "
                "cannot be deleted. Deactivate it instead."
            ),
        )

        return redirect(
            "admin_coupons"
        )

    coupon_code = coupon.code

    # ------------------------------------------------------
    # DELETE WITH ROW LOCK
    # ------------------------------------------------------

    try:

        with transaction.atomic():

            locked_coupon = (
                Coupon.objects
                .select_for_update()
                .get(
                    id=coupon.id
                )
            )

            if not can_delete_coupon(
                locked_coupon
            ):

                messages.error(
                    request,
                    (
                        f"Coupon {locked_coupon.code} has "
                        "already been used and cannot be deleted."
                    ),
                )

                return redirect(
                    "admin_coupons"
                )

            delete_coupon(
                locked_coupon
            )

        messages.success(
            request,
            f"Coupon {coupon_code} deleted successfully.",
        )

    except Coupon.DoesNotExist:

        messages.error(
            request,
            "Coupon not found.",
        )

    except ValidationError as exc:

        add_coupon_errors_to_messages(
            request,
            exc.messages,
        )

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            "Unable to delete coupon. Please try again.",
        )

    return redirect(
        "admin_coupons"
    )
    
# ==========================================================
# ORDER MANAGEMENT
# ==========================================================


@login_required(login_url="admin_signin")
@admin_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_orders_view(request):
    """
    Display the Admin Order Management listing.

    Search, filters, summary statistics and pagination
    are handled by helpers.py.
    """

    context = get_admin_order_listing_context(
        request
    )

    return render(
        request,
        "admins/orders/order_list.html",
        context,
    )


# ==========================================================
# ADMIN ORDER DETAIL
# ==========================================================


@login_required(login_url="admin_signin")
@admin_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_order_detail_view(
    request,
    order_id,
):
    """
    Display the complete Admin Order Details page.

    All order-detail preparation is handled by helpers.py.
    """

    order = get_admin_order_detail(
        order_id
    )

    return render(
        request,
        "admins/orders/order_detail.html",
        {
            "order": order,

            # ==================================================
            # REFUND INFORMATION
            # ==================================================

            "refunds": getattr(
                order,
                "admin_refunds",
                [],
            ),

            "refunded_amount": getattr(
                order,
                "admin_refunded_amount",
                Decimal("0.00"),
            ),

            "net_paid": getattr(
                order,
                "admin_net_paid",
                order.final_amount,
            ),

            "refund_count": getattr(
                order,
                "admin_refund_count",
                0,
            ),

            "timeline_events": getattr(
                order,
                "admin_timeline_events",
                [],
            ),
        },
    )

# ==========================================================
# CREATE / RESTORE TEST PAYMENT ACCESS
# ==========================================================


@login_required(login_url="admin_signin")
@admin_required
@require_POST
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_create_test_payment_scenario_view(
    request,
    order_id,
):
    """
    Create or restore a paid payment state for Admin Order
    Management testing.

    This action supports TWO payment situations:

        1. SCENARIO payment
           -> No real Razorpay payment ID
           -> Used for local testing

        2. REAL RAZORPAY payment
           -> Existing real Razorpay payment ID
           -> Existing real payment is preserved
           -> Never converted into SCENARIO

    Purpose:

        This action is used to test/recover the complete:

            Payment
                ->
            Order
                ->
            Student Access

        workflow.

    Important rules:

        - A real Razorpay payment ID is NEVER removed.
        - A real Razorpay payment is NEVER converted into
          a Scenario payment.
        - No fake Razorpay payment ID is created.
        - This action NEVER calls Razorpay.
        - REFUNDED purchases cannot be reactivated.
        - REFUNDED and PARTIALLY_REFUNDED orders remain protected.
        - REVOKED student access can be restored to ACTIVE.
    """

    # ------------------------------------------------------
    # LOCAL MODEL IMPORTS
    # ------------------------------------------------------

    from orders.models import (
        Order,
        Payment,
        Invoice,
        StudentBatchPurchase,
        OrderTimelineEvent,
    )

    try:

        with transaction.atomic():

            # --------------------------------------------------
            # LOCK ORDER
            # --------------------------------------------------

            order = (
                Order.objects
                .select_for_update()
                .get(
                    pk=order_id,
                )
            )

            # --------------------------------------------------
            # REFUND SAFETY
            # --------------------------------------------------

            if order.status in {
                Order.Status.REFUNDED,
                Order.Status.PARTIALLY_REFUNDED,
            }:

                messages.error(
                    request,
                    (
                        "A refunded or partially refunded "
                        "order cannot be restored through "
                        "the test payment action."
                    ),
                )

                return redirect(
                    "admin_order_detail",
                    order_id=order.id,
                )

            # --------------------------------------------------
            # ORDER STATES
            # --------------------------------------------------
            #
            # Scenario payments are allowed for:
            #
            #     PENDING
            #     PAYMENT_PROCESSING
            #     PAYMENT_FAILED
            #     CANCELLED
            #
            # A real already-paid order is also allowed so that
            # student access can be restored when the student
            # has already completed a real Razorpay payment.
            #
            # --------------------------------------------------

            allowed_statuses = {
                Order.Status.PENDING,
                Order.Status.PAYMENT_PROCESSING,
                Order.Status.PAYMENT_FAILED,
                Order.Status.CANCELLED,
                Order.Status.PAID,
            }

            if order.status not in allowed_statuses:

                messages.error(
                    request,
                    (
                        "This payment recovery action is not "
                        "available for the current order status."
                    ),
                )

                return redirect(
                    "admin_order_detail",
                    order_id=order.id,
                )

            # --------------------------------------------------
            # ORDER ITEMS
            # --------------------------------------------------

            order_items = list(
                order.items
                .select_related("batch")
                .all()
            )

            if not order_items:

                messages.error(
                    request,
                    "This order has no order items.",
                )

                return redirect(
                    "admin_order_detail",
                    order_id=order.id,
                )

            # --------------------------------------------------
            # GET PAYMENT
            # --------------------------------------------------

            payment = (
                Payment.objects
                .select_for_update()
                .filter(
                    order=order,
                )
                .first()
            )

            # --------------------------------------------------
            # DETERMINE PAYMENT TYPE
            # --------------------------------------------------

            is_real_razorpay_payment = (
                payment is not None
                and bool(
                    payment.razorpay_payment_id
                )
            )

            # --------------------------------------------------
            # CREATE PAYMENT IF MISSING
            # --------------------------------------------------

            if payment is None:

                payment = Payment.objects.create(
                    order=order,
                    payment_source=(
                        Payment.Source.SCENARIO
                    ),
                    razorpay_order_id=None,
                    razorpay_payment_id=None,
                    amount=order.final_amount,
                    currency=order.currency,
                    status=(
                        Payment.Status.CAPTURED
                    ),
                    captured_at=timezone.now(),
                    failure_reason="",
                )

                is_real_razorpay_payment = False

            # --------------------------------------------------
            # REAL RAZORPAY PAYMENT
            # --------------------------------------------------
            #
            # IMPORTANT:
            #
            # If a real Razorpay payment ID already exists,
            # preserve the payment exactly as a real payment.
            #
            # NEVER:
            #
            #     payment_source = SCENARIO
            #
            # NEVER:
            #
            #     razorpay_payment_id = None
            #
            # --------------------------------------------------

            elif is_real_razorpay_payment:

                # --------------------------------------------------
                # PRESERVE REAL RAZORPAY PAYMENT
                # --------------------------------------------------

                payment.payment_source = (
                    Payment.Source.RAZORPAY
                )

                payment.status = (
                    Payment.Status.CAPTURED
                )

                payment.amount = (
                    order.final_amount
                )

                payment.currency = (
                    order.currency
                )

                payment.captured_at = (
                    payment.captured_at
                    or timezone.now()
                )

                payment.failure_reason = ""

                # --------------------------------------------------
                # IMPORTANT:
                #
                # razorpay_payment_id is intentionally NOT changed.
                #
                # The real payment ID stays exactly as it is.
                # --------------------------------------------------

                payment.save(
                    update_fields=[
                        "payment_source",
                        "status",
                        "amount",
                        "currency",
                        "captured_at",
                        "failure_reason",
                        "updated_at",
                    ]
                )

            # --------------------------------------------------
            # EXISTING SCENARIO / NON-RAZORPAY PAYMENT
            # --------------------------------------------------

            else:

                payment.payment_source = (
                    Payment.Source.SCENARIO
                )

                payment.razorpay_payment_id = None

                payment.status = (
                    Payment.Status.CAPTURED
                )

                payment.amount = (
                    order.final_amount
                )

                payment.currency = (
                    order.currency
                )

                payment.captured_at = (
                    payment.captured_at
                    or timezone.now()
                )

                payment.failure_reason = ""

                payment.save(
                    update_fields=[
                        "payment_source",
                        "razorpay_payment_id",
                        "status",
                        "amount",
                        "currency",
                        "captured_at",
                        "failure_reason",
                        "updated_at",
                    ]
                )

            # --------------------------------------------------
            # MARK ORDER AS PAID
            # --------------------------------------------------

            order.status = (
                Order.Status.PAID
            )

            order.paid_at = (
                order.paid_at
                or timezone.now()
            )

            order.save(
                update_fields=[
                    "status",
                    "paid_at",
                    "updated_at",
                ]
            )

            # --------------------------------------------------
            # PAYMENT SUCCESS TIMELINE
            # --------------------------------------------------

            create_order_timeline_event(
                order=order,
                payment=payment,
                event_type=(
                    OrderTimelineEvent
                    .EventType
                    .PAYMENT_SUCCEEDED
                ),
                title="Payment Successful",
                description=(
                    "Payment was captured successfully."
                ),
                metadata={
                    "payment_source": (
                        payment.payment_source
                    ),
                    "amount": str(
                        payment.amount
                    ),
                    "currency": (
                        payment.currency
                    ),
                    "razorpay_payment_id": (
                        payment.razorpay_payment_id
                    ),
                },
            )

            # --------------------------------------------------
            # ENSURE INVOICE
            # --------------------------------------------------

            invoice = (
                Invoice.objects
                .filter(
                    order=order,
                )
                .first()
            )

            if invoice is None:

                Invoice.objects.create(
                    order=order,
                    subtotal=order.subtotal,
                    coupon_discount=(
                        order.total_coupon_discount
                    ),
                    total_discount=(
                        order.total_discount
                    ),
                    final_amount=(
                        order.final_amount
                    ),
                    currency=order.currency,
                )

            # --------------------------------------------------
            # GRANT / RESTORE STUDENT ACCESS
            # --------------------------------------------------

            for order_item in order_items:

                # --------------------------------------------------
                # FIND PURCHASE FOR THIS ORDER ITEM
                # --------------------------------------------------

                purchase = (
                    StudentBatchPurchase.objects
                    .filter(
                        order_item=order_item,
                    )
                    .first()
                )

                # --------------------------------------------------
                # CREATE PURCHASE IF MISSING
                # --------------------------------------------------

                if purchase is None:

                    existing_purchase = (
                        StudentBatchPurchase.objects
                        .filter(
                            student=order.user,
                            batch=order_item.batch,
                        )
                        .first()
                    )

                    # --------------------------------------------------
                    # EXISTING PURCHASE FOR SAME STUDENT + BATCH
                    # --------------------------------------------------

                    if existing_purchase is not None:

                        # --------------------------------------------------
                        # NEVER REACTIVATE REFUNDED PURCHASE
                        # --------------------------------------------------

                        if (
                            existing_purchase.status
                            == (
                                StudentBatchPurchase
                                .Status.REFUNDED
                            )
                        ):

                            messages.error(
                                request,
                                (
                                    "Access could not be granted "
                                    "because this batch already "
                                    "has a refunded purchase."
                                ),
                            )

                            raise ValueError(
                                "Refunded batch purchase conflict."
                            )

                        # --------------------------------------------------
                        # PREVENT DUPLICATE PURCHASE
                        # --------------------------------------------------

                        messages.error(
                            request,
                            (
                                "Access could not be granted "
                                "because this student already "
                                "has a purchase for one of the "
                                "batches in this order."
                            ),
                        )

                        raise ValueError(
                            "Existing student batch purchase conflict."
                        )

                    # --------------------------------------------------
                    # CREATE ACTIVE PURCHASE
                    # --------------------------------------------------

                    StudentBatchPurchase.objects.create(
                        student=order.user,
                        batch=order_item.batch,
                        order=order,
                        order_item=order_item,
                        status=(
                            StudentBatchPurchase
                            .Status.ACTIVE
                        ),
                        refunded_at=None,
                    )

                # --------------------------------------------------
                # EXISTING PURCHASE
                # --------------------------------------------------

                else:

                    # --------------------------------------------------
                    # NEVER REACTIVATE REFUNDED PURCHASE
                    # --------------------------------------------------

                    if (
                        purchase.status
                        == (
                            StudentBatchPurchase
                            .Status.REFUNDED
                        )
                    ):

                        messages.error(
                            request,
                            (
                                "A refunded batch purchase "
                                "cannot be reactivated."
                            ),
                        )

                        raise ValueError(
                            "Refunded batch purchase cannot be reactivated."
                        )

                    # --------------------------------------------------
                    # ACTIVE / REVOKED -> ACTIVE
                    # --------------------------------------------------

                    purchase.status = (
                        StudentBatchPurchase
                        .Status.ACTIVE
                    )

                    purchase.refunded_at = None

                    purchase.save(
                        update_fields=[
                            "status",
                            "refunded_at",
                        ]
                    )

            # --------------------------------------------------
            # ACCESS GRANTED TIMELINE
            # --------------------------------------------------

            create_order_timeline_event(
                order=order,
                payment=payment,
                event_type=(
                    OrderTimelineEvent
                    .EventType
                    .ACCESS_GRANTED
                ),
                title="Learning Access Granted",
                description=(
                    "Learning access was granted for the "
                    "batches included in the paid order."
                ),
                metadata={
                    "order_item_count": len(
                        order_items
                    ),
                    "payment_source": (
                        payment.payment_source
                    ),
                    "razorpay_payment_id": (
                        payment.razorpay_payment_id
                    ),
                },
            )

        # ------------------------------------------------------
        # SUCCESS MESSAGE
        # ------------------------------------------------------

        if is_real_razorpay_payment:

            messages.success(
                request,
                (
                    f"Real Razorpay payment for order "
                    f"{order.order_number} was preserved "
                    "and student access has been restored."
                ),
            )

        else:

            messages.success(
                request,
                (
                    f"Test payment scenario created for "
                    f"order {order.order_number}. "
                    "Order is now paid and student access "
                    "has been granted."
                ),
            )

    # ----------------------------------------------------------
    # ORDER NOT FOUND
    # ----------------------------------------------------------

    except Order.DoesNotExist:

        messages.error(
            request,
            "Order not found.",
        )

    # ----------------------------------------------------------
    # BUSINESS LOGIC ERROR
    # ----------------------------------------------------------

    except ValueError:

        # Detailed error message was already added.

        pass

    # ----------------------------------------------------------
    # UNEXPECTED ERROR
    # ----------------------------------------------------------

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            (
                "Unable to process the payment/access "
                "recovery action. Please try again."
            ),
        )

    # ------------------------------------------------------
    # RETURN
    # ------------------------------------------------------

    return redirect(
        "admin_order_detail",
        order_id=order_id,
    )

# ==========================================================
# REVERT PAYMENT / REMOVE ACCESS
# ==========================================================


@login_required(login_url="admin_signin")
@admin_required
@require_POST
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_revert_payment_view(
    request,
    order_id,
):
    """
    Revert a paid order from Admin Order Management.

    Result:

        Order
            -> PAYMENT_FAILED

        Payment
            -> FAILED

        StudentBatchPurchase
            ACTIVE
            -> REVOKED

    Refund records are NOT modified.

    REFUNDED and PARTIALLY_REFUNDED orders are protected.

    The Order row is locked separately so PostgreSQL does
    not receive a FOR UPDATE lock across nullable joins.
    """

    # ------------------------------------------------------
    # LOCAL MODEL IMPORTS
    # ------------------------------------------------------

    from orders.models import (
        Order,
        Payment,
        StudentBatchPurchase,
        Invoice,
        OrderTimelineEvent,
    )

    try:

        with transaction.atomic():

            # --------------------------------------------------
            # LOCK ONLY THE ORDER ROW
            # --------------------------------------------------

            order = (
                Order.objects
                .select_for_update()
                .get(
                    pk=order_id,
                )
            )

            # --------------------------------------------------
            # REFUND SAFETY
            # --------------------------------------------------

            if order.status in {
                Order.Status.REFUNDED,
                Order.Status.PARTIALLY_REFUNDED,
            }:

                messages.error(
                    request,
                    (
                        "Refunded or partially refunded "
                        "orders cannot be reverted from "
                        "Order Management."
                    ),
                )

                return redirect(
                    "admin_order_detail",
                    order_id=order.id,
                )

            # --------------------------------------------------
            # ONLY PAID ORDERS CAN BE REVERTED
            # --------------------------------------------------

            if order.status != Order.Status.PAID:

                messages.error(
                    request,
                    "Only paid orders can be reverted.",
                )

                return redirect(
                    "admin_order_detail",
                    order_id=order.id,
                )

            # --------------------------------------------------
            # GET PAYMENT SEPARATELY
            # --------------------------------------------------

            payment = (
                Payment.objects
                .filter(
                    order=order,
                )
                .first()
            )

            # --------------------------------------------------
            # PAYMENT -> FAILED
            # --------------------------------------------------

            if payment is not None:

                payment.status = (
                    Payment.Status.FAILED
                )

                payment.failure_reason = (
                    "Payment reverted by admin."
                )

                payment.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "updated_at",
                    ]
                )

                create_order_timeline_event(
                    order=order,
                    payment=payment,
                    event_type=(
                        OrderTimelineEvent.EventType.PAYMENT_FAILED
                    ),
                    title="Payment Failed",
                    description=(
                        "Payment was reverted by an administrator."
                    ),
                    metadata={
                        "reason": "Payment reverted by admin.",
                    },
                )

            # --------------------------------------------------
            # REMOVE INVOICE
            # --------------------------------------------------
            #
            # Invoice has no status field.
            #
            # Therefore a manually reverted payment should
            # not leave a successful invoice attached to an
            # order that is now PAYMENT_FAILED.
            #
            # If payment is marked received again later,
            # a fresh invoice will be created.
            # --------------------------------------------------

            Invoice.objects.filter(
                order=order,
            ).delete()

            # --------------------------------------------------
            # REVOKE ACTIVE STUDENT ACCESS
            # --------------------------------------------------

            revoked_access_count = (
                StudentBatchPurchase.objects.filter(
                    order=order,
                    student=order.user,
                    status=(
                        StudentBatchPurchase
                        .Status.ACTIVE
                    ),
                ).update(
                    status=(
                        StudentBatchPurchase
                        .Status.REVOKED
                    ),
                    refunded_at=None,
                )
            )

            if revoked_access_count > 0:
                create_order_timeline_event(
                    order=order,
                    payment=payment,
                    event_type=(
                        OrderTimelineEvent.EventType.ACCESS_REVOKED
                    ),
                    title="Learning Access Revoked",
                    description=(
                        "Learning access was revoked after "
                        "the payment was reverted."
                    ),
                    metadata={
                        "revoked_access_count": (
                            revoked_access_count
                        ),
                    },
                )

            # --------------------------------------------------
            # ORDER -> PAYMENT_FAILED
            # --------------------------------------------------

            order.status = (
                Order.Status.PAYMENT_FAILED
            )

            order.paid_at = None

            order.save(
                update_fields=[
                    "status",
                    "paid_at",
                    "updated_at",
                ]
            )

        # ------------------------------------------------------
        # SUCCESS
        # ------------------------------------------------------

        messages.success(
            request,
            (
                f"Payment for order "
                f"{order.order_number} "
                "was reverted, invoice removed, "
                "and student access was revoked."
            ),
        )

    # ----------------------------------------------------------
    # ORDER NOT FOUND
    # ----------------------------------------------------------

    except Order.DoesNotExist:

        messages.error(
            request,
            "Order not found.",
        )

    # ----------------------------------------------------------
    # UNEXPECTED ERROR
    # ----------------------------------------------------------

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            (
                "Unable to revert payment. "
                "Please try again."
            ),
        )

    # ------------------------------------------------------
    # RETURN
    # ------------------------------------------------------

    return redirect(
        "admin_order_detail",
        order_id=order_id,
    )


# ==========================================================
# ADMIN ORDER SELECTION
# ==========================================================


@login_required(login_url="admin_signin")
@admin_required
@require_POST
def admin_order_selection_view(request):
    """
    Save or remove Admin Order Management selections.

    Selection belongs to the logged-in admin and is stored
    through the AdminOrderSelection helper functions.
    """

    action = (
        request.POST
        .get(
            "action",
            "",
        )
        .strip()
        .lower()
    )

    order_id = (
        request.POST
        .get(
            "order_id",
            "",
        )
        .strip()
    )

    # ------------------------------------------------------
    # SELECT ONE ORDER
    # ------------------------------------------------------

    if action == "select":

        if not order_id:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Order ID is required.",
                },
                status=400,
            )

        try:

            order_id = int(
                order_id
            )

        except (
            TypeError,
            ValueError,
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid order ID.",
                },
                status=400,
            )

        success = save_admin_order_selection(
            request.user,
            order_id,
        )

        if not success:

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Unable to select this order."
                    ),
                },
                status=400,
            )

        return JsonResponse(
            {
                "success": True,
                "selected": True,
                "order_id": order_id,
            }
        )

    # ------------------------------------------------------
    # UNSELECT ONE ORDER
    # ------------------------------------------------------

    if action == "unselect":

        if not order_id:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Order ID is required.",
                },
                status=400,
            )

        try:

            order_id = int(
                order_id
            )

        except (
            TypeError,
            ValueError,
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid order ID.",
                },
                status=400,
            )

        remove_admin_order_selection(
            request.user,
            order_id,
        )

        return JsonResponse(
            {
                "success": True,
                "selected": False,
                "order_id": order_id,
            }
        )

    # ------------------------------------------------------
    # CLEAR ALL SELECTIONS
    # ------------------------------------------------------

    if action == "clear":

        clear_admin_order_selections(
            request.user,
        )

        return JsonResponse(
            {
                "success": True,
                "cleared": True,
            }
        )

    # ------------------------------------------------------
    # INVALID ACTION
    # ------------------------------------------------------

    return JsonResponse(
        {
            "success": False,
            "message": "Invalid selection action.",
        },
        status=400,
    )


# ==========================================================
# ADMIN INVOICE DETAIL
# ==========================================================


@login_required(login_url="admin_signin")
@admin_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_invoice_detail_view(
    request,
    invoice_number,
):
    """
    Display one invoice for Admin Order Management.

    This is an admin-only invoice view.

    It is read-only.

    It does not modify:
        - Order
        - Payment
        - Student access
        - Refunds
    """

    from orders.models import Invoice

    try:

        invoice = (
            Invoice.objects
            .select_related(
                "order",
                "order__user",
                "order__payment",
            )
            .prefetch_related(
                "order__items__batch",
            )
            .get(
                invoice_number=invoice_number,
            )
        )

    except Invoice.DoesNotExist:

        messages.error(
            request,
            "Invoice not found.",
        )

        return redirect(
            "admin_orders"
        )

    return render(
        request,
        "admins/orders/invoice_detail.html",
        {
            "invoice": invoice,
        },
    )
    
# ==========================================================
# REFUND MANAGEMENT
# ==========================================================


# ==========================================================
# ADMIN REFUND LIST
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_refunds_view(request):
    """
    Display the Admin Refund Management listing.

    Refund parent statuses exposed by Admin:

        REQUESTED
        PROCESSING
        COMPLETED
        REJECTED

    Razorpay gateway failures are stored in RefundAttempt.
    They do not create a FAILED parent refund state.
    """

    context = get_admin_refund_listing_context(
        request
    )

    return render(
        request,
        "admins/refunds/refund_list.html",
        context,
    )


# ==========================================================
# ADMIN REFUND DETAIL
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_refund_detail_view(
    request,
    refund_id,
):
    """
    Display complete Admin Refund Details.

    Read-only page.

    Refund execution/rejection/reopening are handled
    by separate POST actions.
    """

    refund = get_admin_refund_detail(
        refund_id
    )

    refund.admin_type = get_admin_refund_type(
        refund
    )

    refund.admin_item_count = (
        get_admin_refund_item_count(
            refund
        )
    )

    refund.admin_amount = (
        get_admin_refund_amount(
            refund
        )
    )

    refund.admin_status_label = (
        refund.status.replace(
            "_",
            " ",
        ).title()
        if refund.status
        else ""
    )

    # ------------------------------------------------------
    # Latest gateway attempt
    # ------------------------------------------------------

    refund.admin_latest_attempt = (
        refund.attempts.first()
    )

    return render(
        request,
        "admins/refunds/refund_detail.html",
        {
            "refund": refund,
        },
    )


# ==========================================================
# ADMIN APPROVE / EXECUTE REFUND
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_approve_refund_view(
    request,
    refund_id,
):
    """
    Approve and execute a requested refund.

    The actual money movement is performed by Razorpay
    through execute_refund().

    Successful gateway result:

        Refund
            -> COMPLETED

        Student access
            -> removed for refunded items

        Order
            -> PARTIALLY_REFUNDED
               or
               REFUNDED

    Gateway failure:

        Refund
            -> REQUESTED

        RefundAttempt
            -> FAILED

        Student access
            -> unchanged

        Order
            -> unchanged
    """

    from orders.models import Refund

    refund = get_object_or_404(
        Refund,
        pk=refund_id,
    )

    # ------------------------------------------------------
    # Only REQUESTED refunds can be approved
    # ------------------------------------------------------

    if refund.status != Refund.Status.REQUESTED:

        messages.error(
            request,
            "This refund is not available for approval.",
        )

        return redirect(
            "admin_refund_detail",
            refund_id=refund.id,
        )

    try:

        execute_refund(
            refund.id
        )

        refund.refresh_from_db()

        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        if refund.status == Refund.Status.COMPLETED:

            messages.success(
                request,
                (
                    f"Refund #{refund.id} was completed "
                    "successfully."
                ),
            )

        # --------------------------------------------------
        # GATEWAY FAILURE
        # --------------------------------------------------

        else:

            messages.warning(
                request,
                (
                    f"Refund #{refund.id} could not be "
                    "completed by Razorpay. The refund "
                    "remains requested and can be retried."
                ),
            )

    except ValueError as exc:

        messages.error(
            request,
            str(exc),
        )

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            (
                "Unable to process this refund. "
                "No refund completion was recorded."
            ),
        )

    return redirect(
        "admin_refund_detail",
        refund_id=refund.id,
    )


# ==========================================================
# ADMIN RETRY REFUND
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_retry_refund_view(
    request,
    refund_id,
):
    """
    Retry a refund whose previous Razorpay attempt failed.

    The same Refund ID is reused.

    A new RefundAttempt is created by execute_refund().
    """

    from orders.models import Refund

    refund = get_object_or_404(
        Refund,
        pk=refund_id,
    )

    if refund.status != Refund.Status.REQUESTED:

        messages.error(
            request,
            (
                "Only a requested refund can be retried."
            ),
        )

        return redirect(
            "admin_refund_detail",
            refund_id=refund.id,
        )

    try:

        execute_refund(
            refund.id
        )

        refund.refresh_from_db()

        if refund.status == Refund.Status.COMPLETED:

            messages.success(
                request,
                (
                    f"Refund #{refund.id} was completed "
                    "successfully on retry."
                ),
            )

        else:

            messages.warning(
                request,
                (
                    f"Refund #{refund.id} is still requested "
                    "because the Razorpay refund attempt "
                    "did not complete."
                ),
            )

    except ValueError as exc:

        messages.error(
            request,
            str(exc),
        )

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            (
                "Unable to retry this refund."
            ),
        )

    return redirect(
        "admin_refund_detail",
        refund_id=refund.id,
    )


# ==========================================================
# ADMIN REJECT REFUND
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_reject_refund_view(
    request,
    refund_id,
):
    """
    Reject a requested refund.

    A rejection reason is mandatory.

    Rejected refunds:

        Refund
            -> REJECTED

    No Razorpay refund is performed.

    Student access remains unchanged.
    """

    from orders.models import (
        Refund,
        OrderTimelineEvent,
    )

    refund = get_object_or_404(
        Refund,
        pk=refund_id,
    )

    # ------------------------------------------------------
    # Only REQUESTED refunds can be rejected
    # ------------------------------------------------------

    if refund.status != Refund.Status.REQUESTED:

        messages.error(
            request,
            (
                "Only a requested refund can be rejected."
            ),
        )

        return redirect(
            "admin_refund_detail",
            refund_id=refund.id,
        )

    rejection_reason = (
        request.POST.get(
            "rejection_reason",
            "",
        )
        .strip()
    )

    if not rejection_reason:

        messages.error(
            request,
            (
                "A rejection reason is required."
            ),
        )

        return redirect(
            "admin_refund_detail",
            refund_id=refund.id,
        )

    # ------------------------------------------------------
    # Save rejection
    # ------------------------------------------------------

    try:

        with transaction.atomic():

            locked_refund = (
                Refund.objects
                .select_for_update()
                .get(
                    pk=refund.id,
                )
            )

            # Re-check after acquiring lock

            if (
                locked_refund.status
                != Refund.Status.REQUESTED
            ):

                messages.error(
                    request,
                    (
                        "This refund is no longer "
                        "available for rejection."
                    ),
                )

                return redirect(
                    "admin_refund_detail",
                    refund_id=locked_refund.id,
                )

            locked_refund.status = (
                Refund.Status.REJECTED
            )

            locked_refund.admin_note = (
                rejection_reason
            )

            locked_refund.processed_at = (
                timezone.now()
            )

            locked_refund.save(
                update_fields=[
                    "status",
                    "admin_note",
                    "processed_at",
                ]
            )

            create_order_timeline_event(
                order=locked_refund.order,
                refund=locked_refund,
                event_type=(
                    OrderTimelineEvent.EventType.REFUND_REJECTED
                ),
                title="Refund Rejected",
                description=(
                    "The refund request was rejected by "
                    "an administrator."
                ),
                metadata={
                    "rejection_reason": rejection_reason,
                },
            )

        messages.success(
            request,
            (
                f"Refund #{refund.id} was rejected."
            ),
        )

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            (
                "Unable to reject this refund."
            ),
        )

    return redirect(
        "admin_refund_detail",
        refund_id=refund.id,
    )


# ==========================================================
# ADMIN REOPEN REJECTED REFUND
# ==========================================================

@login_required(login_url="admin_signin")
@admin_required
@require_POST
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def admin_reopen_refund_view(
    request,
    refund_id,
):
    """
    Reopen a rejected refund.

    IMPORTANT:

        Reopening keeps the SAME Refund ID.

        It does not create a new Refund.

    A new Refund ID is created only when the student/admin
    creates a genuinely new refund request.
    """

    from orders.models import (
        Refund,
        OrderTimelineEvent,
    )

    try:

        with transaction.atomic():

            refund = (
                Refund.objects
                .select_for_update()
                .get(
                    pk=refund_id,
                )
            )

            # --------------------------------------------------
            # Only rejected refunds can be reopened
            # --------------------------------------------------

            if (
                refund.status
                != Refund.Status.REJECTED
            ):

                messages.error(
                    request,
                    (
                        "Only a rejected refund can be reopened."
                    ),
                )

                return redirect(
                    "admin_refund_detail",
                    refund_id=refund.id,
                )

            # --------------------------------------------------
            # Reopen
            # --------------------------------------------------

            refund.status = (
                Refund.Status.REQUESTED
            )

            refund.processed_at = None

            refund.save(
                update_fields=[
                    "status",
                    "processed_at",
                ]
            )

            create_order_timeline_event(
                order=refund.order,
                refund=refund,
                event_type=(
                    OrderTimelineEvent.EventType.REFUND_REOPENED
                ),
                title="Refund Reopened",
                description=(
                    "The previously rejected refund request "
                    "was reopened for review."
                ),
            )

        messages.success(
            request,
            (
                f"Refund #{refund.id} was reopened "
                "successfully."
            ),
        )

    except Refund.DoesNotExist:

        messages.error(
            request,
            "Refund not found.",
        )

        return redirect(
            "admin_refunds"
        )

    except Exception:

        import traceback

        traceback.print_exc()

        messages.error(
            request,
            (
                "Unable to reopen this refund."
            ),
        )

    return redirect(
        "admin_refund_detail",
        refund_id=refund.id,
    )

# ==========================================================
# ADMIN COURSE BUILDER ENTRY POINT
# ==========================================================

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def admin_course_builder_entry_view(request, batch_id, subject_id):

    # ------------------------------------------------------
    # Validate selected batch
    # ------------------------------------------------------

    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    # ------------------------------------------------------
    # Validate that the subject belongs to this batch
    # ------------------------------------------------------

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    # ------------------------------------------------------
    # Redirect to the shared Course Builder
    # ------------------------------------------------------

    return redirect(
        "courses:course_builder",
        batch_id=batch.id,
        subject_id=subject.id,
    )