from django.db import models
from django.contrib.auth.models import User
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
    # CREATION / UPDATE TRACKING
    #
    # Teacher is the normal content creator.
    #
    # created_by_admin / updated_by_admin are retained only
    # for historical/admin-management tracking.
    # They do NOT give Admin creation permission.
    # =========================================================

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_chapters",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_created_chapters",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="updated_chapters",
    )

    updated_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_updated_chapters",
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
    #
    # Teacher can request deletion.
    # Admin can approve or reject the request.
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

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    # =========================================================
    # ACTOR TRACKING
    #
    # Exactly one of changed_by / changed_by_admin should
    # normally identify the person responsible for the action.
    # =========================================================

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="chapter_change_logs",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_chapter_change_logs",
    )

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
    )

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

    change_summary = models.TextField(
        blank=True,
    )

    changed_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-changed_at",
            "-id",
        ]

    def __str__(self):
        return (
            f"{self.chapter.chapter_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by or self.changed_by_admin}"
        )


# =========================================================
# CHAPTER VIDEO
# =========================================================

class ChapterVideo(models.Model):

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

    video_file = CloudinaryField(
        "video",
        resource_type="video",
    )

    video_order = models.PositiveIntegerField(
        default=1,
    )

    # =========================================================
    # CREATION / UPDATE TRACKING
    #
    # Teacher normally creates videos.
    # Admin fields are retained for historical tracking and
    # Admin edit tracking.
    # =========================================================

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_videos",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_created_videos",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="updated_videos",
    )

    updated_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_updated_videos",
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

    def __str__(self):
        return self.video_name


# =========================================================
# VIDEO CHANGE / TIMELINE
# =========================================================

class VideoChangeLog(models.Model):

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

    video = models.ForeignKey(
        ChapterVideo,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="video_change_logs",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_video_change_logs",
    )

    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
    )

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

    change_summary = models.TextField(
        blank=True,
    )

    changed_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-changed_at",
            "-id",
        ]

    def __str__(self):
        return (
            f"{self.video.video_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by or self.changed_by_admin}"
        )


# =========================================================
# CHAPTER PDF
# =========================================================

class ChapterPDF(models.Model):

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="pdfs",
    )

    pdf_name = models.CharField(
        max_length=255,
    )

    pdf_description = models.TextField(
        blank=False,
    )

    pdf_file = models.FileField(
        upload_to="course_pdfs/",
    )

    pdf_thumbnail = CloudinaryField(
        "pdf_thumbnail",
        resource_type="image",
        folder="neolearn/pdf_thumbnails",
        blank=True,
        null=True,
    )

    pdf_order = models.PositiveIntegerField(
        default=1,
    )

    # =========================================================
    # CREATION / UPDATE TRACKING
    # =========================================================

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_pdfs",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_created_pdfs",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="updated_pdfs",
    )

    updated_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_updated_pdfs",
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
        related_name="pdf_delete_requests",
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

    class Meta:
        ordering = [
            "pdf_order",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "chapter",
                    "pdf_order",
                ]
            ),
        ]

    def __str__(self):
        return self.pdf_name


# =========================================================
# PDF CHANGE / TIMELINE
# =========================================================

class PDFChangeLog(models.Model):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("name_changed", "Name Changed"),
        ("description_changed", "Description Changed"),
        ("file_changed", "PDF File Changed"),
        ("thumbnail_changed", "Thumbnail Changed"),
        ("order_changed", "Order Changed"),
        ("delete_requested", "Delete Requested"),
        ("delete_approved", "Delete Approved"),
        ("delete_rejected", "Delete Rejected"),
        ("restored", "Restored"),
    ]

    pdf = models.ForeignKey(
        ChapterPDF,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pdf_change_logs",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_pdf_change_logs",
    )

    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
    )

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

    change_summary = models.TextField(
        blank=True,
    )

    changed_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-changed_at",
            "-id",
        ]

    def __str__(self):
        return (
            f"{self.pdf.pdf_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by or self.changed_by_admin}"
        )


# =========================================================
# CHAPTER QUIZ
# =========================================================

class ChapterQuiz(models.Model):

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )

    quiz_name = models.CharField(
        max_length=255,
    )

    quiz_description = models.TextField(
        blank=False,
    )

    # Stored for the future student-attempt stage.
    attempt_limit = models.PositiveIntegerField(
        default=1,
    )

    # =========================================================
    # CREATION / UPDATE TRACKING
    # =========================================================

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_quizzes",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_created_quizzes",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="updated_quizzes",
    )

    updated_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_updated_quizzes",
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
        related_name="quiz_delete_requests",
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

    class Meta:
        ordering = [
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "chapter",
                ]
            ),
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

    question_text = models.TextField(
        blank=False,
    )

    marks = models.PositiveIntegerField(
        default=1,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "id",
        ]

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

    option_text = models.CharField(
        max_length=500,
        blank=False,
    )

    is_correct = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "option_label",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "question",
                    "option_label",
                ],
                name="unique_quiz_question_option_label",
            ),
        ]

    def __str__(self):
        return (
            f"{self.question} - "
            f"{self.option_label}"
        )


# =========================================================
# QUIZ CHANGE / TIMELINE
# =========================================================

class QuizChangeLog(models.Model):

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
        ("delete_approved", "Delete Approved"),
        ("delete_rejected", "Delete Rejected"),
        ("restored", "Restored"),
    ]

    quiz = models.ForeignKey(
        ChapterQuiz,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quiz_change_logs",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_quiz_change_logs",
    )

    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
    )

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

    change_summary = models.TextField(
        blank=True,
    )

    changed_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-changed_at",
            "-id",
        ]

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
# One common audit system for:
#
# - Chapter
# - Video
# - PDF
# - Quiz
#
# This model stores the complete deletion history.
#
# It supports:
#
# 1. Teacher delete request
# 2. Admin approve
# 3. Admin reject
# 4. Admin direct delete
#
# The record remains even after the original content is
# permanently deleted.
#
# =========================================================


class DeletionAudit(models.Model):

    # =====================================================
    # CONTENT TYPE
    # =====================================================

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

    # Original database ID of the content.
    #
    # This is intentionally NOT a ForeignKey because the
    # original content may be permanently deleted.
    #
    object_id = models.PositiveBigIntegerField()

    # =====================================================
    # CONTENT INFORMATION SNAPSHOT
    # =====================================================

    content_name = models.CharField(
        max_length=255,
    )

    batch_name = models.CharField(
        max_length=255,
        blank=True,
    )

    subject_name = models.CharField(
        max_length=255,
        blank=True,
    )

    chapter_name = models.CharField(
        max_length=255,
        blank=True,
    )

    # =====================================================
    # ORIGINAL CREATOR
    # =====================================================
    #
    # Normally content is created by a Teacher.
    #
    # created_by_admin is retained for historical support
    # in case an older Admin-created record exists.
    #
    # =====================================================

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

    # =====================================================
    # TEACHER DELETE REQUEST
    # =====================================================

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

    delete_request_reason = models.TextField(
        blank=True,
    )

    # =====================================================
    # ADMIN DECISION
    # =====================================================
    #
    # This handles:
    #
    # - Approve Teacher request
    # - Reject Teacher request
    #
    # The same fields also record Admin's explanation.
    #
    # =====================================================

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

    admin_response = models.TextField(
        blank=True,
    )

    # =====================================================
    # ADMIN DIRECT DELETE
    # =====================================================
    #
    # Used when Admin directly deletes content without
    # waiting for a Teacher delete request.
    #
    # =====================================================

    deleted_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_audits_direct_deleted",
    )

    admin_delete_reason = models.TextField(
        blank=True,
    )

    # =====================================================
    # DELETION METHOD
    # =====================================================

    DELETION_METHOD_CHOICES = [
        (
            "admin_direct",
            "Admin Direct Delete",
        ),
        (
            "teacher_request_approved",
            "Teacher Request Approved",
        ),
    ]

    deletion_method = models.CharField(
        max_length=40,
        choices=DELETION_METHOD_CHOICES,
        blank=True,
    )

    # =====================================================
    # FINAL STATUS
    # =====================================================
    #
    # pending
    #     Teacher requested deletion, waiting for Admin.
    #
    # approved
    #     Admin approved the Teacher request.
    #
    # rejected
    #     Admin rejected the Teacher request.
    #
    # deleted
    #     Content has been permanently deleted.
    #
    # =====================================================

    STATUS_CHOICES = [
        (
            "pending",
            "Pending",
        ),
        (
            "approved",
            "Approved",
        ),
        (
            "rejected",
            "Rejected",
        ),
        (
            "deleted",
            "Permanently Deleted",
        ),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    # =====================================================
    # FINAL DELETION TIME
    # =====================================================

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # =====================================================
    # CONTENT SNAPSHOT
    # =====================================================
    #
    # This is extremely important.
    #
    # Before permanent deletion, the view will save useful
    # information here.
    #
    # Example:
    #
    # {
    #     "content_name": "Motion Introduction",
    #     "description": "...",
    #     "order": 1,
    #     "created_by": "Teacher Name",
    #     ...
    # }
    #
    # Therefore the audit remains useful even after the
    # original database object no longer exists.
    #
    # =====================================================

    snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    # =====================================================
    # AUDIT CREATED TIME
    # =====================================================
    #
    # Different from deleted_at.
    #
    # deleted_at = actual permanent deletion time.
    #
    # created_at = when this audit record was created.
    #
    # For a pending request, deleted_at remains NULL.
    #
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:

        ordering = [
            "-created_at",
            "-id",
        ]

        indexes = [

            models.Index(
                fields=[
                    "content_type",
                    "object_id",
                ]
            ),

            models.Index(
                fields=[
                    "status",
                    "created_at",
                ]
            ),

            models.Index(
                fields=[
                    "deletion_method",
                    "created_at",
                ]
            ),

            models.Index(
                fields=[
                    "admin_decision",
                    "created_at",
                ]
            ),
        ]

    # =====================================================
    # STRING REPRESENTATION
    # =====================================================

    def __str__(self):

        return (
            f"{self.get_content_type_display()} - "
            f"{self.content_name} - "
            f"{self.get_status_display()}"
        )