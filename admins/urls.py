from django.urls import path

from .views import (
    # ==========================================================
    # AUTH
    # ==========================================================
    admin_signin_view,
    admin_dashboard_view,
    admin_logout_view,

    # ==========================================================
    # STUDENTS
    # ==========================================================
    admin_students_view,
    block_student_view,
    unblock_student_view,
    delete_student_view,

    # ==========================================================
    # BATCHES
    # ==========================================================
    admin_batches_view,
    create_batch_view,
    edit_batch_view,
    delete_batch_view,
    batch_subjects,

    # ==========================================================
    # SUBJECTS
    # ==========================================================
    admin_subjects_view,
    create_subject_view,
    edit_subject_view,
    delete_subject_view,

    # ==========================================================
    # TEACHERS
    # ==========================================================
    admin_teachers,
    create_teacher_view,
    admin_assign_teacher_batch,
    admin_teacher_assignments,
    admin_view_teacher_subjects,
    admin_remove_teacher_batch,
    admin_remove_teacher_subject,
    admin_block_teacher,
    admin_unblock_teacher,
    admin_delete_teacher,
    get_teacher_batches_data,

    # ==========================================================
    # COUPONS
    # ==========================================================
    admin_coupons_view,
    create_coupon_view,
    edit_coupon_view,
    toggle_coupon_status_view,
    delete_coupon_view,

    # ==========================================================
    # ADMIN COURSE BUILDER
    # ==========================================================
    admin_course_builder_entry_view,
)


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


    # ==========================================================
# COUPONS
# ==========================================================

# Coupon listing page
path(
    "coupons/",
    admin_coupons_view,
    name="admin_coupons",
),

# Create coupon page
path(
    "coupons/create/",
    create_coupon_view,
    name="create_coupon",
),

# Edit coupon page
path(
    "coupons/edit/<int:coupon_id>/",
    edit_coupon_view,
    name="edit_coupon",
),

# Activate / Deactivate coupon
path(
    "coupons/<int:coupon_id>/toggle/",
    toggle_coupon_status_view,
    name="toggle_coupon_status",
),

# Delete coupon
path(
    "coupons/<int:coupon_id>/delete/",
    delete_coupon_view,
    name="delete_coupon",
),


    # ==========================================================
    # ADMIN COURSE BUILDER
    # ==========================================================

    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/",
        admin_course_builder_entry_view,
        name="admin_course_builder_entry",
    ),

]