# teachers/urls.py

from django.urls import path

from .views import (
    teacher_login_view,
    teacher_change_password_view,
    teacher_logout_view,
    teacher_dashboard_view,
    teacher_batches_view,
    teacher_subjects_view,
    teacher_course_builder_entry_view,
    teacher_my_profile_view,
    teacher_edit_profile_view,
    teacher_colleagues_view,
    teacher_colleague_detail_view,
    teacher_help_videos_view,
    teacher_analytics_view,
)

urlpatterns = [
    path(
        "teacher/login/",
        teacher_login_view,
        name="teacher_login",
    ),
    path(
        "teacher/change-password/",
        teacher_change_password_view,
        name="teacher_change_password",
    ),
    path(
        "logout/",
        teacher_logout_view,
        name="teacher_logout",
    ),
    path(
        "dashboard/",
        teacher_dashboard_view,
        name="teacher_dashboard",
    ),
    path(
        "batches/",
        teacher_batches_view,
        name="teacher_batches",
    ),
    path(
        "batch/<int:batch_id>/subjects/",
        teacher_subjects_view,
        name="teacher_subjects",
    ),
    path(
        "batch/<int:batch_id>/subjects/<int:subject_id>/course-builder/",
        teacher_course_builder_entry_view,
        name="teacher_course_builder_entry",
    ),
    path(
        "my-profile/",
        teacher_my_profile_view,
        name="teacher_my_profile",
    ),
    path(
        "my-profile/edit/",
        teacher_edit_profile_view,
        name="teacher_edit_profile",
    ),


    path(
        "colleagues/",
        teacher_colleagues_view,
        name="teacher_colleagues",
    ),
    path(
        "colleagues/<int:teacher_id>/",
        teacher_colleague_detail_view,
        name="teacher_colleague_detail",
    ),

    path(
    "help-videos/",
    teacher_help_videos_view,
    name="teacher_help_videos",
    ),
    
    path(
    "analytics/",
    teacher_analytics_view,
    name="teacher_analytics",
),
]
