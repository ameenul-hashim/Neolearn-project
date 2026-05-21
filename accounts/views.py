from django.shortcuts import render,redirect
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password,check_password
from .models import User,EmailOTP
import random
import re



# SIGNUP VIEW

def signup_view(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # EMPTY CHECK

        if not username or not email or not password or not confirm_password:

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'All fields are required'
                }
            )

        # USERNAME EXISTS

        if User.objects.filter(username=username).exists():

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Username already exists'
                }
            )

        # EMAIL VALIDATION

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

        # EMAIL EXISTS

        if User.objects.filter(email=email).exists():

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Email already exists'
                }
            )

        # PASSWORD MATCH

        if password != confirm_password:

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Passwords do not match'
                }
            )

        # PASSWORD LENGTH

        if len(password) < 8:

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least 8 characters'
                }
            )

        # UPPERCASE CHECK

        if not re.search(r'[A-Z]', password):

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least one uppercase letter'
                }
            )

        # LOWERCASE CHECK

        if not re.search(r'[a-z]', password):

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least one lowercase letter'
                }
            )

        # NUMBER CHECK

        if not re.search(r'[0-9]', password):

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least one number'
                }
            )

        # SPECIAL CHARACTER CHECK

        if not re.search(r'[@$!%*?&]', password):

            return render(
                request,
                'accounts/signup.html',
                {
                    'error':'Password must contain at least one special character'
                }
            )

        # HASH PASSWORD

        hashed_password = make_password(password)

        # STORE TEMP USER

        request.session['temp_user'] = {

            'username':username,
            'email':email,
            'password':hashed_password

        }

        # GENERATE OTP

        otp = str(random.randint(100000,999999))

        # STORE OTP

        request.session['otp'] = otp
        request.session['email'] = email

        # SUCCESS MESSAGE

        request.session['otp_success'] = (
            'OTP sent successfully to your email'
        )

        # SEND EMAIL

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

    temp_user = request.session.get('temp_user')

    session_otp = request.session.get('otp')

    success = request.session.pop(
        'otp_success',
        None
    )

    # BLOCK DIRECT ACCESS

    if not temp_user or not session_otp:

        return redirect('signup')

    # VERIFY OTP

    if request.method == 'POST':

        entered_otp = request.POST.get('otp')

        # EMPTY CHECK

        if not entered_otp:

            return render(
                request,
                'accounts/verify_otp.html',
                {
                    'error':'Please enter OTP',
                    'success':success
                }
            )

        # REMOVE SPACE

        entered_otp = str(entered_otp).strip()

        session_otp = str(session_otp).strip()

        # INVALID OTP

        if entered_otp != session_otp:

            return render(
                request,
                'accounts/verify_otp.html',
                {
                    'error':'Invalid verification code',
                    'success':success
                }
            )

        # CREATE USER

        user = User.objects.create(

            username=temp_user['username'],
            email=temp_user['email'],
            password=temp_user['password'],
            role='student',
            is_verified=True,
            is_blocked=False

        )

        # SAVE OTP HISTORY

        EmailOTP.objects.create(

            user=user,
            otp=session_otp,
            is_used=True

        )

        # CLEAR SESSION

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

    return render(
        request,
        'accounts/verification_success.html'
    )



# RESEND OTP VIEW

def resend_otp_view(request):

    email = request.session.get('email')

    if not email:

        return redirect('signup')

    # NEW OTP

    otp = str(random.randint(100000,999999))

    # UPDATE SESSION

    request.session['otp'] = otp

    # SUCCESS MESSAGE

    request.session['otp_success'] = (
        'New OTP sent successfully'
    )

    # SEND EMAIL

    send_mail(

        'NeoLearn OTP Verification',

        f'Your new OTP is {otp}',

        None,

        [email],

        fail_silently=False

    )

    return redirect('verify_otp')



# SIGNIN VIEW

def signin_view(request):

    success = request.session.pop(
        'password_success',
        None
    )

    if request.method == 'POST':

        username = request.POST.get('username')

        password = request.POST.get('password')

        # EMPTY CHECK

        if not username or not password:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Both username and password are required',
                    'success':success
                }
            )

        # USER CHECK

        try:

            user = User.objects.get(username=username)

        except User.DoesNotExist:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Username not found',
                    'success':success
                }
            )

        # VERIFIED CHECK

        if not user.is_verified:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Please verify your account first',
                    'success':success
                }
            )

        # BLOCK CHECK

        if user.is_blocked:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Your account has been blocked',
                    'success':success
                }
            )

        # PASSWORD CHECK

        if not check_password(password,user.password):

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Incorrect password',
                    'success':success
                }
            )

        # LOGIN SESSION

        request.session['user_id'] = user.id
        request.session['username'] = user.username
        request.session['email'] = user.email
        request.session['role'] = user.role
        request.session['is_logged_in'] = True

        request.session.set_expiry(3600)

        return render(
            request,
            'accounts/signin.html',
            {
                'success':'Login successful'
            }
        )

    return render(
        request,
        'accounts/signin.html',
        {
            'success':success
        }
    )



# LOGOUT VIEW

def logout_view(request):

    request.session.flush()

    return redirect('signin')



# FORGOT PASSWORD VIEW

def forgot_password_view(request):

    success = request.session.pop(
        'forgot_success',
        None
    )

    if request.method == 'POST':

        username = request.POST.get('username')

        email = request.POST.get('email')

        # EMPTY CHECK

        if not username or not email:

            return render(
                request,
                'accounts/forgot_password.html',
                {
                    'error':'Username and email are required',
                    'success':success
                }
            )

        # EMAIL VALIDATION

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

        # USER CHECK

        try:

            user = User.objects.get(username=username)

        except User.DoesNotExist:

            return render(
                request,
                'accounts/forgot_password.html',
                {
                    'error':'Username not found',
                    'success':success
                }
            )

        # EMAIL CHECK

        if user.email != email:

            return render(
                request,
                'accounts/forgot_password.html',
                {
                    'error':'Email does not match this username',
                    'success':success
                }
            )

        # BLOCK CHECK

        if user.is_blocked:

            return render(
                request,
                'accounts/forgot_password.html',
                {
                    'error':'Your account has been blocked',
                    'success':success
                }
            )

        # GENERATE OTP

        otp = str(random.randint(100000,999999))

        # STORE SESSION

        request.session['forgot_password_otp'] = otp
        request.session['forgot_password_user_id'] = user.id
        request.session['forgot_password_email'] = email

        # SEND EMAIL

        send_mail(

            'NeoLearn Password Reset OTP',

            f'Your password reset OTP is {otp}',

            None,

            [email],

            fail_silently=False

        )

        # SUCCESS MESSAGE

        request.session['forgot_success'] = (
            'Verification OTP sent successfully'
        )

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

    session_otp = request.session.get(
        'forgot_password_otp'
    )

    email = request.session.get(
        'forgot_password_email'
    )

    user_id = request.session.get(
        'forgot_password_user_id'
    )

    success = request.session.pop(
        'forgot_success',
        None
    )

    # BLOCK DIRECT ACCESS

    if not session_otp or not email or not user_id:

        return redirect('forgot_password')

    # VERIFY OTP

    if request.method == 'POST':

        entered_otp = request.POST.get('otp')

        # EMPTY CHECK

        if not entered_otp:

            return render(
                request,
                'accounts/forgot_password_verify.html',
                {
                    'error':'Please enter verification code',
                    'success':success
                }
            )

        # REMOVE SPACE

        entered_otp = str(entered_otp).strip()

        session_otp = str(session_otp).strip()

        # INVALID OTP

        if entered_otp != session_otp:

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

    email = request.session.get(
        'forgot_password_email'
    )

    if not email:

        return redirect('forgot_password')

    # NEW OTP

    otp = str(random.randint(100000,999999))

    # UPDATE SESSION

    request.session[
        'forgot_password_otp'
    ] = otp

    # SUCCESS MESSAGE

    request.session[
        'forgot_success'
    ] = (
        'New OTP sent successfully'
    )

    # SEND EMAIL

    send_mail(

        'NeoLearn Password Reset OTP',

        f'Your new OTP is {otp}',

        None,

        [email],

        fail_silently=False

    )

    return redirect(
        'forgot_password_verify'
    )



# RESET PASSWORD VIEW

def reset_password_view(request):

    user_id = request.session.get(
        'forgot_password_user_id'
    )

    # BLOCK DIRECT ACCESS

    if not user_id:

        return redirect('forgot_password')

    try:

        user = User.objects.get(
            id=user_id
        )

    except User.DoesNotExist:

        return redirect('forgot_password')

    # FORM SUBMIT

    if request.method == 'POST':

        password = request.POST.get(
            'password'
        )

        confirm_password = request.POST.get(
            'confirm_password'
        )

        # EMPTY CHECK

        if not password or not confirm_password:

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Please enter your new password'
                }
            )

        # PASSWORD MATCH

        if password != confirm_password:

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Passwords do not match'
                }
            )

        # PASSWORD LENGTH

        if len(password) < 8:

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least 8 characters'
                }
            )

        # UPPERCASE CHECK

        if not re.search(r'[A-Z]',password):

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least one uppercase letter'
                }
            )

        # LOWERCASE CHECK

        if not re.search(r'[a-z]',password):

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least one lowercase letter'
                }
            )

        # NUMBER CHECK

        if not re.search(r'[0-9]',password):

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least one number'
                }
            )

        # SPECIAL CHARACTER CHECK

        if not re.search(r'[@$!%*?&]',password):

            return render(
                request,
                'accounts/reset_password.html',
                {
                    'error':'Password must contain at least one special character'
                }
            )

        # HASH PASSWORD

        hashed_password = make_password(
            password
        )

        # UPDATE PASSWORD

        user.password = hashed_password

        user.save()

        # CLEAR SESSION

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

        # SUCCESS MESSAGE

        request.session['password_success'] = (
            'Password updated successfully'
        )

        return redirect('signin')

    return render(
        request,
        'accounts/reset_password.html'
    )