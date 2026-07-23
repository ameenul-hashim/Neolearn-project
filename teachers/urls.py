from django.urls import path

from .views import *

urlpatterns = [
    path("teacher/login/",teacher_login_view,name="teacher_login"),
    path("teacher/change-password/",teacher_change_password_view,name="teacher_change_password"),
    path("dashboard/",teacher_dashboard_view,name="teacher_dashboard",),
    path("logout/",teacher_logout_view,name="teacher_logout"),
    path("batches/",teacher_batches_view,name="teacher_batches"),
    path("batch/<int:batch_id>/subjects/",teacher_subjects_view,name="teacher_subjects"),
    path("subjects/<int:subject_id>/builder/",teacher_course_builder_view,name="teacher_course_builder"),
    path("subjects/<int:subject_id>/builder/",teacher_course_builder_view,name="teacher_course_builder"),
]