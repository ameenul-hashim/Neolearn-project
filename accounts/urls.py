from django.urls import path
from . import views

urlpatterns=[

    path('signup/',views.signup_view,name='signup'),
    path('verify-otp/',views.verify_otp_view,name='verify_otp'),
    path('verification-success/',views.verification_success_view,name='verification_success'),
    path('resend-otp/',views.resend_otp_view,name='resend_otp'),
    path('signin/',views.signin_view,name='signin'),
    path('forgot-password/',views.forgot_password_view,name='forgot_password'),
    path('forgot-password-verify/',views.forgot_password_verify_view,name='forgot_password_verify'),
    path('reset-password/',views.reset_password_view,name='reset_password'),
    path('resend-reset-otp/',views.resend_reset_otp_view,name='resend_reset_otp'),
]