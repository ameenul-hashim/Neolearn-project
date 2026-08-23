from django.urls import path
from .views import *


urlpatterns = [
    # ========================================================
    # AUTHENTICATION
    # ========================================================

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

    # ========================================================
    # TEACHER DASHBOARD
    # ========================================================

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

    # ========================================================
    # COURSE BUILDER
    # ========================================================

    path(
        "subjects/<int:subject_id>/builder/",
        teacher_course_builder_view,
        name="teacher_course_builder",
    ),

    # ========================================================
    # CHAPTER
    # ========================================================

    path(
        "subjects/<int:subject_id>/builder/chapter/create/",
        teacher_create_chapter_view,
        name="teacher_create_chapter",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/",
        teacher_chapter_view,
        name="teacher_chapter",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/edit/",
        teacher_edit_chapter_view,
        name="teacher_edit_chapter",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/delete-request/",
        teacher_request_chapter_delete_view,
        name="teacher_request_chapter_delete",
    ),

    # ========================================================
    # VIDEO
    # ========================================================

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/videos/",
        teacher_chapter_videos_view,
        name="teacher_chapter_videos",
    ),

    # ========================================================
    # PDF
    # ========================================================

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/pdfs/",
        teacher_chapter_pdfs_view,
        name="teacher_chapter_pdfs",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/timeline/",
        teacher_pdf_timeline_view,
        name="teacher_pdf_timeline_view",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/edit/",
        teacher_edit_pdf_view,
        name="teacher_edit_pdf_view",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/delete-request/",
        teacher_request_pdf_delete_view,
        name="teacher_request_pdf_delete_view",
    ),

    # ========================================================
    # QUIZ
    #
    # Current scope:
    # - Quiz workspace
    # - Quiz create
    # - Quiz edit
    # - Quiz timeline
    # - Quiz delete request
    #
    # Student attempts/results are intentionally not routed yet.
    # ========================================================

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/quizzes/",
        teacher_chapter_quizzes_view,
        name="teacher_chapter_quizzes",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/edit/",
        teacher_edit_quiz_view,
        name="teacher_edit_quiz_view",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/timeline/",
        teacher_quiz_timeline_view,
        name="teacher_quiz_timeline_view",
    ),

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/delete-request/",
        teacher_request_quiz_delete_view,
        name="teacher_request_quiz_delete_view",
    ),

    # ========================================================
    # LIVE
    # ========================================================

    path(
        "subjects/<int:subject_id>/builder/chapter/<int:chapter_id>/live/",
        teacher_chapter_live_view,
        name="teacher_chapter_live",
    ),
]