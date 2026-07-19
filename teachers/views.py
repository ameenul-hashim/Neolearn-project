from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)
from django.contrib import messages
from django.contrib.auth import (authenticate,login,logout,update_session_auth_hash,)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.cache import cache_control
import re
from admins.models import (
    Teacher,
    TeacherBatch,
    TeacherSubject,
    Batch,
)


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_login_view(request):

    if request.user.is_authenticated:
        if hasattr(request.user, "teacher_profile"):
            teacher = request.user.teacher_profile
            if teacher.is_first_login:
                return redirect("teacher_change_password")
            return redirect("teacher_dashboard")

    if request.method == "POST":
        email = request.POST.get("email","").strip().lower()
        password = request.POST.get("password","")

        if not email or not password:
            messages.error(request,"All fields are required.")
            return redirect("teacher_login")

        try:
            existing_user = User.objects.get(username=email)

        except User.DoesNotExist:
            messages.error(request,"Teacher account not found.")
            return redirect("teacher_login")

        user = authenticate(request,username=existing_user.username,password=password,)

        if user is None:
            messages.error(request,"Incorrect password.")
            return redirect("teacher_login")

        try:
            teacher = user.teacher_profile

        except Teacher.DoesNotExist:
            messages.error(request,"Teacher profile not found.")
            return redirect("teacher_login")

        if teacher.is_blocked:
            messages.error(request,"Your teacher account has been blocked.")
            return redirect("teacher_login")

        login(request,user,)
        messages.success(request,"Teacher logged in successfully.")


        if teacher.is_first_login:
            return redirect("teacher_change_password")

        return redirect("teacher_dashboard")

    return render(request,"teachers/auth/teacher_login.html",)
    
@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_change_password_view(request):

    if not hasattr(request.user, "teacher_profile"):
        messages.error(request,"Access denied.")
        return redirect("teacher_login")

    teacher = request.user.teacher_profile
    user = request.user



    if not teacher.is_first_login:
        return redirect("teacher_dashboard")



    if request.method == "POST":
        password = request.POST.get("password","")
        confirm_password = request.POST.get("confirm_password","")


        if  not password or not confirm_password:
            messages.error(request,"All fields are required.")
            return redirect("teacher_change_password")


        if len(password) < 8:
            messages.error(request,"Password must contain at least 8 characters.")
            return redirect("teacher_change_password")

        if not re.search(r"[A-Z]", password):
            messages.error(request,"Password must contain at least one uppercase letter.")
            return redirect("teacher_change_password")

        if not re.search(r"[a-z]", password):
            messages.error(request,"Password must contain at least one lowercase letter.")
            return redirect("teacher_change_password")

        if not re.search(r"[0-9]", password):
            messages.error(request,"Password must contain at least one number.")
            return redirect("teacher_change_password")

        if not re.search(r"[!@#$%^&*()_+=\-[\]{};:'\"\\|,.<>/?]",password):
            messages.error(request,"Password must contain at least one special character.")
            return redirect("teacher_change_password")

        if password != confirm_password:
            messages.error(request,"Passwords do not match.")
            return redirect("teacher_change_password")

        user.set_password(password)
        user.save()
        teacher.is_first_login = False
        teacher.save()
        update_session_auth_hash(request,user)

        messages.success(request,"Security setup completed successfully.")
        return redirect("teacher_dashboard")
    
    return render(request,"teachers/auth/change_password.html",)
    

@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_dashboard_view(request):

    

    if not hasattr(request.user, "teacher_profile"):
        messages.error(request,"Access denied.")
        return redirect("teacher_login")

    teacher = request.user.teacher_profile
    if teacher.is_first_login:
        return redirect("teacher_change_password")

    response = render(request,"teachers/dashboard/dashboard.html",{"teacher": teacher,})
    response["Cache-Control"] = (
        "no-cache, no-store, must-revalidate")
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@login_required(login_url="teacher_login")
def teacher_logout_view(request):
    logout(request)
    request.session.flush()
    response = redirect("teacher_login")
    response.delete_cookie("sessionid")
    response.delete_cookie("csrftoken")
    messages.success(request,"Logged out successfully.")
    return response

@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_batches_view(request):

    if not hasattr(request.user, "teacher_profile"):
        messages.error(request, "Access denied.")
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

        subject_count = TeacherSubject.objects.filter(
            teacher=teacher,
            batch=batch,
            is_active=True,
        ).count()

        teacher_count = TeacherBatch.objects.filter(
            batch=batch,
            is_active=True,
        ).count()

        batch_cards.append({
            "assignment": assignment,
            "batch": batch,
            "subject_count": subject_count,
            "teacher_count": teacher_count,
        })

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
    
@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_subjects_view(request, batch_id):

    if not hasattr(request.user, "teacher_profile"):
        messages.error(request, "Access denied.")
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
        .select_related("subject")
        .order_by("subject__subject_name")
    )

    context = {

        "teacher": teacher,

        "batch": batch,

        "assigned_subjects": assigned_subjects,

    }

    return render(
        request,
        "teachers/subjects/subjects.html",
        context,
    )
    
@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_subjects_view(request, batch_id):

    if not hasattr(request.user, "teacher_profile"):
        messages.error(request, "Access denied.")
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
        .order_by("subject__subject_name")
    )

    context = {

        "teacher": teacher,

        "batch": batch,

        "assigned_subjects": assigned_subjects,

        "subject_count": assigned_subjects.count(),

    }

    return render(
        request,
        "teachers/batches/subjects.html",
        context,
    )