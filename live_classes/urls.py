
from django.urls import path

from .views import (
    teacher_live_classes_view,
    admin_live_schedule_view,
    teacher_reschedule_live_class_view,
    teacher_request_live_class_cancellation_view,
    admin_reschedule_live_class_view,
    admin_review_cancellation_view,
)

app_name = "live_classes"

urlpatterns = [
    path(
        "teacher/",
        teacher_live_classes_view,
        name="teacher_live_classes",
    ),
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
    path(
        "admin/cancellation/<int:request_id>/review/",
        admin_review_cancellation_view,
        name="admin_review_cancellation",
    ),
]
