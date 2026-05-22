from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.contrib import messages


# GOOGLE SIGNUP CHECK

def google_signup(request):

    request.session['google_auth_type'] = 'signup'

    return redirect('/accounts/google/login/')


# GOOGLE SIGNIN CHECK

def google_signin(request):

    request.session['google_auth_type'] = 'signin'

    return redirect('/accounts/google/login/')