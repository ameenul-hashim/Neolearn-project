from django.db import models
from cloudinary.models import CloudinaryField

from admins.models import Batch, Subject, Teacher


# =========================================================
# COURSE CHAPTER
# =========================================================

class CourseChapter(models.Model):

    # =========================================================
    # STATUS
    # =========================================================

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
    ]

    # =========================================================
    # COURSE RELATION
    # =========================================================

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="course_chapters",
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="course_chapters",
    )

    # =========================================================
    # TEACHER TRACKING
    # =========================================================

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="created_chapters",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="updated_chapters",
    )

    # =========================================================
    # CHAPTER INFORMATION
    # =========================================================

    chapter_name = models.CharField(
        max_length=255,
    )

    chapter_description = models.CharField(
        max_length=255,
        blank=True,
    )

    chapter_order = models.PositiveIntegerField(
        default=1,
    )

    # =========================================================
    # PUBLISH STATUS
    # =========================================================

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft",
    )

    # =========================================================
    # DELETE REQUEST
    # =========================================================

    delete_requested = models.BooleanField(
        default=False,
    )

    delete_requested_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chapter_delete_requests",
    )

    delete_requested_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    delete_reason = models.TextField(
        blank=True,
    )

    DELETE_STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    delete_status = models.CharField(
        max_length=20,
        choices=DELETE_STATUS,
        default="pending",
    )

    # =========================================================
    # SOFT DELETE
    # =========================================================

    is_deleted = models.BooleanField(
        default=False,
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = [
            "chapter_order",
        ]

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return self.chapter_name


# =========================================================
# CHAPTER CHANGE / TIMELINE
# =========================================================

class ChapterChangeLog(models.Model):

    # =========================================================
    # ACTIONS
    # =========================================================

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("order_changed", "Order Changed"),
        ("status_changed", "Status Changed"),
        ("delete_requested", "Delete Requested"),
        ("delete_approved", "Delete Approved"),
        ("delete_rejected", "Delete Rejected"),
        ("restored", "Restored"),
    ]

    # =========================================================
    # RELATION
    # =========================================================

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    # =========================================================
    # TEACHER WHO PERFORMED ACTION
    # =========================================================

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="chapter_change_logs",
    )

    # =========================================================
    # ACTION
    # =========================================================

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
    )

    # =========================================================
    # FIELD CHANGE INFORMATION
    # =========================================================

    field_name = models.CharField(
        max_length=100,
        blank=True,
    )

    old_value = models.TextField(
        blank=True,
    )

    new_value = models.TextField(
        blank=True,
    )

    # =========================================================
    # HUMAN-READABLE DESCRIPTION
    # =========================================================

    change_summary = models.TextField(
        blank=True,
    )

    # =========================================================
    # TIMESTAMP
    # =========================================================

    changed_at = models.DateTimeField(
        auto_now_add=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = [
            "-changed_at",
            "-id",
        ]

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return (
            f"{self.chapter.chapter_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by}"
        )


# =========================================================
# CHAPTER VIDEO
# =========================================================

class ChapterVideo(models.Model):

    # =========================================================
    # RELATION
    # =========================================================

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    # =========================================================
    # VIDEO INFORMATION
    # =========================================================

    video_name = models.CharField(
        max_length=255,
    )

    video_description = models.TextField(
        blank=True,
    )

    # =========================================================
    # VIDEO FILE
    # =========================================================
    #
    # Stored in Cloudinary as a video resource.
    #
    # =========================================================

    video_file = CloudinaryField(
        "video",
        resource_type="video",
    )

    # =========================================================
    # AUTOMATIC ORDER
    # =========================================================

    video_order = models.PositiveIntegerField(
        default=1,
    )

    # =========================================================
    # TEACHER TRACKING
    # =========================================================

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="created_videos",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="updated_videos",
    )

    # =========================================================
    # DELETE REQUEST
    # =========================================================

    delete_requested = models.BooleanField(
        default=False,
    )

    delete_requested_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_delete_requests",
    )

    delete_requested_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    delete_reason = models.TextField(
        blank=True,
    )

    DELETE_STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    delete_status = models.CharField(
        max_length=20,
        choices=DELETE_STATUS,
        default="pending",
    )

    # =========================================================
    # SOFT DELETE
    # =========================================================

    is_deleted = models.BooleanField(
        default=False,
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = [
            "video_order",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "chapter",
                    "video_order",
                ]
            ),
        ]

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return self.video_name


# =========================================================
# VIDEO CHANGE / TIMELINE
# =========================================================

class VideoChangeLog(models.Model):

    # =========================================================
    # ACTIONS
    # =========================================================

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("name_changed", "Name Changed"),
        ("description_changed", "Description Changed"),
        ("file_changed", "Video File Changed"),
        ("order_changed", "Order Changed"),
        ("delete_requested", "Delete Requested"),
        ("delete_approved", "Delete Approved"),
        ("delete_rejected", "Delete Rejected"),
        ("restored", "Restored"),
    ]

    # =========================================================
    # RELATION
    # =========================================================

    video = models.ForeignKey(
        ChapterVideo,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    # =========================================================
    # TEACHER WHO PERFORMED ACTION
    # =========================================================

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="video_change_logs",
    )

    # =========================================================
    # ACTION
    # =========================================================

    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
    )

    # =========================================================
    # FIELD CHANGE INFORMATION
    # =========================================================

    field_name = models.CharField(
        max_length=100,
        blank=True,
    )

    old_value = models.TextField(
        blank=True,
    )

    new_value = models.TextField(
        blank=True,
    )

    # =========================================================
    # HUMAN-READABLE DESCRIPTION
    # =========================================================

    change_summary = models.TextField(
        blank=True,
    )

    # =========================================================
    # TIMESTAMP
    # =========================================================

    changed_at = models.DateTimeField(
        auto_now_add=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = [
            "-changed_at",
            "-id",
        ]

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return (
            f"{self.video.video_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by}"
        )