from django.urls import path
from .views import *

urlpatterns = [
    path("teacher/login/",teacher_login_view,name="teacher_login"),
    # path("teacher/change-password/",teacher_change_password_view,name="teacher_change_password"),

]