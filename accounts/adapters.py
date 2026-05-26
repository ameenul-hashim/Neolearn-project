from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User
import random



class GoogleAccountAdapter(
    DefaultSocialAccountAdapter
):


    def populate_user(
        self,
        request,
        sociallogin,
        data
    ):

        user=super().populate_user(
            request,
            sociallogin,
            data
        )

        email=data.get(
            'email',
            ''
        )

        first_name=data.get(
            'first_name',
            ''
        )

        last_name=data.get(
            'last_name',
            ''
        )


        # AUTO USERNAME

        if email:

            base_username=email.split('@')[0].lower()

        else:

            base_username='student'


        username=base_username


        # UNIQUE USERNAME

        while User.objects.filter(
            username=username
        ).exists():

            username=f'{base_username}{random.randint(1000,9999)}'


        user.username=username

        user.first_name=first_name

        user.last_name=last_name

        user.email=email

        return user



    def get_login_redirect_url(
        self,
        request
    ):

        return '/students/dashboard/'
    

SOCIALACCOUNT_PROVIDERS={

    'google':{

        'SCOPE':[

            'profile',
            'email',
        ],

        'AUTH_PARAMS':{

            'access_type':'online',
        },

        'OAUTH_PKCE_ENABLED':True,
    }
}

