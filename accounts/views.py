from django.shortcuts import render,redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from .models import User,EmailOTP
import random
import re


def signup_view(request):

    if request.method=='POST':

        username=request.POST.get('username')

        email=request.POST.get('email')

        password=request.POST.get('password')

        confirm_password=request.POST.get('confirm_password')

        # EMPTY FIELD CHECK

        if not username or not email or not password or not confirm_password:

            messages.error(request,"All fields are required")

            return redirect('signup')

        # REMOVE OLD UNVERIFIED USER

        old_user=User.objects.filter(
            email=email,
            is_verified=False
        ).first()

        if old_user:

            EmailOTP.objects.filter(
                user=old_user
            ).delete()

            old_user.delete()

        # USERNAME CHECK

        if User.objects.filter(username=username).exists():

            messages.error(request,"Username already exists")

            return redirect('signup')

        # EMAIL VALIDATION

        try:

            validate_email(email)

        except ValidationError:

            messages.error(request,"Invalid email format")

            return redirect('signup')

        # EMAIL CHECK

        if User.objects.filter(
            email=email,
            is_verified=True
        ).exists():

            messages.error(request,"Email already exists")

            return redirect('signup')

        # PASSWORD VALIDATION

        if len(password)<8:

            messages.error(
                request,
                "Password must be at least 8 characters"
            )

            return redirect('signup')

        if not re.search(r'[A-Z]',password):

            messages.error(
                request,
                "Password must contain at least one uppercase letter"
            )

            return redirect('signup')

        if not re.search(r'[a-z]',password):

            messages.error(
                request,
                "Password must contain at least one lowercase letter"
            )

            return redirect('signup')

        if not re.search(r'[!@#$%^&*(),.?\":{}|<>]',password):

            messages.error(
                request,
                "Password must contain at least one special character"
            )

            return redirect('signup')

        # PASSWORD MATCH

        if password!=confirm_password:

            messages.error(request,"Passwords do not match")

            return redirect('signup')

        # HASH PASSWORD

        hashed_password=make_password(password)

        # CREATE USER

        user=User.objects.create(

            username=username,

            email=email,

            password=hashed_password,

            role='student',

            is_verified=False,

            is_blocked=False

        )

        # GENERATE OTP

        otp=random.randint(100000,999999)

        # SAVE OTP

        EmailOTP.objects.create(

            user=user,

            otp=str(otp),

            is_used=False

        )

        # SEND EMAIL

        send_mail(

            'NeoLearn OTP Verification',

            f'Your OTP is {otp}',

            None,

            [email],

            fail_silently=False

        )

        # SAVE SESSION

        request.session['email']=email

        messages.success(
            request,
            "OTP sent to your email"
        )

        return redirect('verify_otp')

    return render(
        request,
        'accounts/signup.html'
    )


def verify_otp_view(request):

    email=request.session.get('email')

    if not email:

        return redirect('signup')

    try:

        user=User.objects.get(email=email)

    except User.DoesNotExist:

        messages.error(request,"User not found")

        return redirect('signup')

    if request.method=='POST':

        entered_otp=request.POST.get('otp')

        otp_obj=EmailOTP.objects.filter(

            user=user,

            otp=entered_otp,

            is_used=False

        ).last()

        if otp_obj:

            otp_obj.is_used=True

            otp_obj.save()

            user.is_verified=True

            user.save()

            return redirect('verification_success')

        else:

            messages.error(request,"Invalid OTP")

            return redirect('verify_otp')

    return render(
        request,
        'accounts/verify_otp.html'
    )


def verification_success_view(request):

    return render(
        request,
        'accounts/verification_success.html'
    )


def resend_otp_view(request):

    email=request.session.get('email')

    if not email:

        messages.error(request,"Session expired")

        return redirect('signup')

    try:

        user=User.objects.get(email=email)

    except User.DoesNotExist:

        messages.error(request,"User not found")

        return redirect('signup')

    # DISABLE OLD OTP

    EmailOTP.objects.filter(

        user=user,

        is_used=False

    ).update(is_used=True)

    # NEW OTP

    new_otp=random.randint(100000,999999)

    # SAVE NEW OTP

    EmailOTP.objects.create(

        user=user,

        otp=str(new_otp),

        is_used=False

    )

    # SEND NEW OTP EMAIL

    send_mail(

        'NeoLearn OTP Verification',

        f'Your new OTP is {new_otp}',

        None,

        [email],

        fail_silently=False

    )

    messages.success(
        request,
        "New OTP sent successfully"
    )

    return redirect('verify_otp')