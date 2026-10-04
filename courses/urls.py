from django.urls import path

from .views import (
    course_builder_view,
    course_create_chapter_view,
    course_edit_chapter_view,
    course_video_view,
    course_pdf_view,
    course_edit_pdf_view,
    course_quiz_view,
    course_edit_quiz_view,
    course_add_quiz_question_view,
    course_edit_quiz_question_view,
    course_delete_quiz_question_view,
    course_video_timeline_view,
    course_pdf_timeline_view,
    course_quiz_timeline_view,
    course_live_view,
)


# app_name intentionally removed.
# Views use reverse("course_builder", ...) without a namespace,
# so adding app_name here would break them.


urlpatterns = [
    # ============================================================
    # COURSE BUILDER WORKSPACE (shared: admin + teacher)
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
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/video/<int:video_id>/timeline/",
        course_video_timeline_view,
        name="course_video_timeline",
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
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/timeline/",
        course_pdf_timeline_view,
        name="course_pdf_timeline",
    ),

    # ============================================================
    # QUIZZES
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/",
        course_quiz_view,
        name="course_quiz",
    ),
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/edit/",
        course_edit_quiz_view,
        name="course_edit_quiz",
    ),
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/timeline/",
        course_quiz_timeline_view,
        name="course_quiz_timeline",
    ),

    # ============================================================
    # QUIZ QUESTIONS
    # ============================================================
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/question/add/",
        course_add_quiz_question_view,
        name="course_add_quiz_question",
    ),
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/question/<int:question_id>/edit/",
        course_edit_quiz_question_view,
        name="course_edit_quiz_question",
    ),
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/question/<int:question_id>/delete/",
        course_delete_quiz_question_view,
        name="course_delete_quiz_question",
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