from django.urls import path

from .views import course_builder_view


urlpatterns = [
    path(
        "batches/<int:batch_id>/subjects/<int:subject_id>/course-builder/",
        course_builder_view,
        name="course_builder",
    ),
]