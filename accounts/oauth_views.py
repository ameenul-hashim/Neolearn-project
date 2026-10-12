
from django.shortcuts import redirect


# ============================================================
# GOOGLE SIGNUP
# ============================================================

def google_signup(request):

    request.session["google_auth_type"] = "signup"
    request.session.modified = True

    return redirect("/accounts/google/login/")


# ============================================================
# GOOGLE SIGNIN
# ============================================================

def google_signin(request):

    request.session["google_auth_type"] = "signin"
    request.session.modified = True

    return redirect("/accounts/google/login/")
