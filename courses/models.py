# =========================================================
# NEOLEARNER — SHARED COURSE BUILDER MODELS
#
# Used by BOTH Admin panel and Teacher panel.
#
# - Chapters, Videos, PDFs, Quizzes
# - Change / timeline logs
# - Deletion audit (shared, read-only)
#
# Content creation logic is shared. Delete actions are
# separated by role in their respective views
# (teachers/views.py and admins/views.py).
# =========================================================

from django.db import models
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField

from admins.models import Batch, Subject
from teachers.models import Teacher


# =========================================================
# ABSTRACT BASE — SHARED CREATION / UPDATE TRACKING
# =========================================================

class ContentTracking(models.Model):
    """
    Common creation / update tracking fields for every
    piece of Course Builder content.

    Inherited by:
        CourseChapter
        ChapterVideo
        ChapterPDF
        ChapterQuiz
    """

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_created",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_admin_created",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
    )

    updated_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_admin_updated",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# =========================================================
# ABSTRACT BASE — SHARED DELETE-REQUEST FIELDS
# =========================================================

class SoftDeleteFields(models.Model):
    """
    Common teacher delete-request fields shared by all
    Course Builder content.

    Teacher requests delete → Admin approves / rejects.
    Actual deletion is handled in views / services.
    """

    DELETE_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("withdrawn", "Withdrawn"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    delete_requested = models.BooleanField(default=False)

    delete_requested_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_delete_requests",
    )

    delete_requested_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    delete_reason = models.TextField(blank=True)

    delete_status = models.CharField(
        max_length=20,
        choices=DELETE_STATUS_CHOICES,
        default="pending",
    )

    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


# =========================================================
# ABSTRACT BASE — SHARED CHANGE-LOG FIELDS
# =========================================================

class BaseChangeLog(models.Model):
    """
    Common timeline fields for all Course Builder change logs.

    Each child model:
        - overrides ACTION_CHOICES
        - declares its own FK to its content type
    """

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_changed",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_admin_changed",
    )

    field_name = models.CharField(max_length=100, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    change_summary = models.TextField(blank=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-changed_at", "-id"]


# =========================================================
# COURSE CHAPTER
# =========================================================

class CourseChapter(ContentTracking, SoftDeleteFields):

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
    ]

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

    chapter_name = models.CharField(max_length=255)
    chapter_description = models.CharField(max_length=255, blank=True)

    chapter_order = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft",
    )

    class Meta:
        ordering = ["chapter_order", "pk"]

    def __str__(self):
        return self.chapter_name


# =========================================================
# CHAPTER CHANGE / TIMELINE
# =========================================================

class ChapterChangeLog(BaseChangeLog):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("order_changed", "Order Changed"),
        ("status_changed", "Status Changed"),
        ("delete_requested", "Delete Requested"),
        ("delete_withdrawn", "Delete Withdrawn"),
        ("delete_approved", "Delete Approved"),
        ("delete_rejected", "Delete Rejected"),
        ("restored", "Restored"),
    ]

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
    )

    def __str__(self):
        return (
            f"{self.chapter.chapter_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by or self.changed_by_admin}"
        )


# =========================================================
# CHAPTER VIDEO
# =========================================================

class ChapterVideo(ContentTracking, SoftDeleteFields):

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    video_name = models.CharField(max_length=255)
    video_description = models.TextField(blank=True)

    video_file = CloudinaryField(
        "video",
        resource_type="video",
    )

    video_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["video_order", "pk"]
        indexes = [
            models.Index(fields=["chapter", "video_order"]),
        ]

    def __str__(self):
        return self.video_name


# =========================================================
# VIDEO CHANGE / TIMELINE
# =========================================================

class VideoChangeLog(BaseChangeLog):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("name_changed", "Name Changed"),
        ("description_changed", "Description Changed"),
        ("file_changed", "Video File Changed"),
        ("order_changed", "Order Changed"),
        ("delete_requested", "Delete Requested"),
        ("delete_withdrawn", "Delete Withdrawn"),
        ("delete_approved", "Delete Approved"),
        ("delete_rejected", "Delete Rejected"),
        ("restored", "Restored"),
    ]

    video = models.ForeignKey(
        ChapterVideo,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
    )

    def __str__(self):
        return (
            f"{self.video.video_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by or self.changed_by_admin}"
        )


# =========================================================
# CHAPTER PDF
# =========================================================

class ChapterPDF(ContentTracking, SoftDeleteFields):

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="pdfs",
    )

    pdf_name = models.CharField(max_length=255)
    pdf_description = models.TextField(blank=False)

    pdf_file = models.FileField(upload_to="course_pdfs/")

    pdf_thumbnail = CloudinaryField(
        "pdf_thumbnail",
        resource_type="image",
        folder="neolearn/pdf_thumbnails",
        blank=True,
        null=True,
    )

    pdf_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pdf_order", "pk"]
        indexes = [
            models.Index(fields=["chapter", "pdf_order"]),
        ]

    def __str__(self):
        return self.pdf_name


# =========================================================
# PDF CHANGE / TIMELINE
# =========================================================

class PDFChangeLog(BaseChangeLog):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("name_changed", "Name Changed"),
        ("description_changed", "Description Changed"),
        ("file_changed", "PDF File Changed"),
        ("thumbnail_changed", "Thumbnail Changed"),
        ("order_changed", "Order Changed"),
        ("delete_requested", "Delete Requested"),
        ("delete_withdrawn", "Delete Withdrawn"),
        ("delete_approved", "Delete Approved"),
        ("delete_rejected", "Delete Rejected"),
        ("restored", "Restored"),
    ]

    pdf = models.ForeignKey(
        ChapterPDF,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
    )

    def __str__(self):
        return (
            f"{self.pdf.pdf_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by or self.changed_by_admin}"
        )


# =========================================================
# CHAPTER QUIZ
# =========================================================

class ChapterQuiz(ContentTracking, SoftDeleteFields):

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )

    quiz_name = models.CharField(max_length=255)
    quiz_description = models.TextField(blank=False)

    # Stored for future student-attempt stage.
    attempt_limit = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pk"]
        indexes = [
            models.Index(fields=["chapter"]),
        ]

    def __str__(self):
        return self.quiz_name


# =========================================================
# QUIZ QUESTION
# =========================================================

class QuizQuestion(models.Model):

    quiz = models.ForeignKey(
        ChapterQuiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    question_text = models.TextField(blank=False)
    marks = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.question_text[:80]


# =========================================================
# QUIZ OPTION
# =========================================================

class QuizOption(models.Model):

    OPTION_LABELS = [
        ("A", "Option A"),
        ("B", "Option B"),
        ("C", "Option C"),
        ("D", "Option D"),
    ]

    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )

    option_label = models.CharField(
        max_length=1,
        choices=OPTION_LABELS,
    )

    option_text = models.CharField(max_length=500, blank=False)
    is_correct = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["option_label"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "option_label"],
                name="unique_quiz_question_option_label",
            ),
        ]

    def __str__(self):
        return f"{self.question} - {self.option_label}"


# =========================================================
# QUIZ CHANGE / TIMELINE
# =========================================================

class QuizChangeLog(BaseChangeLog):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("name_changed", "Name Changed"),
        ("description_changed", "Description Changed"),
        ("attempt_limit_changed", "Attempt Limit Changed"),
        ("question_added", "Question Added"),
        ("question_updated", "Question Updated"),
        ("question_deleted", "Question Deleted"),
        ("option_changed", "Option Changed"),
        ("correct_answer_changed", "Correct Answer Changed"),
        ("delete_requested", "Delete Requested"),
        ("delete_withdrawn", "Delete Withdrawn"),
        ("delete_approved", "Delete Approved"),
        ("delete_rejected", "Delete Rejected"),
        ("restored", "Restored"),
    ]

    quiz = models.ForeignKey(
        ChapterQuiz,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
    )

    def __str__(self):
        return (
            f"{self.quiz.quiz_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by or self.changed_by_admin}"
        )


# =========================================================
# COMMON CONTENT DELETION AUDIT
# =========================================================
#
# Shared, read-only audit for the whole Course Builder.
#
# Records every delete action:
#
#   1. Teacher delete request        → status = pending
#   2. Teacher withdraw              → status = withdrawn
#   3. Admin approve                 → status = approved
#   4. Admin reject                  → status = rejected
#   5. Admin direct delete           → status = deleted
#
# The record remains even after the original content has
# been permanently deleted.
#
# Read-only across both panels. Write actions are handled
# in teachers/views.py and admins/views.py.
# =========================================================


class DeletionAudit(models.Model):

    # -----------------------------------------------------
    # CONTENT TYPE
    # -----------------------------------------------------

    CONTENT_TYPE_CHOICES = [
        ("chapter", "Chapter"),
        ("video", "Video"),
        ("pdf", "PDF"),
        ("quiz", "Quiz"),
    ]

    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
    )

    # Original DB id — NOT a FK, because content may be
    # permanently deleted.
    object_id = models.PositiveBigIntegerField()

    # -----------------------------------------------------
    # CONTENT SNAPSHOT
    # -----------------------------------------------------

    content_name = models.CharField(max_length=255)
    batch_name = models.CharField(max_length=255, blank=True)
    subject_name = models.CharField(max_length=255, blank=True)
    chapter_name = models.CharField(max_length=255, blank=True)

    # -----------------------------------------------------
    # ORIGINAL CREATOR
    # -----------------------------------------------------

    created_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_audits_created",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_audits_created",
    )

    created_at_original = models.DateTimeField(
        null=True,
        blank=True,
    )

    # -----------------------------------------------------
    # TEACHER DELETE REQUEST
    # -----------------------------------------------------

    delete_requested_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_audits_requested",
    )

    delete_requested_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    delete_request_reason = models.TextField(blank=True)

    # -----------------------------------------------------
    # TEACHER WITHDRAW
    # -----------------------------------------------------

    withdrawn_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_audits_withdrawn",
    )

    withdrawn_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # -----------------------------------------------------
    # ADMIN DECISION (approve / reject)
    # -----------------------------------------------------

    ADMIN_DECISION_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    admin_decision = models.CharField(
        max_length=20,
        choices=ADMIN_DECISION_CHOICES,
        blank=True,
    )

    decision_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_audits_decisions",
    )

    decision_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    admin_response = models.TextField(blank=True)

    # -----------------------------------------------------
    # ADMIN DIRECT DELETE
    # -----------------------------------------------------

    deleted_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_audits_direct_deleted",
    )

    admin_delete_reason = models.TextField(blank=True)

    # -----------------------------------------------------
    # DELETION METHOD
    # -----------------------------------------------------

    DELETION_METHOD_CHOICES = [
        ("admin_direct", "Admin Direct Delete"),
        ("teacher_request_approved", "Teacher Request Approved"),
    ]

    deletion_method = models.CharField(
        max_length=40,
        choices=DELETION_METHOD_CHOICES,
        blank=True,
    )

    # -----------------------------------------------------
    # FINAL STATUS
    # -----------------------------------------------------

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("withdrawn", "Withdrawn"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("deleted", "Permanently Deleted"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # -----------------------------------------------------
    # SNAPSHOT OF CONTENT BEFORE DELETE
    # -----------------------------------------------------

    snapshot = models.JSONField(default=dict, blank=True)

    # -----------------------------------------------------
    # AUDIT CREATION TIME
    # -----------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)

    # -----------------------------------------------------
    # META
    # -----------------------------------------------------

    class Meta:
        ordering = ["-created_at", "-id"]

        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["deletion_method", "created_at"]),
            models.Index(fields=["admin_decision", "created_at"]),
            models.Index(fields=["subject_name", "created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.get_content_type_display()} - "
            f"{self.content_name} - "
            f"{self.get_status_display()}"
        )