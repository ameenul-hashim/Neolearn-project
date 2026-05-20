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
                    'error':'Password must contain at least one special character one upper and one lower atleast. '
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

        # REDIRECT VERIFY PAGE

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

        # EMPTY OTP

        if not entered_otp:

            return render(
                request,
                'accounts/verify_otp.html',
                {
                    'error':'Please enter OTP'
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
                    'error':'Invalid verification code'
                }
            )

        # CREATE VERIFIED USER

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

        # REDIRECT SUCCESS PAGE

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

    # SESSION CHECK

    if not email:

        return redirect('signup')

    # GENERATE NEW OTP

    new_otp = str(random.randint(100000,999999))

    # UPDATE SESSION OTP

    request.session['otp'] = new_otp

    # SUCCESS MESSAGE

    request.session['otp_success'] = (
        'New OTP sent successfully'
    )

    # SEND EMAIL

    send_mail(

        'NeoLearn OTP Verification',

        f'Your new OTP is {new_otp}',

        None,

        [email],

        fail_silently=False

    )

    # REDIRECT VERIFY PAGE

    return redirect('verify_otp')



# SIGNIN VIEW

def signin_view(request):

    if request.method == 'POST':

        email = request.POST.get('email')

        password = request.POST.get('password')

        # EMPTY CHECK

        if not email or not password:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Both email and password are required'
                }
            )

        # ACCOUNT CHECK

        try:

            user = User.objects.get(email=email)

        except User.DoesNotExist:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Account not found'
                }
            )

        # VERIFIED CHECK

        if not user.is_verified:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Please verify your account first'
                }
            )

        # BLOCK CHECK

        if user.is_blocked:

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Your account has been blocked'
                }
            )

        # PASSWORD CHECK

        if not check_password(password,user.password):

            return render(
                request,
                'accounts/signin.html',
                {
                    'error':'Incorrect password'
                }
            )

        # LOGIN SESSION

        request.session['user_id'] = user.id
        request.session['username'] = user.username
        request.session['email'] = user.email
        request.session['role'] = user.role
        request.session['is_logged_in'] = True

        # SESSION EXPIRY

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
        'accounts/signin.html'
    )



# LOGOUT VIEW

def logout_view(request):

    request.session.flush()

    return redirect('signin')