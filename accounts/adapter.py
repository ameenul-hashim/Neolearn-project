from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User


class CustomSocialAccountAdapter(
    DefaultSocialAccountAdapter
):

    def pre_social_login(
        self,
        request,
        sociallogin
    ):

        email=sociallogin.user.email

        existing_user=User.objects.filter(
            email=email
        ).exists()

        # NEW GOOGLE USER

        if not existing_user:

            request.session[
                'google_signup'
            ]=True

            username=email.split('@')[0]

            base_username=username

            counter=1

            while User.objects.filter(
                username=username
            ).exists():

                username=f"{base_username}{counter}"

                counter+=1

            sociallogin.user.username=username

        # EXISTING GOOGLE USER

        else:

            request.session[
                'google_signup'
            ]=False


    def get_login_redirect_url(
        self,
        request
    ):

        google_signup=request.session.get(
            'google_signup'
        )

        # NEW GOOGLE USER

        if google_signup:

            request.session.pop(
                'google_signup',
                None
            )

            return '/verification-success/'

        # EXISTING GOOGLE USER

        return '/dashboard/'