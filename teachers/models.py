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


# =========================================================
# CHAPTER PDF
# =========================================================

class ChapterPDF(models.Model):

    # =========================================================
    # RELATION
    # =========================================================

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="pdfs",
    )

    # =========================================================
    # PDF INFORMATION
    # =========================================================

    pdf_name = models.CharField(
        max_length=255,
    )

    pdf_description = models.TextField(
        blank=False,
    )

    # =========================================================
    # PDF FILE
    #
    # Keep this as a normal FileField for now.
    # The PDF view will enforce PDF-only uploads.
    # =========================================================

    pdf_file = models.FileField(
        upload_to="course_pdfs/",
    )

    # =========================================================
    # PDF THUMBNAIL
    #
    # Optional custom 16:9 image.
    # Course Builder will use the NeoLearner default thumbnail
    # when this field is empty.
    # =========================================================

    pdf_thumbnail = CloudinaryField(
        "pdf_thumbnail",
        resource_type="image",
        folder="neolearn/pdf_thumbnails",
        blank=True,
        null=True,
    )

    # =========================================================
    # AUTOMATIC ORDER
    # =========================================================

    pdf_order = models.PositiveIntegerField(
        default=1,
    )

    # =========================================================
    # TEACHER TRACKING
    # =========================================================

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="created_pdfs",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="updated_pdfs",
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

    # =========================================================
    # META
    # =========================================================

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

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return self.pdf_name


# =========================================================
# PDF CHANGE / TIMELINE
# =========================================================

class PDFChangeLog(models.Model):

    # =========================================================
    # ACTIONS
    # =========================================================

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

    # =========================================================
    # RELATION
    # =========================================================

    pdf = models.ForeignKey(
        ChapterPDF,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    # =========================================================
    # TEACHER WHO PERFORMED ACTION
    # =========================================================

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="pdf_change_logs",
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
            f"{self.pdf.pdf_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by}"
        )

# =========================================================
# CHAPTER QUIZ
#
# Current scope:
# - Quiz basic information
# - Attempt limit stored for later student-attempt stage
# - Teacher tracking
# - Delete request
# - Soft delete
# - No quiz order
# - No question order
# - No student attempt/result models yet
# =========================================================


class ChapterQuiz(models.Model):

    # =========================================================
    # RELATION
    # =========================================================

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )

    # =========================================================
    # QUIZ INFORMATION
    # =========================================================

    quiz_name = models.CharField(
        max_length=255,
    )

    quiz_description = models.TextField(
        blank=False,
    )

    # =========================================================
    # ATTEMPT LIMIT
    #
    # Stored now for the future student-attempt stage.
    # The actual attempt enforcement is NOT implemented now.
    # =========================================================

    attempt_limit = models.PositiveIntegerField(
        default=1,
    )

    # =========================================================
    # TEACHER TRACKING
    # =========================================================

    created_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="created_quizzes",
    )

    updated_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="updated_quizzes",
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

    # =========================================================
    # META
    # =========================================================

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

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return self.quiz_name


# =========================================================
# QUIZ QUESTION
#
# No question-order field.
# =========================================================


class QuizQuestion(models.Model):

    # =========================================================
    # RELATION
    # =========================================================

    quiz = models.ForeignKey(
        ChapterQuiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    # =========================================================
    # QUESTION
    # =========================================================

    question_text = models.TextField(
        blank=False,
    )

    # =========================================================
    # MARKS
    # =========================================================

    marks = models.PositiveIntegerField(
        default=1,
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
            "id",
        ]

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return self.question_text[:80]


# =========================================================
# QUIZ OPTION
#
# Each question has exactly four options:
# A, B, C, D.
#
# The custom views will enforce:
# - all four options entered
# - exactly one correct option
# =========================================================


class QuizOption(models.Model):

    OPTION_LABELS = [
        ("A", "Option A"),
        ("B", "Option B"),
        ("C", "Option C"),
        ("D", "Option D"),
    ]

    # =========================================================
    # RELATION
    # =========================================================

    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )

    # =========================================================
    # OPTION LABEL
    # =========================================================

    option_label = models.CharField(
        max_length=1,
        choices=OPTION_LABELS,
    )

    # =========================================================
    # OPTION TEXT
    # =========================================================

    option_text = models.CharField(
        max_length=500,
        blank=False,
    )

    # =========================================================
    # CORRECT ANSWER
    # =========================================================

    is_correct = models.BooleanField(
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
    # META / CONSTRAINTS
    # =========================================================

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

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return (
            f"{self.question} - "
            f"{self.option_label}"
        )


# =========================================================
# QUIZ CHANGE / TIMELINE
#
# This is for the quiz itself and its questions/options.
# Student attempt history is intentionally NOT included yet.
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

    # =========================================================
    # RELATION
    # =========================================================

    quiz = models.ForeignKey(
        ChapterQuiz,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    # =========================================================
    # TEACHER WHO PERFORMED ACTION
    # =========================================================

    changed_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="quiz_change_logs",
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
            f"{self.quiz.quiz_name} - "
            f"{self.get_action_display()} - "
            f"{self.changed_by}"
        )