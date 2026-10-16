from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash)
from datetime import date
from django.core.validators import validate_email
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.cache import cache_control
from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
import re

from admins.models import (
    Batch,
    Subject,
    FAQVideo,
)

from teachers.models import (
    Teacher,
    TeacherBatch,
    TeacherSubject,
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

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_course_builder_entry_view(
    request,
    batch_id,
    subject_id,
):

    # ========================================================
    # TEACHER PROFILE CHECK
    # ========================================================

    if not hasattr(request.user, "teacher_profile"):
        messages.error(
            request,
            "Access denied.",
        )
        return redirect("teacher_login")

    teacher = request.user.teacher_profile

    # ========================================================
    # BATCH
    # ========================================================

    batch = get_object_or_404(
        Batch,
        id=batch_id,
    )

    # ========================================================
    # SUBJECT
    # ========================================================

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
    )

    # ========================================================
    # TEACHER BATCH ASSIGNMENT
    # ========================================================

    get_object_or_404(
        TeacherBatch,
        teacher=teacher,
        batch=batch,
        is_active=True,
    )

    # ========================================================
    # TEACHER SUBJECT ASSIGNMENT
    # ========================================================

    get_object_or_404(
        TeacherSubject,
        teacher=teacher,
        batch=batch,
        subject=subject,
        is_active=True,
    )

    # ========================================================
    # REDIRECT TO SHARED COURSE BUILDER
    # ========================================================

    return redirect(
        "courses:course_builder",
        batch_id=batch.id,
        subject_id=subject.id,
    )



# ============================================================
# TEACHER MY PROFILE
# ============================================================

# ============================================================
# TEACHER MY PROFILE - READ-ONLY DISPLAY
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_my_profile_view(request):
    if not hasattr(request.user, "teacher_profile"):
        messages.error(request, "Access denied.")
        return redirect("teacher_login")

    teacher = request.user.teacher_profile

    if teacher.is_blocked:
        logout(request)
        messages.error(
            request,
            "Your teacher account has been blocked.",
        )
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    completion_fields = [
        teacher.date_of_birth,
        teacher.gender,
        teacher.qualification,
        teacher.specialization,
        teacher.bio,
        teacher.profile_image,
    ]

    completed_count = sum(bool(value) for value in completion_fields)

    profile_completion = round(
        completed_count / len(completion_fields) * 100
    )

    context = {
        "teacher": teacher,
        "profile_completion": profile_completion,
    }

    return render(
        request,
        "teachers/profile/my_profile.html",
        context,
    )


# ============================================================
# TEACHER EDIT PROFILE
# ============================================================


@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_edit_profile_view(request):
    """
    Allow the logged-in teacher to update their own profile.

    Protected fields:
    - teacher_id
    - full_name
    - email
    - phone_number
    - is_first_login
    - is_blocked
    - profile_completed
    - created_by
    """

    # --------------------------------------------------
    # 1. CHECK TEACHER ACCESS
    # --------------------------------------------------

    try:
        teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        messages.error(
            request,
            "Your teacher profile could not be found. Please log in again.",
        )
        return redirect("teacher_login")

    if teacher.is_blocked:
        logout(request)
        messages.error(
            request,
            "Your teacher account has been blocked. Please contact the administrator.",
        )
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    # --------------------------------------------------
    # 2. FIELDS THE TEACHER MAY EDIT
    # --------------------------------------------------

    editable_fields = [
        "date_of_birth",
        "gender",
        "alternate_phone",
        "emergency_contact_name",
        "emergency_contact_relationship",
        "emergency_contact_phone",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
        "qualification",
        "institution_name",
        "graduation_year",
        "additional_qualifications",
        "specialization",
        "qualified_subjects",
        "experience",
        "previous_institution",
        "bio",
        "language",
        "linkedin",
        "website",
    ]

    # --------------------------------------------------
    # 3. PREPARE EXISTING VALUES
    # --------------------------------------------------

    form_values = {}

    for field_name in editable_fields:
        value = getattr(teacher, field_name)

        if field_name == "date_of_birth" and value:
            form_values[field_name] = value.isoformat()
        elif value is None:
            form_values[field_name] = ""
        else:
            form_values[field_name] = str(value)

    errors = {}

    # --------------------------------------------------
    # 4. HANDLE FORM SUBMISSION
    # --------------------------------------------------

    if request.method == "POST":

        # Read submitted values without modifying protected fields.
        for field_name in editable_fields:
            form_values[field_name] = request.POST.get(
                field_name, ""
            ).strip()

        # ----------------------------------------------
        # DATE OF BIRTH
        # ----------------------------------------------

        parsed_dob = None
        dob_value = form_values["date_of_birth"]

        if dob_value:
            try:
                parsed_dob = date.fromisoformat(dob_value)

                if parsed_dob >= date.today():
                    errors["date_of_birth"] = (
                        "Date of birth must be in the past."
                    )

            except ValueError:
                errors["date_of_birth"] = (
                    "Enter a valid date of birth."
                )

        # ----------------------------------------------
        # GRADUATION YEAR
        # ----------------------------------------------

        parsed_graduation_year = None
        graduation_value = form_values["graduation_year"]

        if graduation_value:
            try:
                parsed_graduation_year = int(graduation_value)

                if not (
                    1900
                    <= parsed_graduation_year
                    <= date.today().year + 10
                ):
                    errors["graduation_year"] = (
                        "Enter a valid graduation year."
                    )

            except ValueError:
                errors["graduation_year"] = (
                    "Graduation year must be a whole number."
                )

        # ----------------------------------------------
        # TEACHING EXPERIENCE
        # ----------------------------------------------

        parsed_experience = None
        experience_value = form_values["experience"]

        if experience_value:
            try:
                parsed_experience = int(experience_value)

                if not 0 <= parsed_experience <= 80:
                    errors["experience"] = (
                        "Experience must be between 0 and 80 years."
                    )

            except ValueError:
                errors["experience"] = (
                    "Experience must be a whole number."
                )
        else:
            errors["experience"] = (
                "Please enter your years of teaching experience."
            )

        # ----------------------------------------------
        # ALTERNATE AND EMERGENCY MOBILE NUMBERS
        # ----------------------------------------------

        for field_name, label in (
            ("alternate_phone", "Alternate mobile number"),
            ("emergency_contact_phone", "Emergency contact number"),
        ):
            phone = form_values[field_name]

            if phone and not re.fullmatch(r"[6-9]\d{9}", phone):
                errors[field_name] = (
                    f"{label} must contain exactly 10 digits "
                    "and start with 6, 7, 8, or 9."
                )

        alternate_phone = form_values["alternate_phone"]

        if (
            alternate_phone
            and alternate_phone == teacher.phone_number
        ):
            errors["alternate_phone"] = (
                "Alternate mobile number must differ from your primary number."
            )

        # ----------------------------------------------
        # PROFILE IMAGE VALIDATION
        # ----------------------------------------------

        uploaded_image = request.FILES.get("profile_image")

        if uploaded_image:
            allowed_extensions = (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
            )

            if not uploaded_image.name.lower().endswith(
                allowed_extensions
            ):
                errors["profile_image"] = (
                    "Upload a JPG, JPEG, PNG, or WEBP image."
                )

            elif uploaded_image.size > 5 * 1024 * 1024:
                errors["profile_image"] = (
                    "The profile image must be 5 MB or smaller."
                )

            else:
                try:
                    uploaded_image.seek(0)

                    with Image.open(uploaded_image) as image:
                        if image.format not in (
                            "JPEG",
                            "PNG",
                            "WEBP",
                        ):
                            errors["profile_image"] = (
                                "The uploaded image format is not supported."
                            )
                        else:
                            image.verify()

                except (
                    UnidentifiedImageError,
                    OSError,
                    ValueError,
                ):
                    errors["profile_image"] = (
                        "The uploaded file is not a valid image."
                    )

                finally:
                    uploaded_image.seek(0)

        # ----------------------------------------------
        # CHECK MODEL FIELD LENGTHS
        # ----------------------------------------------

        for field_name in editable_fields:
            model_field = Teacher._meta.get_field(field_name)
            max_length = getattr(model_field, "max_length", None)
            value = form_values[field_name]

            if max_length and len(value) > max_length:
                errors[field_name] = (
                    f"This field cannot exceed {max_length} characters."
                )

        # --------------------------------------------------
        # 5. VALIDATE AND SAVE
        # --------------------------------------------------

        if not errors:
            try:
                # Apply editable form values to this teacher only.
                for field_name in editable_fields:
                    setattr(
                        teacher,
                        field_name,
                        form_values[field_name],
                    )

                # Convert typed fields to their correct Python values.
                teacher.date_of_birth = parsed_dob
                teacher.graduation_year = parsed_graduation_year
                teacher.experience = parsed_experience

                if uploaded_image:
                    teacher.profile_image = uploaded_image

                # Validate model fields, choices, URLs, and model.clean().
                # This also checks model-level uniqueness constraints.
                teacher.full_clean()

                # Calculate completion from the same fields used by My Profile.
                required_profile_fields = [
                    teacher.date_of_birth,
                    teacher.gender,
                    teacher.qualification,
                    teacher.specialization,
                    teacher.bio,
                    teacher.profile_image,
                ]

                teacher.profile_completed = all(
                    bool(value)
                    for value in required_profile_fields
                )

                teacher.save()

                messages.success(
                    request,
                    "Your profile has been updated successfully.",
                )

                return redirect("teacher_my_profile")

            except ValidationError as exc:
                # Keep model validation errors visible to the teacher.
                if hasattr(exc, "message_dict"):
                    for field_name, field_errors in exc.message_dict.items():
                        if field_name in editable_fields or field_name == "profile_image":
                            errors[field_name] = " ".join(
                                str(error) for error in field_errors
                            )
                        else:
                            errors.setdefault("general", " ".join(
                                str(error) for error in field_errors
                            ))
                else:
                    errors["general"] = " ".join(
                        str(error) for error in exc.messages
                    )

            except Exception:
                # Avoid exposing internal server or Cloudinary details.
                errors["general"] = (
                    "We could not save your profile right now. "
                    "Please check your information and try again."
                )

        # Show custom error messages through Django messages.
        for error in errors.values():
            messages.error(request, error)

    # --------------------------------------------------
    # 6. PROFILE COMPLETION
    # --------------------------------------------------

    completion_fields = [
        teacher.date_of_birth,
        teacher.gender,
        teacher.qualification,
        teacher.specialization,
        teacher.bio,
        teacher.profile_image,
    ]

    completed_count = sum(
        bool(value) for value in completion_fields
    )

    profile_completion = round(
        completed_count / len(completion_fields) * 100
    )

    # --------------------------------------------------
    # 7. RENDER EDIT PROFILE
    # --------------------------------------------------

    context = {
        "teacher": teacher,
        "errors": errors,
        "form_values": form_values,
        "profile_completion": profile_completion,
        "gender_choices": Teacher._meta.get_field(
            "gender"
        ).choices,
        "relationship_choices": Teacher._meta.get_field(
            "emergency_contact_relationship"
        ).choices,
    }

    response = render(
        request,
        "teachers/profile/edit_profile.html",
        context,
    )

    response["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response

# ============================================================
# MY COLLEAGUES
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_colleagues_view(request):
    # --------------------------------------------------------
    # 1. VALIDATE THE CURRENT TEACHER
    # --------------------------------------------------------
    try:
        teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        messages.error(request, "Access denied.")
        return redirect("teacher_login")

    if teacher.is_blocked:
        logout(request)
        messages.error(
            request,
            "Your teacher account has been blocked.",
        )
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    # --------------------------------------------------------
    # 2. ELIGIBLE COLLEAGUES
    # --------------------------------------------------------
    colleagues = Teacher.objects.filter(
        is_first_login=False,
        profile_completed=True,
        is_blocked=False,
    ).exclude(
        pk=teacher.pk,
    )

    # --------------------------------------------------------
    # 3. SEARCH BY FULL NAME
    # --------------------------------------------------------
    search = request.GET.get("q", "").strip()

    if search:
        colleagues = colleagues.filter(
            full_name__icontains=search,
        )

    # --------------------------------------------------------
    # 4. SORTING
    # --------------------------------------------------------
    sort = request.GET.get("sort", "name_asc")

    if sort == "name_desc":
        colleagues = colleagues.order_by(
            "-full_name",
            "pk",
        )
    else:
        sort = "name_asc"
        colleagues = colleagues.order_by(
            "full_name",
            "pk",
        )

    # --------------------------------------------------------
    # 5. COUNT MATCHING RESULTS BEFORE PAGINATION
    # --------------------------------------------------------
    colleague_count = colleagues.count()

    # --------------------------------------------------------
    # 6. PAGINATION — 20 COLLEAGUES PER PAGE
    # get_page() handles invalid and out-of-range page values.
    # --------------------------------------------------------
    paginator = Paginator(colleagues, 20)
    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    # Only the current page's colleagues reach the template.
    page_colleagues = page_obj.object_list

    # --------------------------------------------------------
    # 7. RENDER DIRECTORY
    # Preserve search, sort and pagination context.
    # --------------------------------------------------------
    context = {
        "teacher": teacher,
        "colleagues": page_colleagues,
        "search": search,
        "sort": sort,
        "colleague_count": colleague_count,
        "page_obj": page_obj,
        "paginator": paginator,
    }

    response = render(
        request,
        "teachers/colleagues/colleagues.html",
        context,
    )

    response["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response


# ============================================================
# COLLEAGUE PROFESSIONAL PROFILE
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_colleague_detail_view(request, teacher_id):
    # --------------------------------------------------------
    # 1. VALIDATE THE CURRENT TEACHER
    # --------------------------------------------------------
    try:
        current_teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        messages.error(request, "Access denied.")
        return redirect("teacher_login")

    if current_teacher.is_blocked:
        logout(request)
        messages.error(
            request,
            "Your teacher account has been blocked.",
        )
        return redirect("teacher_login")

    if current_teacher.is_first_login:
        return redirect("teacher_change_password")

    # --------------------------------------------------------
    # 2. FETCH AN ELIGIBLE COLLEAGUE
    # --------------------------------------------------------
    colleague = get_object_or_404(
        Teacher.objects.filter(
            is_blocked=False,
            is_first_login=False,
            profile_completed=True,
        ),
        pk=teacher_id,
    )

    # A teacher must use their own profile page.
    if colleague.pk == current_teacher.pk:
        return redirect("teacher_my_profile")

    # --------------------------------------------------------
    # 3. GET ACTIVE BATCH ASSIGNMENTS
    # --------------------------------------------------------
    batch_assignments_qs = (
        TeacherBatch.objects.filter(
            teacher=colleague,
            is_active=True,
        )
        .select_related("batch")
        .order_by("batch__batch_name")
    )

    batch_assignments_list = list(
        batch_assignments_qs
    )

    # --------------------------------------------------------
    # 4. GET ACTIVE SUBJECT ASSIGNMENTS
    # --------------------------------------------------------
    subject_assignments = (
        TeacherSubject.objects.filter(
            teacher=colleague,
            is_active=True,
        )
        .select_related("batch", "subject")
        .order_by(
            "batch__batch_name",
            "subject__subject_name",
        )
    )

    # --------------------------------------------------------
    # 5. GROUP SUBJECTS BY BATCH ID
    # --------------------------------------------------------
    subjects_by_batch = {}

    for assignment in subject_assignments:
        batch_id = assignment.batch_id

        if batch_id not in subjects_by_batch:
            subjects_by_batch[batch_id] = []

        subjects_by_batch[batch_id].append(
            assignment.subject
        )

    # --------------------------------------------------------
    # 6. BUILD BATCH-WISE TEMPLATE DATA
    # Keep batches visible even when they have no subjects.
    # --------------------------------------------------------
    batch_assignments = []

    for batch_assignment in batch_assignments_list:
        batch = batch_assignment.batch

        batch_assignments.append({
            "batch": batch,
            "subjects": subjects_by_batch.get(
                batch.pk,
                [],
            ),
        })

    # --------------------------------------------------------
    # 7. RENDER THE COLLEAGUE PROFILE
    # --------------------------------------------------------
    context = {
        "teacher": current_teacher,
        "current_teacher": current_teacher,
        "colleague": colleague,
        "batch_assignments": batch_assignments,
    }

    response = render(
        request,
        "teachers/colleagues/colleague_detail.html",
        context,
    )

    response["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response


# ============================================================
# TEACHER HELP VIDEOS
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def teacher_help_videos_view(request):
    """Display published help videos available to teachers."""

    try:
        teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        messages.error(request, "Access denied.")
        return redirect("teacher_login")

    if teacher.is_blocked:
        logout(request)
        messages.error(
            request,
            "Your teacher account has been blocked.",
        )
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    from django.db.models import Q

    videos = FAQVideo.objects.filter(
        status="published",
        audience__in=("teachers", "both"),
    )

    # Search by video title or description.
    search = request.GET.get("q", "").strip()

    if search:
        videos = videos.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
        )

    # Filter by a valid video category.
    selected_category = request.GET.get(
        "category", ""
    ).strip()

    valid_categories = {
        value
        for value, label in FAQVideo.CATEGORY_CHOICES
    }

    if selected_category in valid_categories:
        videos = videos.filter(
            category=selected_category
        )
    else:
        selected_category = ""

    videos = videos.order_by(
        "display_order",
        "-created_at",
        "-pk",
    )

    # Nine cards per page.
    paginator = Paginator(videos, 9)
    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    response = render(
        request,
        "teachers/help_videos.html",
        {
            "teacher": teacher,
            "videos": page_obj.object_list,
            "page_obj": page_obj,
            "search": search,
            "selected_category": selected_category,
            "video_categories": FAQVideo.CATEGORY_CHOICES,
            "result_count": paginator.count,
        },
    )

    response["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response

@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_analytics_view(request):
    from datetime import date, timedelta
    from django.utils.dateparse import parse_date
    from django.db.models import Count
    from admins.models import Teacher, TeacherBatch, TeacherSubject
    from courses.models import CourseChapter, ChapterVideo, ChapterPDF, ChapterQuiz
    from students.models import QuizAttempt
    from orders.models import StudentBatchPurchase

    if not hasattr(request.user, "teacher_profile"):
        logout(request)
        messages.error(request, "Teacher profile was not found.")
        return redirect("teacher_login")

    teacher = request.user.teacher_profile

    if teacher.is_blocked:
        logout(request)
        messages.error(request, "Your teacher account is currently blocked.")
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    # Only active batch and subject assignments are eligible for analytics.
    batch_ids = list(
        TeacherBatch.objects.filter(
            teacher=teacher, is_active=True
        ).values_list("batch_id", flat=True).distinct()
    )
    subject_assignments = TeacherSubject.objects.filter(
        teacher=teacher, is_active=True, batch_id__in=batch_ids
    ).select_related("batch", "subject")

    assigned_subject_ids = list(
        subject_assignments.values_list("subject_id", flat=True).distinct()
    )

    batches = list(
        __import__("admins.models", fromlist=["Batch"]).Batch.objects.filter(
            id__in=batch_ids
        ).order_by("batch_name")
    )

    selected_batch_id = request.GET.get("batch", "").strip()
    selected_subject_id = request.GET.get("subject", "").strip()
    start_raw = request.GET.get("start", "").strip()
    end_raw = request.GET.get("end", "").strip()

    selected_batch = None
    if selected_batch_id.isdigit() and int(selected_batch_id) in batch_ids:
        selected_batch = next(
            (batch for batch in batches if batch.id == int(selected_batch_id)),
            None,
        )
    else:
        selected_batch_id = ""

    available_subject_assignments = subject_assignments
    if selected_batch:
        available_subject_assignments = available_subject_assignments.filter(
            batch_id=selected_batch.id
        )

    available_subjects = list(
        {row.subject_id: row.subject for row in available_subject_assignments}.values()
    )
    available_subjects.sort(key=lambda item: item.subject_name.lower())

    selected_subject = None
    available_subject_ids = [item.id for item in available_subjects]
    if selected_subject_id.isdigit() and int(selected_subject_id) in available_subject_ids:
        selected_subject = next(
            (item for item in available_subjects if item.id == int(selected_subject_id)),
            None,
        )
    else:
        selected_subject_id = ""

    filtered_batch_ids = [selected_batch.id] if selected_batch else batch_ids
    filtered_subject_ids = (
        [selected_subject.id] if selected_subject else
        list(
            subject_assignments.filter(batch_id__in=filtered_batch_ids)
            .values_list("subject_id", flat=True).distinct()
        )
    )

    # Optional date range. Dates are validated and used only for dated quiz attempts.
    start_date = parse_date(start_raw) if start_raw else None
    end_date = parse_date(end_raw) if end_raw else None
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date
        start_raw, end_raw = end_raw, start_raw

    chapters_qs = CourseChapter.objects.filter(
        batch_id__in=filtered_batch_ids,
        subject_id__in=filtered_subject_ids,
    )
    videos_qs = ChapterVideo.objects.filter(
        chapter__batch_id__in=filtered_batch_ids,
        chapter__subject_id__in=filtered_subject_ids,
    )
    pdfs_qs = ChapterPDF.objects.filter(
        chapter__batch_id__in=filtered_batch_ids,
        chapter__subject_id__in=filtered_subject_ids,
    )
    quizzes_qs = ChapterQuiz.objects.filter(
        chapter__batch_id__in=filtered_batch_ids,
        chapter__subject_id__in=filtered_subject_ids,
    )

    active_purchases = StudentBatchPurchase.objects.filter(
        batch_id__in=filtered_batch_ids,
        status="active",
    )
    overall_students = active_purchases.values("student_id").distinct().count()

    submitted_attempts = QuizAttempt.objects.filter(
        quiz__chapter__batch_id__in=filtered_batch_ids,
        quiz__chapter__subject_id__in=filtered_subject_ids,
        status="submitted",
    )
    if start_date:
        submitted_attempts = submitted_attempts.filter(
            submitted_at__date__gte=start_date
        )
    if end_date:
        submitted_attempts = submitted_attempts.filter(
            submitted_at__date__lte=end_date
        )

    score_rows = list(
        submitted_attempts.filter(maximum_marks__gt=0)
        .values_list("score", "maximum_marks")
    )
    average_score = (
        round(sum((score / maximum) * 100 for score, maximum in score_rows) / len(score_rows), 1)
        if score_rows else None
    )

    batch_rows = []
    student_chart = []
    content_chart = []
    quiz_chart = []
    for batch in batches:
        if batch.id not in filtered_batch_ids:
            continue
        batch_subject_ids = list(
            subject_assignments.filter(batch_id=batch.id)
            .values_list("subject_id", flat=True).distinct()
        )
        if selected_subject:
            batch_subject_ids = [sid for sid in batch_subject_ids if sid == selected_subject.id]
        if not batch_subject_ids:
            # Show assigned batch even if it currently has no active subject assignment.
            batch_subject_ids = []

        batch_chapters = CourseChapter.objects.filter(
            batch_id=batch.id, subject_id__in=batch_subject_ids
        )
        chapter_ids = batch_chapters.values_list("id", flat=True)
        batch_videos = ChapterVideo.objects.filter(chapter_id__in=chapter_ids).count()
        batch_pdfs = ChapterPDF.objects.filter(chapter_id__in=chapter_ids).count()
        batch_quizzes = ChapterQuiz.objects.filter(chapter_id__in=chapter_ids).count()
        batch_students = StudentBatchPurchase.objects.filter(
            batch_id=batch.id, status="active"
        ).values("student_id").distinct().count()

        batch_attempts = QuizAttempt.objects.filter(
            quiz__chapter__batch_id=batch.id,
            quiz__chapter__subject_id__in=batch_subject_ids,
            status="submitted",
        )
        if start_date:
            batch_attempts = batch_attempts.filter(submitted_at__date__gte=start_date)
        if end_date:
            batch_attempts = batch_attempts.filter(submitted_at__date__lte=end_date)
        batch_scores = list(
            batch_attempts.filter(maximum_marks__gt=0).values_list("score", "maximum_marks")
        )
        batch_average = (
            round(sum((score / maximum) * 100 for score, maximum in batch_scores) / len(batch_scores), 1)
            if batch_scores else None
        )

        batch_rows.append({
            "batch": batch,
            "subject_count": len(batch_subject_ids),
            "student_count": batch_students,
            "chapter_count": batch_chapters.count(),
            "video_count": batch_videos,
            "pdf_count": batch_pdfs,
            "quiz_count": batch_quizzes,
            "quiz_attempt_count": batch_attempts.count(),
            "quiz_average": batch_average,
        })
        student_chart.append({"label": batch.batch_name, "value": batch_students})

    content_chart = [
        {"label": "Chapters", "value": chapters_qs.count()},
        {"label": "Videos", "value": videos_qs.count()},
        {"label": "PDFs", "value": pdfs_qs.count()},
        {"label": "Quizzes", "value": quizzes_qs.count()},
    ]
    quiz_chart = [
        {"label": row["batch"].batch_name, "value": row["quiz_average"] or 0}
        for row in batch_rows
    ]

    context = {
        "teacher": teacher,
        "batches": batches,
        "available_subjects": available_subjects,
        "selected_batch_id": selected_batch_id,
        "selected_subject_id": selected_subject_id,
        "start_date": start_raw,
        "end_date": end_raw,
        "assigned_batch_count": len(batch_ids),
        "assigned_subject_count": len(assigned_subject_ids),
        "student_count": overall_students,
        "chapter_count": chapters_qs.count(),
        "video_count": videos_qs.count(),
        "pdf_count": pdfs_qs.count(),
        "quiz_count": quizzes_qs.count(),
        "submitted_attempt_count": submitted_attempts.count(),
        "average_score": average_score,
        "batch_rows": batch_rows,
        "student_chart_json": __import__("json").dumps(student_chart),
        "content_chart_json": __import__("json").dumps(content_chart),
        "quiz_chart_json": __import__("json").dumps(quiz_chart),
    }
    return render(request, "teachers/analytics/analytics.html", context)