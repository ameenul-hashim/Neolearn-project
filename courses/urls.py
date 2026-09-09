from django.urls import path

from .views import (
    course_builder_view,
    course_create_chapter_view,
    course_edit_chapter_view,
    course_video_view,
    course_pdf_view,
    course_edit_pdf_view,
    course_quiz_view,
    course_request_chapter_delete_view,
    course_request_pdf_delete_view,
    course_request_quiz_delete_view,
    course_video_timeline_view,
    course_pdf_timeline_view,
    course_quiz_timeline_view,
    course_live_view,
)


app_name = "courses"


urlpatterns = [
    # ============================================================
    # COURSE BUILDER WORKSPACE
    # Shared by Admin + Teacher
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/",
        course_builder_view,
        name="course_builder",
    ),

    # ============================================================
    # CHAPTERS
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/create/",
        course_create_chapter_view,
        name="course_create_chapter",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/edit/",
        course_edit_chapter_view,
        name="course_edit_chapter",
    ),

    # ============================================================
    # VIDEOS
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/video/",
        course_video_view,
        name="course_video",
    ),

    # ============================================================
    # PDFs
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/pdf/",
        course_pdf_view,
        name="course_pdf",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/edit/",
        course_edit_pdf_view,
        name="course_edit_pdf",
    ),

    # ============================================================
    # QUIZZES
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/",
        course_quiz_view,
        name="course_quiz",
    ),

    # ============================================================
    # TEACHER DELETE REQUESTS
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/delete-request/",
        course_request_chapter_delete_view,
        name="course_request_chapter_delete",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/delete-request/",
        course_request_pdf_delete_view,
        name="course_request_pdf_delete",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/delete-request/",
        course_request_quiz_delete_view,
        name="course_request_quiz_delete",
    ),

    # ============================================================
    # TIMELINES
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/video/<int:video_id>/timeline/",
        course_video_timeline_view,
        name="course_video_timeline",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/timeline/",
        course_pdf_timeline_view,
        name="course_pdf_timeline",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/timeline/",
        course_quiz_timeline_view,
        name="course_quiz_timeline",
    ),

    # ============================================================
    # LIVE CLASS WORKSPACE
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/live/",
        course_live_view,
        name="course_live_workspace",
    ),
]