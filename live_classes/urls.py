
from django.urls import path

from .views import (
    # Teacher
    teacher_live_classes_view,
    teacher_upcoming_classes_view,
    teacher_cancellation_requests_view,
    teacher_reschedule_live_class_view,
    teacher_request_live_class_cancellation_view,

    # Admin
    admin_live_schedule_view,
    admin_reschedule_live_class_view,
    admin_review_cancellation_view,
    admin_upcoming_classes_view,
    admin_cancel_live_class_view,
    admin_cancellation_requests_view,
)

app_name = "live_classes"

urlpatterns = [

    # ==========================================
    # TEACHER: TIMETABLE AND BOOKING
    # ==========================================
    path(
        "teacher/",
        teacher_live_classes_view,
        name="teacher_live_classes",
    ),

    # ==========================================
    # TEACHER: UPCOMING CLASSES
    # ==========================================
    path(
        "teacher/upcoming/",
        teacher_upcoming_classes_view,
        name="teacher_upcoming_classes",
    ),

    # ==========================================
    # TEACHER: RESCHEDULE AND CANCELLATION
    # ==========================================
    path(
        "teacher/class/<int:class_id>/reschedule/",
        teacher_reschedule_live_class_view,
        name="teacher_reschedule_live_class",
    ),
    path(
        "teacher/class/<int:class_id>/request-cancellation/",
        teacher_request_live_class_cancellation_view,
        name="teacher_request_cancellation",
    ),

    # ==========================================
    # TEACHER: CANCELLATION REQUEST HISTORY
    # ==========================================
    path(
        "teacher/cancellation-requests/",
        teacher_cancellation_requests_view,
        name="teacher_cancellation_requests",
    ),

    # ==========================================
    # ADMIN: TIMETABLE AND BOOKING
    # ==========================================
    path(
        "admin/",
        admin_live_schedule_view,
        name="admin_live_schedule",
    ),
    path(
        "admin/class/<int:class_id>/reschedule/",
        admin_reschedule_live_class_view,
        name="admin_reschedule_live_class",
    ),

    # ==========================================
    # ADMIN: CANCELLATION REQUEST REVIEW
    # ==========================================
    path(
        "admin/cancellation/<int:request_id>/review/",
        admin_review_cancellation_view,
        name="admin_review_cancellation",
    ),
    path(
        "admin/cancellation-requests/",
        admin_cancellation_requests_view,
        name="admin_cancellation_requests",
    ),

    # ==========================================
    # ADMIN: UPCOMING CLASSES
    # ==========================================
    path(
        "admin/upcoming/",
        admin_upcoming_classes_view,
        name="admin_upcoming_classes",
    ),
    path(
        "admin/class/<int:class_id>/cancel/",
        admin_cancel_live_class_view,
        name="admin_cancel_live_class",
    ),
]
