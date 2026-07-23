from django.db import models
from admins.models import Batch, Subject, Teacher, TeacherSubject

class CourseChapter(models.Model):

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
    ]

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="course_chapters"
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="course_chapters"
    )

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="created_chapters"
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="updated_chapters"
    )

    chapter_name = models.CharField(max_length=255)

    chapter_order = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft"
    )

    delete_requested = models.BooleanField(default=False)

    delete_requested_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chapter_delete_requests"
    )

    delete_requested_at = models.DateTimeField(
        null=True,
        blank=True
    )

    delete_reason = models.TextField(
        blank=True
    )

    DELETE_STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    delete_status = models.CharField(
        max_length=20,
        choices=DELETE_STATUS,
        default="pending"
    )

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["chapter_order"]

    def __str__(self):
        return self.chapter_name