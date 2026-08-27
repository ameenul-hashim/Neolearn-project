from django.urls import path
from .views import *


urlpatterns = [

    # ==========================================================
    # AUTH
    # ==========================================================

    path(
        "signin/",
        admin_signin_view,
        name="admin_signin",
    ),

    path(
        "dashboard/",
        admin_dashboard_view,
        name="admin_dashboard",
    ),

    path(
        "logout/",
        admin_logout_view,
        name="admin_logout",
    ),


    # ==========================================================
    # STUDENTS
    # ==========================================================

    path(
        "students/",
        admin_students_view,
        name="admin_students",
    ),

    path(
        "students/block/<int:user_id>/",
        block_student_view,
        name="block_student",
    ),

    path(
        "students/unblock/<int:user_id>/",
        unblock_student_view,
        name="unblock_student",
    ),

    path(
        "students/delete/<int:user_id>/",
        delete_student_view,
        name="delete_student",
    ),


    # ==========================================================
    # BATCHES
    # ==========================================================

    path(
        "batches/",
        admin_batches_view,
        name="admin_batches",
    ),

    path(
        "batches/create/",
        create_batch_view,
        name="create_batch",
    ),

    path(
        "edit-batch/<int:batch_id>/",
        edit_batch_view,
        name="edit_batch",
    ),

    path(
        "batches/delete/<int:batch_id>/",
        delete_batch_view,
        name="delete_batch",
    ),

    path(
        "batches/<int:batch_id>/subjects/",
        batch_subjects,
        name="batch_subjects",
    ),


    # ==========================================================
    # SUBJECTS
    # ==========================================================

    path(
        "subjects/",
        admin_subjects_view,
        name="admin_subjects",
    ),

    path(
        "subjects/create/",
        create_subject_view,
        name="create_subject",
    ),

    path(
        "subjects/edit/<int:subject_id>/",
        edit_subject_view,
        name="edit_subject",
    ),

    path(
        "subjects/delete/<int:subject_id>/",
        delete_subject_view,
        name="delete_subject",
    ),


    # ==========================================================
    # ADMIN COURSE BUILDER
    # ==========================================================

    path(
        "subjects/<int:subject_id>/content/",
        admin_subject_course_builder_view,
        name="admin_subject_course_builder",
    ),


    # ==========================================================
    # ADMIN COURSE BUILDER — CHAPTER
    # ==========================================================

    # Create Chapter
    path(
        "subjects/<int:subject_id>/content/chapter/create/",
        admin_create_chapter_view,
        name="admin_create_chapter",
    ),

    # Edit Chapter
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/edit/",
        admin_edit_chapter_view,
        name="admin_edit_chapter",
    ),

    # Chapter Timeline
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/timeline/",
        admin_chapter_timeline_view,
        name="admin_chapter_timeline",
    ),

    # Chapter Delete
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/delete/",
        admin_delete_chapter_view,
        name="admin_delete_chapter",
    ),


    # ==========================================================
    # ADMIN COURSE BUILDER — VIDEO
    # ==========================================================

    # Upload / Create Video
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/video/upload/",
        admin_upload_video_view,
        name="admin_upload_video",
    ),

    # Play / Preview Video
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/video/<int:video_id>/play/",
        admin_play_video_view,
        name="admin_play_video",
    ),

    # Edit Video
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/video/<int:video_id>/edit/",
        admin_edit_video_view,
        name="admin_edit_video",
    ),

    # Video Timeline
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/video/<int:video_id>/timeline/",
        admin_video_timeline_view,
        name="admin_video_timeline",
    ),

    # Video Delete
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/video/<int:video_id>/delete/",
        admin_delete_video_view,
        name="admin_delete_video",
    ),


    # ==========================================================
    # ADMIN COURSE BUILDER — PDF
    # ==========================================================

    # Upload PDF
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/pdf/upload/",
        admin_upload_pdf_view,
        name="admin_upload_pdf",
    ),

    # Open PDF
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/pdf/<int:pdf_id>/open/",
        admin_open_pdf_view,
        name="admin_open_pdf",
    ),

    # Edit PDF
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/pdf/<int:pdf_id>/edit/",
        admin_edit_pdf_view,
        name="admin_edit_pdf",
    ),

    # PDF Timeline
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/pdf/<int:pdf_id>/timeline/",
        admin_pdf_timeline_view,
        name="admin_pdf_timeline",
    ),

    # PDF Delete
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/pdf/<int:pdf_id>/delete/",
        admin_delete_pdf_view,
        name="admin_delete_pdf",
    ),


    # ==========================================================
    # ADMIN COURSE BUILDER — QUIZ
    # ==========================================================

    # Create Quiz
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/quiz/create/",
        admin_create_quiz_view,
        name="admin_create_quiz",
    ),

    # View Quiz
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/quiz/<int:quiz_id>/view/",
        admin_view_quiz_view,
        name="admin_view_quiz",
    ),

    # Edit Quiz + Questions
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/quiz/<int:quiz_id>/edit/",
        admin_edit_quiz_view,
        name="admin_edit_quiz",
    ),

    # Quiz Timeline
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/quiz/<int:quiz_id>/timeline/",
        admin_quiz_timeline_view,
        name="admin_quiz_timeline",
    ),

    # Quiz Delete
    path(
        "subjects/<int:subject_id>/content/chapter/<int:chapter_id>/quiz/<int:quiz_id>/delete/",
        admin_delete_quiz_view,
        name="admin_delete_quiz",
    ),


    # ==========================================================
    # ADMIN COURSE BUILDER — DELETE REQUESTS
    # ==========================================================

    path(
        "subjects/<int:subject_id>/content/delete-requests/",
        admin_delete_requests_view,
        name="admin_delete_requests",
    ),

    path(
        "subjects/<int:subject_id>/content/delete-request/<int:request_id>/approve/",
        admin_approve_delete_request_view,
        name="admin_approve_delete_request",
    ),

    path(
        "subjects/<int:subject_id>/content/delete-request/<int:request_id>/reject/",
        admin_reject_delete_request_view,
        name="admin_reject_delete_request",
    ),


    # ==========================================================
    # ADMIN COURSE BUILDER — AUDIT
    # ==========================================================

    path(
        "subjects/<int:subject_id>/content/audit/",
        admin_course_audit_view,
        name="admin_course_audit",
    ),


    # ==========================================================
    # TEACHERS
    # ==========================================================

    path(
        "teachers/",
        admin_teachers,
        name="admin_teachers",
    ),

    path(
        "teachers/create/",
        create_teacher_view,
        name="create_teacher",
    ),

    path(
        "teachers/<int:teacher_id>/assign-batch/",
        admin_assign_teacher_batch,
        name="admin_assign_teacher_batch",
    ),

    path(
        "teachers/<int:teacher_id>/assignments/",
        admin_teacher_assignments,
        name="admin_teacher_assignments",
    ),

    path(
        "teachers/<int:teacher_id>/batch/<int:batch_id>/subjects/",
        admin_view_teacher_subjects,
        name="admin_view_teacher_subjects",
    ),

    path(
        "teacher-batch/<int:assignment_id>/remove/",
        admin_remove_teacher_batch,
        name="admin_remove_teacher_batch",
    ),

    path(
        "teacher-subject/<int:assignment_id>/remove/",
        admin_remove_teacher_subject,
        name="admin_remove_teacher_subject",
    ),

    path(
        "teachers/<int:teacher_id>/block/",
        admin_block_teacher,
        name="admin_block_teacher",
    ),

    path(
        "teachers/<int:teacher_id>/unblock/",
        admin_unblock_teacher,
        name="admin_unblock_teacher",
    ),

    path(
        "teachers/<int:teacher_id>/delete/",
        admin_delete_teacher,
        name="admin_delete_teacher",
    ),

    path(
        "teachers/<int:teacher_id>/batches-data/",
        get_teacher_batches_data,
        name="get_teacher_batches_data",
    ),

]