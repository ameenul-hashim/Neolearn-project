
from django.conf import settings
from django.db import models
from django.db.models import Q

from django.contrib.auth.models import User

from admins.models import Batch
from courses.models import ChapterQuiz, QuizQuestion


# ============================================================
# STUDENT PROFILE
# ============================================================

class StudentProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
    )

    neo_student_id = models.CharField(
        max_length=15,
        unique=True,
        editable=False,
        db_index=True,
    )

    profile_image = models.URLField(
        blank=True,
        null=True,
    )

    cloudinary_public_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    bio = models.TextField(
        blank=True,
    )

    phone = models.CharField(
        max_length=10,
        blank=True,
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.user.username


# ============================================================
# STUDENT WISHLIST
# ============================================================

class StudentWishlist(models.Model):

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="wishlists",
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "student_wishlist"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["student", "batch"],
                name="unique_student_batch_wishlist",
            ),
        ]

    def __str__(self):
        return (
            f"{self.student.username} "
            f"❤️ {self.batch.batch_name}"
        )


# ============================================================
# STUDENT CART
# ============================================================

class Cart(models.Model):

    student = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "student_cart"

    def __str__(self):
        return f"Cart - {self.student.username}"

    @property
    def item_count(self):
        return self.items.count()

    @property
    def subtotal(self):
        return sum(
            item.batch.final_price
            for item in self.items.select_related("batch")
        )


# ============================================================
# CART ITEM
# ============================================================

class CartItem(models.Model):

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    added_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "student_cart_item"
        ordering = ["-added_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["cart", "batch"],
                name="unique_cart_batch",
            ),
        ]

    def __str__(self):
        return (
            f"{self.cart.student.username} - "
            f"{self.batch.batch_name}"
        )


# ============================================================
# CART COUPON
# ============================================================

class CartCoupon(models.Model):

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="cart_coupons",
    )

    coupon = models.ForeignKey(
        "admins.Coupon",
        on_delete=models.CASCADE,
        related_name="cart_applications",
    )

    # Batch-specific coupons identify the exact batch.
    # Checkout-level coupons can leave batch empty.
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="cart_coupon_applications",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "student_cart_coupon"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["cart", "coupon"],
                name="unique_cart_coupon",
            ),
            models.UniqueConstraint(
                fields=["cart", "batch"],
                condition=Q(batch__isnull=False),
                name="unique_cart_coupon_batch",
            ),
        ]

    def __str__(self):
        return (
            f"{self.cart.student.username} - "
            f"{self.coupon.code}"
        )


# ============================================================
# QUIZ ATTEMPT
# ============================================================

class QuizAttempt(models.Model):

    class Status(models.TextChoices):

        IN_PROGRESS = (
            "in_progress",
            "In Progress",
        )

        SUBMITTED = (
            "submitted",
            "Submitted",
        )

        TIMED_OUT = (
            "timed_out",
            "Timed Out",
        )

    # --------------------------------------------------------
    # STUDENT AND QUIZ
    # --------------------------------------------------------

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )

    # Preserve the attempt if a quiz is deleted.
    # The original quiz title is stored separately.
    quiz = models.ForeignKey(
        ChapterQuiz,
        on_delete=models.SET_NULL,
        related_name="student_attempts",
        null=True,
        blank=True,
    )

    quiz_title_snapshot = models.CharField(
        max_length=100,
    )

    # --------------------------------------------------------
    # ATTEMPT NUMBER AND STATUS
    # --------------------------------------------------------

    attempt_number = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True,
    )

    # --------------------------------------------------------
    # QUIZ SETTINGS SNAPSHOT
    # --------------------------------------------------------

    answering_time_minutes_snapshot = (
        models.PositiveIntegerField()
    )

    maximum_attempts_snapshot = (
        models.PositiveIntegerField()
    )

    marks_per_question_snapshot = (
        models.PositiveIntegerField()
    )

    maximum_marks = models.PositiveIntegerField(
        default=0,
    )

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    expires_at = models.DateTimeField()

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    score = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # --------------------------------------------------------
    # DATABASE RULES
    # --------------------------------------------------------

    class Meta:

        db_table = "student_quiz_attempt"

        ordering = [
            "-started_at",
            "-id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "quiz",
                    "attempt_number",
                ],
                condition=Q(quiz__isnull=False),
                name="unique_student_quiz_attempt_number",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "student",
                    "status",
                ],
                name="stu_quiz_attempt_status_idx",
            ),
            models.Index(
                fields=[
                    "quiz",
                    "status",
                ],
                name="quiz_attempt_status_idx",
            ),
        ]

    def __str__(self):

        return (
            f"{self.student.username} - "
            f"{self.quiz_title_snapshot} - "
            f"Attempt {self.attempt_number}"
        )


# ============================================================
# QUIZ ATTEMPT ANSWER
# ============================================================

class QuizAttemptAnswer(models.Model):

    # --------------------------------------------------------
    # ATTEMPT
    # --------------------------------------------------------

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )

    # Retain answer history if the original question is deleted.
    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.SET_NULL,
        related_name="student_attempt_answers",
        null=True,
        blank=True,
    )

    # Original question ID stored as a string.
    # This remains available if the question is deleted.
    question_snapshot_key = models.CharField(
        max_length=64,
    )

    # --------------------------------------------------------
    # QUESTION SNAPSHOT
    # --------------------------------------------------------

    question_text_snapshot = models.TextField()

    # Example:
    # [
    #     {"label": "A", "text": "Option one"},
    #     {"label": "B", "text": "Option two"},
    #     {"label": "C", "text": "Option three"},
    #     {"label": "D", "text": "Option four"}
    # ]
    #
    # The options are captured when the attempt begins.
    options_snapshot = models.JSONField(
        default=list,
    )

    # Stored privately for server-side scoring.
    # Never expose this field to the student during the quiz.
    correct_option_label_snapshot = models.CharField(
        max_length=1,
    )

    # --------------------------------------------------------
    # STUDENT ANSWER
    # --------------------------------------------------------

    selected_option_label = models.CharField(
        max_length=1,
        blank=True,
        default="",
    )

    selected_option_text_snapshot = models.TextField(
        blank=True,
        default="",
    )

    answered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # --------------------------------------------------------
    # MARKING
    # --------------------------------------------------------

    is_correct = models.BooleanField(
        null=True,
        blank=True,
    )

    marks_awarded = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # --------------------------------------------------------
    # DATABASE RULES
    # --------------------------------------------------------

    class Meta:

        db_table = "student_quiz_attempt_answer"

        ordering = [
            "id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "attempt",
                    "question_snapshot_key",
                ],
                name="unique_attempt_question_snapshot",
            ),
        ]

    def __str__(self):

        return (
            f"Attempt {self.attempt_id} - "
            f"Question {self.question_snapshot_key}"
        )
