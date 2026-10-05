from django.urls import path

from .views import (
    course_builder_view,

    create_chapter_view,
    edit_chapter_view,
    change_chapter_order_view,

    create_video_view,
    edit_video_view,
    change_video_order_view,

    create_pdf_view,
    edit_pdf_view,
    change_pdf_order_view,

    create_quiz_view,
    edit_quiz_view,
    change_quiz_order_view,

    teacher_request_delete_view,
    admin_direct_delete_view,

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
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/create/",
        create_chapter_view,
        name="create_chapter",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/edit/",
        edit_chapter_view,
        name="edit_chapter",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/order/",
        change_chapter_order_view,
        name="change_chapter_order",
    ),


    # ============================================================
    # VIDEO
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/video/create/",
        create_video_view,
        name="create_video",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/video/<int:video_id>/edit/",
        edit_video_view,
        name="edit_video",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/video/<int:video_id>/order/",
        change_video_order_view,
        name="change_video_order",
    ),


    # ============================================================
    # PDF
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/pdf/create/",
        create_pdf_view,
        name="create_pdf",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/edit/",
        edit_pdf_view,
        name="edit_pdf",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/pdf/<int:pdf_id>/order/",
        change_pdf_order_view,
        name="change_pdf_order",
    ),


    # ============================================================
    # QUIZ
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/create/",
        create_quiz_view,
        name="create_quiz",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/edit/",
        edit_quiz_view,
        name="edit_quiz",
    ),

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/chapter/<int:chapter_id>/quiz/<int:quiz_id>/order/",
        change_quiz_order_view,
        name="change_quiz_order",
    ),


    # ============================================================
    # TEACHER DELETE REQUEST
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/delete-request/<str:content_type>/<int:object_id>/",
        teacher_request_delete_view,
        name="teacher_request_delete",
    ),


    # ============================================================
    # ADMIN DIRECT DELETE
    # ============================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/delete/<str:content_type>/<int:object_id>/",
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