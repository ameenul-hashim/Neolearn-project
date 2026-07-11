from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.views.decorators.cache import cache_control
from admins.models import Teacher



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_login_view(request):
    
    if request.user.is_authenticated:
        if hasattr(request.user, "teacher_profile"):
            teacher = request.user.teacher_profile
            if teacher.is_first_login:
                return redirect("teacher_change_password")

            return redirect("teacher_dashboard")

    if request.method == "POST":
        email = request.POST.get("email").strip()
        password = request.POST.get("password")


        try:

            user = User.objects.get(username=email)

        except User.DoesNotExist:

            messages.error(request,"Teacher account not found")


            return redirect("teacher_login")


        if not user.check_password(password):
            messages.error(request,"Incorrect password")
            return redirect("teacher_login")

        try:

            teacher = user.teacher_profile

        except Teacher.DoesNotExist:
            messages.error(request,"Teacher profile not found")
            return redirect("teacher_login")


        if teacher.is_blocked:
            messages.error(request,"Your teacher account has been blocked")
            return redirect("teacher_login")

        login(request,user)

        if teacher.is_first_login:
            return redirect("teacher_change_password")

        return redirect("teacher_dashboard")

    return render(request,"teachers/auth/teacher_login.html")