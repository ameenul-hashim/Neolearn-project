
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse

from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import reverse


class GoogleAccountAdapter(DefaultSocialAccountAdapter):

    # ============================================================
    # ROLE CHECK
    # ============================================================

    @staticmethod
    def is_teacher_or_admin(user):
        if not user or not user.is_authenticated:
            return False

        if user.is_staff or user.is_superuser:
            return True

        if hasattr(user, "teacher_profile"):
            return True

        return False

    # ============================================================
    # BLOCK GOOGLE AUTHENTICATION WITH A MESSAGE
    # ============================================================

    @staticmethod
    def stop_google_authentication(request, message, destination):
        messages.error(request, message)

        request.session.pop("google_auth_type", None)

        raise ImmediateHttpResponse(
            redirect(reverse(destination))
        )

    # ============================================================
    # GOOGLE USERNAME GENERATION
    # ============================================================

    def populate_user(self, request, sociallogin, data):

        user = super().populate_user(
            request,
            sociallogin,
            data,
        )

        email = (
            data.get("email")
            or ""
        ).strip().lower()

        first_name = (
            data.get("first_name")
            or ""
        ).strip()

        last_name = (
            data.get("last_name")
            or ""
        ).strip()

        if email:
            base_username = email.split("@")[0].lower()
        else:
            base_username = "student"

        # Keep the username within Django's default limit.
        base_username = base_username[:140] or "student"

        username = base_username
        counter = 1

        # Generate a unique username.
        while User.objects.filter(username=username).exists():
            suffix = str(counter)
            username = f"{base_username[:150 - len(suffix)]}{suffix}"
            counter += 1

        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.email = email

        return user

    # ============================================================
    # VALIDATE GOOGLE SIGNUP / SIGNIN BEFORE LOGIN
    # ============================================================

    def pre_social_login(self, request, sociallogin):

        auth_type = request.session.get(
            "google_auth_type",
            "signin",
        )

        if auth_type not in ("signup", "signin"):
            auth_type = "signin"

        # Check the account already connected to Google.
        if sociallogin.is_existing:

            user = sociallogin.user

            # Never allow a teacher/admin through student Google auth.
            if self.is_teacher_or_admin(user):
                self.stop_google_authentication(
                    request,
                    (
                        "This is a teacher or admin account. "
                        "Please use your own login area."
                    ),
                    "signin",
                )

            # Signup must not be used to enter an existing account.
            if auth_type == "signup":
                self.stop_google_authentication(
                    request,
                    (
                        "A NeoLearn account already exists for this "
                        "Google account. Please sign in instead."
                    ),
                    "signin",
                )

            # Existing linked student using Google signin: allow.
            request.session.pop("google_auth_type", None)
            return

        # This Google account is not yet connected to a NeoLearn user.
        email = (
            getattr(sociallogin.user, "email", "")
            or ""
        ).strip().lower()

        existing_user = None

        if email:
            existing_user = User.objects.filter(
                email__iexact=email
            ).first()

        # If the email belongs to a teacher/admin, block student auth.
        if existing_user and self.is_teacher_or_admin(existing_user):
            self.stop_google_authentication(
                request,
                (
                    "This email belongs to a teacher or admin account. "
                    "Please use your own login area."
                ),
                "signin",
            )

        # Google signup with an email already registered in NeoLearn.
        if auth_type == "signup" and existing_user:
            self.stop_google_authentication(
                request,
                (
                    "An account with this email already exists. "
                    "Please sign in instead."
                ),
                "signin",
            )

        # Google signin must not create a new account.
        if auth_type == "signin":

            if existing_user:
                self.stop_google_authentication(
                    request,
                    (
                        "This email already has a NeoLearn account, "
                        "but it is not linked to Google. Please sign "
                        "in with your NeoLearn username and password."
                    ),
                    "signin",
                )

            self.stop_google_authentication(
                request,
                (
                    "No NeoLearn account is linked to this Google "
                    "account. Please create an account first."
                ),
                "signup",
            )

        # New email + explicit signup: allow Allauth to create a student.
        request.session.pop("google_auth_type", None)

    # ============================================================
    # GOOGLE AUTHENTICATION ERRORS
    # ============================================================

    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):

        auth_type = request.session.pop(
            "google_auth_type",
            "signin",
        )

        if auth_type not in ("signup", "signin"):
            auth_type = "signin"

        messages.error(
            request,
            (
                "Google authentication could not be completed. "
                "Please try again or use your NeoLearn account."
            ),
        )

        raise ImmediateHttpResponse(
            redirect(
                reverse(
                    "signup" if auth_type == "signup" else "signin"
                )
            )
        )
