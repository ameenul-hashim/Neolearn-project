from django.urls import path

from .views import (
    # ============================================================
    # COURSE BUILDER
    # ============================================================

    course_builder_view,

    # ============================================================
    # CHAPTER
    # ============================================================

    create_chapter_view,
    edit_chapter_view,
    chapter_details_view,

    # ============================================================
    # VIDEO
    # ============================================================

    create_video_view,
    edit_video_view,

    # ============================================================
    # PDF
    # ============================================================

    create_pdf_view,
    edit_pdf_view,

    # ============================================================
    # QUIZ
    # ============================================================

    create_quiz_view,
    edit_quiz_view,

    # ============================================================
    # DELETE
    # ============================================================

    teacher_request_delete_view,
    admin_direct_delete_view,

    # ============================================================
    # DELETION AUDIT
    # ============================================================

    admin_deletion_audit_list_view,
    admin_deletion_audit_detail_view,
    admin_approve_delete_view,
    admin_reject_delete_view,
)


app_name = "courses"


urlpatterns = [

    # ============================================================
    # COURSE BUILDER
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/",
        course_builder_view,
        name="course_builder",
    ),


    # ============================================================
    # CHAPTER
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/<int:chapter_id>/details/",
        chapter_details_view,
        name="chapter_details",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/create/",
        create_chapter_view,
        name="create_chapter",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/<int:chapter_id>/edit/",
        edit_chapter_view,
        name="edit_chapter",
    ),


    # ============================================================
    # VIDEO
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/<int:chapter_id>/video/create/",
        create_video_view,
        name="create_video",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/<int:chapter_id>/video/<int:video_id>/edit/",
        edit_video_view,
        name="edit_video",
    ),


    # ============================================================
    # PDF
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/<int:chapter_id>/pdf/create/",
        create_pdf_view,
        name="create_pdf",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/edit/",
        edit_pdf_view,
        name="edit_pdf",
    ),


    # ============================================================
    # QUIZ
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/<int:chapter_id>/quiz/create/",
        create_quiz_view,
        name="create_quiz",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/edit/",
        edit_quiz_view,
        name="edit_quiz",
    ),


    # ============================================================
    # TEACHER DELETE REQUEST
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/delete-request/<str:content_type>/<int:object_id>/",
        teacher_request_delete_view,
        name="teacher_request_delete",
    ),


    # ============================================================
    # ADMIN DIRECT DELETE
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/"
        "course-builder/delete/<str:content_type>/<int:object_id>/",
        admin_direct_delete_view,
        name="admin_direct_delete",
    ),


    # ============================================================
    # DELETION AUDIT
    # ============================================================

    path(
        "deletion-audit/",
        admin_deletion_audit_list_view,
        name="admin_deletion_audit_list",
    ),

    path(
        "deletion-audit/<int:audit_id>/",
        admin_deletion_audit_detail_view,
        name="admin_deletion_audit_detail",
    ),

    path(
        "deletion-audit/<int:audit_id>/approve/",
        admin_approve_delete_view,
        name="admin_approve_delete",
    ),

    path(
        "deletion-audit/<int:audit_id>/reject/",
        admin_reject_delete_view,
        name="admin_reject_delete",
    ),
]