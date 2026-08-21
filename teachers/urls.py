from django.urls import path
from .views import *


urlpatterns = [
    path("teacher/login/",teacher_login_view,name="teacher_login",),
    path("teacher/change-password/",teacher_change_password_view,name="teacher_change_password",),
    path("logout/",teacher_logout_view,name="teacher_logout",),
    path("dashboard/",teacher_dashboard_view,name="teacher_dashboard",),
    path("batches/",teacher_batches_view,name="teacher_batches",),
    path("batch/<int:batch_id>/subjects/",teacher_subjects_view,name="teacher_subjects",),
    path("subjects/<int:subject_id>/builder/",teacher_course_builder_view,name="teacher_course_builder",),
    path("subjects/<int:subject_id>/builder/chapter/create/",teacher_create_chapter_view,name="teacher_create_chapter",),
    path("subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/",teacher_chapter_view,name="teacher_chapter",),
    path("subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/edit/",teacher_edit_chapter_view,name="teacher_edit_chapter",),
    path("subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/delete-request/",teacher_request_chapter_delete_view,name="teacher_request_chapter_delete",),
    path("subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/videos/",teacher_chapter_videos_view,name="teacher_chapter_videos",),
    path("subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/pdfs/",teacher_chapter_pdfs_view,name="teacher_chapter_pdfs",),
    path("subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/quizzes/",teacher_chapter_quizzes_view,name="teacher_chapter_quizzes",),
    path("subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/live/",teacher_chapter_live_view,name="teacher_chapter_live",),
    
]