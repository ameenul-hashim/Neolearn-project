from django.shortcuts import render,redirect
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from .models import EmailOTP
import random
import re


# SIGNUP VIEW

def signup_view(request):

    if request.method == 'POST':

        username=request.POST.get('username')
        email=request.POST.get('email')
        password=request.POST.get('password')
        confirm_password=request.POST.get('confirm_password')

        if not username or not email or not password or not confirm_password:

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'All fields are required'
                }
            )

        if User.objects.filter(username=username).exists():

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Username already exists'
                }
            )

        try:

            validate_email(email)

        except ValidationError:

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Invalid email format'
                }
            )

        if User.objects.filter(email=email).exists():

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Email already exists'
                }
            )

        if password != confirm_password:

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Passwords do not match'
                }
            )

        if len(password) < 8:

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least 8 characters'
                }
            )

        if not re.search(r'[A-Z]',password):

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least one uppercase letter'
                }
            )

        if not re.search(r'[a-z]',password):

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least one lowercase letter'
                }
            )

        if not re.search(r'[0-9]',password):

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least one number'
                }
            )

        if not re.search(r'[@$!%*?&]',password):

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least one special character'
                }
            )

        request.session['temp_user']={

            'username':username,
            'email':email,
            'password':password
        }

        otp=str(random.randint(100000,999999))

        request.session['otp']=otp
        request.session['email']=email

        request.session['otp_success']='OTP sent successfully to your email'

        send_mail(

            'NeoLearn OTP Verification',

            f'Your OTP is {otp}',

            None,

            [email],

            fail_silently=False
        )

        return redirect('verify_otp')

    return render(
        request,
        'accounts/signup.html'
    )


# VERIFY OTP VIEW

def verify_otp_view(request):

    temp_user=request.session.get('temp_user')
    session_otp=request.session.get('otp')

    success=request.session.pop(
        'otp_success',
        None
    )

    if not temp_user or not session_otp:

        return redirect('signup')

    if request.method == 'POST':

        entered_otp=request.POST.get('otp')

        if not entered_otp:

            return render(
                request,
                'accounts/verify_otp.html',
                {
                    'error':'Please enter OTP',
                    'success':success
                }
            )

        if str(entered_otp).strip() != str(session_otp).strip():

            return render(
                request,
                'accounts/verify_otp.html',
                {
                    'error':'Invalid verification code',
                    'success':success
                }
            )

        user=User.objects.create_user(

            username=temp_user['username'],
            email=temp_user['email'],
            password=temp_user['password']
        )

        EmailOTP.objects.create(

            user=user,
            otp=session_otp,
            is_used=True
        )

        request.session.pop('temp_user',None)
        request.session.pop('otp',None)
        request.session.pop('otp_success',None)

        return redirect('verification_success')

    return render(
        request,
        'accounts/verify_otp.html',
        {
            'success':success
        }
    )


# VERIFICATION SUCCESS VIEW

def verification_success_view(request):

    google_signup=request.session.get(
        'google_signup'
    )

    # GOOGLE SIGNUP USERS

    if google_signup:

        logout(request)

        response=render(
            request,
            'accounts/verification_success.html'
        )

        response.delete_cookie('sessionid')

        response.delete_cookie('csrftoken')

        return response

    return render(
        request,
        'accounts/verification_success.html'
    )


# RESEND OTP VIEW

def resend_otp_view(request):

    email=request.session.get('email')

    if not email:

        return redirect('signup')

    otp=str(random.randint(100000,999999))

    request.session['otp']=otp

    request.session['otp_success']='New OTP sent successfully'

    send_mail(

        'NeoLearn OTP Verification',

        f'Your new OTP is {otp}',

        None,

        [email],

        fail_silently=False
    )

    return redirect('verify_otp')


# SIGNIN VIEW

@never_cache
def signin_view(request):

    success=request.session.pop(
        'password_success',
        None
    )

    if request.method == 'POST':

        username=request.POST.get('username')
        password=request.POST.get('password')

        if not username or not password:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Both username and password are required',
                    'success':success
                }
            )

        user=authenticate(

            request,

            username=username,

            password=password
        )

        if user is None:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Invalid username or password',
                    'success':success
                }
            )

        login(request,user)

        request.session.set_expiry(3600)

        return redirect('dashboard')

    return render(
        request,
        'accounts/signin.html',
        {
            'success':success
        }
    )


# LOGOUT VIEW

def logout_view(request):

    logout(request)

    request.session.flush()

    response=redirect('/signin/')

    response.delete_cookie('sessionid')

    response.delete_cookie('csrftoken')

    return response


# FORGOT PASSWORD VIEW

def forgot_password_view(request):

    success=request.session.pop(
        'forgot_success',
        None
    )

    if request.method == 'POST':

        username=request.POST.get('username')
        email=request.POST.get('email')

        if not username or not email:

            return render(
                request,
                'accounts/forgot_password.html',
                {
                    'error':'Username and email are required',
                    'success':success
                }
            )

        try:

            validate_email(email)

        except ValidationError:

            return render(
                request,
                'accounts/forgot_password.html',
                {
                    'error':'Invalid email format',
                    'success':success
                }
            )

        try:

            user=User.objects.get(
                username=username
            )

        except User.DoesNotExist:

            return render(
                request,
                'accounts/forgot_password.html',
                {
                    'error':'Username not found',
                    'success':success
                }
            )

        if user.email != email:

            return render(
                request,
                'accounts/forgot_password.html',
                {
                    'error':'Email does not match this username',
                    'success':success
                }
            )

        otp=str(random.randint(100000,999999))

        request.session['forgot_password_otp']=otp
        request.session['forgot_password_user_id']=user.id
        request.session['forgot_password_email']=email

        send_mail(

            'NeoLearn Password Reset OTP',

            f'Your password reset OTP is {otp}',

            None,

            [email],

            fail_silently=False
        )

        request.session['forgot_success']='Verification OTP sent successfully'

        return redirect('forgot_password_verify')

    return render(
        request,
        'accounts/forgot_password.html',
        {
            'success':success
        }
    )


# FORGOT PASSWORD VERIFY VIEW

def forgot_password_verify_view(request):

    session_otp=request.session.get('forgot_password_otp')
    email=request.session.get('forgot_password_email')
    user_id=request.session.get('forgot_password_user_id')

    success=request.session.pop(
        'forgot_success',
        None
    )

    if not session_otp or not email or not user_id:

        return redirect('forgot_password')

    if request.method == 'POST':

        entered_otp=request.POST.get('otp')

        if not entered_otp:

            return render(
                request,
                'accounts/forgot_password_verify.html',
                {
                    'error':'Please enter verification code',
                    'success':success
                }
            )

        if str(entered_otp).strip() != str(session_otp).strip():

            return render(
                request,
                'accounts/forgot_password_verify.html',
                {
                    'error':'Invalid verification code',
                    'success':success
                }
            )

        return redirect('reset_password')

    return render(
        request,
        'accounts/forgot_password_verify.html',
        {
            'success':success
        }
    )


# RESEND RESET OTP VIEW

def resend_reset_otp_view(request):

    email=request.session.get('forgot_password_email')

    if not email:

        return redirect('forgot_password')

    otp=str(random.randint(100000,999999))

    request.session['forgot_password_otp']=otp

    request.session['forgot_success']='New OTP sent successfully'

    send_mail(

        'NeoLearn Password Reset OTP',

        f'Your new OTP is {otp}',

        None,

        [email],

        fail_silently=False
    )

    return redirect('forgot_password_verify')


# RESET PASSWORD VIEW

def reset_password_view(request):

    user_id=request.session.get(
        'forgot_password_user_id'
    )

    if not user_id:

        return redirect('forgot_password')

    try:

        user=User.objects.get(id=user_id)

    except User.DoesNotExist:

        return redirect('forgot_password')

    if request.method == 'POST':

        password=request.POST.get('password')

        confirm_password=request.POST.get(
            'confirm_password'
        )

        if not password or not confirm_password:

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Please enter your new password'
                }
            )

        if password != confirm_password:

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Passwords do not match'
                }
            )

        if len(password) < 8:

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least 8 characters'
                }
            )

        if not re.search(r'[A-Z]',password):

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least one uppercase letter'
                }
            )

        if not re.search(r'[a-z]',password):

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least one lowercase letter'
                }
            )

        if not re.search(r'[0-9]',password):

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least one number'
                }
            )

        if not re.search(r'[@$!%*?&]',password):

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least one special character'
                }
            )

        user.set_password(password)

        user.save()

        request.session.pop(
            'forgot_password_otp',
            None
        )

        request.session.pop(
            'forgot_password_user_id',
            None
        )

        request.session.pop(
            'forgot_password_email',
            None
        )

        request.session['password_success']='Password updated successfully'

        return redirect('signin')

    return render(
        request,
        'accounts/reset_password.html'
    )


# DASHBOARD VIEW

@login_required(login_url='/signin/')
@never_cache
def dashboard_view(request):

    google_signup=request.session.get(
        'google_signup'
    )

    # BLOCK NEW GOOGLE SIGNUP USERS

    if google_signup:

        logout(request)

        request.session.flush()

        return redirect('/signin/')

    return render(
        request,
        'accounts/dashboard.html'
    )