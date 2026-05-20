from django.urls import path
from . import views

urlpatterns=[

    path('signup/',views.signup_view,name='signup'),
    path('verify-otp/',views.verify_otp_view,name='verify_otp'),
    path('verification-success/',views.verification_success_view,name='verification_success'),
    path('resend-otp/',views.resend_otp_view,name='resend_otp'),
    path('signin/',views.signin_view,name='signin'),
]