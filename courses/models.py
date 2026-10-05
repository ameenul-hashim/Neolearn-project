from django.db import models
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField

from admins.models import Batch, Subject
from teachers.models import Teacher


# ============================================================
# COMMON STATUS
# ============================================================

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
]


# ============================================================
# COURSE CHAPTER
# ============================================================

class CourseChapter(models.Model):

    STATUS_CHOICES = STATUS_CHOICES

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

    chapter_name = models.CharField(
        max_length=100,
    )

    chapter_description = models.CharField(
        max_length=250,
    )

    chapter_order = models.PositiveIntegerField(
        default=1,
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_chapters_created_as_admin",
    )

    created_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_chapters_created_as_teacher",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "chapter_order",
            "pk",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "batch",
                    "subject",
                    "chapter_name",
                ],
                name="unique_chapter_name_per_batch_subject",
            ),
        ]

    def __str__(self):
        return self.chapter_name


# ============================================================
# CHAPTER CHANGE / TIMELINE
# ============================================================

class ChapterChangeLog(models.Model):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("order_changed", "Order Changed"),
    ]

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="chapter_changes_as_admin",
    )

    changed_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="chapter_changes_as_teacher",
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
            f"{self.get_action_display()}"
        )


# ============================================================
# CHAPTER VIDEO
# ============================================================

class ChapterVideo(models.Model):

    STATUS_CHOICES = STATUS_CHOICES

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    video_name = models.CharField(
        max_length=100,
    )

    video_description = models.CharField(
        max_length=250,
    )

    video_file = CloudinaryField(
        "video",
        resource_type="video",
    )

    video_thumbnail = CloudinaryField(
        "video_thumbnail",
        resource_type="image",
        folder="neolearn/video_thumbnails",
        blank=True,
        null=True,
    )

    video_order = models.PositiveIntegerField(
        default=1,
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_videos_created_as_admin",
    )

    created_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_videos_created_as_teacher",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "video_order",
            "pk",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "chapter",
                    "video_name",
                ],
                name="unique_video_name_per_chapter",
            ),
        ]

    def __str__(self):
        return self.video_name


# ============================================================
# VIDEO CHANGE / TIMELINE
# ============================================================

class VideoChangeLog(models.Model):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("order_changed", "Order Changed"),
    ]

    video = models.ForeignKey(
        ChapterVideo,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="video_changes_as_admin",
    )

    changed_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="video_changes_as_teacher",
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

        indexes = [
            models.Index(
                fields=[
                    "video",
                    "changed_at",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.video.video_name} - "
            f"{self.get_action_display()}"
        )


# ============================================================
# CHAPTER PDF
# ============================================================

class ChapterPDF(models.Model):

    STATUS_CHOICES = STATUS_CHOICES

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="pdfs",
    )

    pdf_name = models.CharField(
        max_length=100,
    )

    pdf_description = models.CharField(
        max_length=250,
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

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_pdfs_created_as_admin",
    )

    created_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_pdfs_created_as_teacher",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "pdf_order",
            "pk",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "chapter",
                    "pdf_name",
                ],
                name="unique_pdf_name_per_chapter",
            ),
        ]

    def __str__(self):
        return self.pdf_name


# ============================================================
# PDF CHANGE / TIMELINE
# ============================================================

class PDFChangeLog(models.Model):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("order_changed", "Order Changed"),
    ]

    pdf = models.ForeignKey(
        ChapterPDF,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pdf_changes_as_admin",
    )

    changed_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pdf_changes_as_teacher",
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

        indexes = [
            models.Index(
                fields=[
                    "pdf",
                    "changed_at",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.pdf.pdf_name} - "
            f"{self.get_action_display()}"
        )


# ============================================================
# CHAPTER QUIZ
# ============================================================

class ChapterQuiz(models.Model):

    STATUS_CHOICES = STATUS_CHOICES

    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )

    quiz_name = models.CharField(
        max_length=100,
    )

    quiz_description = models.CharField(
        max_length=250,
    )

    quiz_order = models.PositiveIntegerField(
        default=1,
    )

    maximum_attempts = models.PositiveIntegerField(
        default=1,
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="draft",
    )

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_quizzes_created_as_admin",
    )

    created_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="course_quizzes_created_as_teacher",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "quiz_order",
            "pk",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "chapter",
                    "quiz_name",
                ],
                name="unique_quiz_name_per_chapter",
            ),
        ]

    def __str__(self):
        return self.quiz_name


# ============================================================
# QUIZ QUESTION
# ============================================================

class QuizQuestion(models.Model):

    quiz = models.ForeignKey(
        ChapterQuiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    question_text = models.TextField()

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
            "pk",
        ]

    def __str__(self):
        return self.question_text[:80]


# ============================================================
# QUIZ OPTION
# ============================================================

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
        max_length=250,
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


# ============================================================
# QUIZ CHANGE / TIMELINE
# ============================================================

class QuizChangeLog(models.Model):

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("order_changed", "Order Changed"),
        ("question_added", "Question Added"),
        ("question_updated", "Question Updated"),
        ("question_deleted", "Question Deleted"),
        ("option_added", "Option Added"),
        ("option_updated", "Option Updated"),
        ("option_deleted", "Option Deleted"),
        ("correct_answer_changed", "Correct Answer Changed"),
    ]

    quiz = models.ForeignKey(
        ChapterQuiz,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    changed_by_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quiz_changes_as_admin",
    )

    changed_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quiz_changes_as_teacher",
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

        indexes = [
            models.Index(
                fields=[
                    "quiz",
                    "changed_at",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.quiz.quiz_name} - "
            f"{self.get_action_display()}"
        )


# ============================================================
# COMMON DELETION AUDIT
# ============================================================

class DeletionAudit(models.Model):

    """
    Common read-only deletion history for:

        Chapter
        Video
        PDF
        Quiz

    This model does not use a ForeignKey to the deleted content
    because the original object may no longer exist.
    """

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

    object_id = models.PositiveBigIntegerField()

    content_name = models.CharField(
        max_length=100,
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
        max_length=100,
        blank=True,
    )

    # ========================================================
    # ORIGINAL CREATOR
    # ========================================================

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_deletion_audits_created_as_admin",
    )

    created_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_deletion_audits_created_as_teacher",
    )

    original_created_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # ========================================================
    # TEACHER DELETE REQUEST
    # ========================================================

    requested_by_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_deletion_requests",
    )

    requested_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    request_reason = models.TextField(
        blank=True,
    )

    # ========================================================
    # ADMIN DECISION
    # ========================================================

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
        related_name="content_deletion_decisions",
    )

    decision_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    admin_response = models.TextField(
        blank=True,
    )

    # ========================================================
    # DIRECT ADMIN DELETE
    # ========================================================

    deleted_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_direct_deletions",
    )

    admin_delete_reason = models.TextField(
        blank=True,
    )

    # ========================================================
    # DELETE METHOD
    # ========================================================

    DELETION_METHOD_CHOICES = [
        ("admin_direct", "Admin Direct Delete"),
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

    # ========================================================
    # AUDIT STATUS
    # ========================================================

    AUDIT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("deleted", "Deleted"),
    ]

    status = models.CharField(
        max_length=20,
        choices=AUDIT_STATUS_CHOICES,
        default="pending",
    )

    # ========================================================
    # ACTUAL DELETION TIME
    # ========================================================

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # ========================================================
    # CONTENT SNAPSHOT
    # ========================================================

    snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    # ========================================================
    # AUDIT CREATED TIME
    # ========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    # ========================================================
    # META
    # ========================================================

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

    def __str__(self):
        return (
            f"{self.get_content_type_display()} - "
            f"{self.content_name} - "
            f"{self.get_status_display()}"
        )