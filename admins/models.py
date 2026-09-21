from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from cloudinary.models import CloudinaryField

class Batch(models.Model):

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    DISCOUNT_CHOICES = [
        ("none", "No Discount"),
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    ]

    PUBLISH_TYPE_CHOICES = [
        ("immediate", "Publish Immediately"),
        ("scheduled", "Schedule Publish"),
    ]

    # --------------------------------------------------
    # Basic Information
    # --------------------------------------------------

    batch_name = models.CharField(
        max_length=200,
        unique=True,
    )

    batch_description = models.TextField()

    batch_thumbnail = CloudinaryField(
        "batch_thumbnail",
        blank=True,
        null=True,
    )

    # --------------------------------------------------
    # Marketplace Pricing
    # --------------------------------------------------

    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_CHOICES,
        default="none",
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    offer_start_date = models.DateTimeField(
        blank=True,
        null=True,
    )

    offer_end_date = models.DateTimeField(
        blank=True,
        null=True,
    )
    
    marketplace_visible = models.BooleanField(default=True)
    
    featured = models.BooleanField(default=False)
    
    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    
    # --------------------------------------------------
    # Publishing
    # --------------------------------------------------

    batch_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    publish_type = models.CharField(
        max_length=20,
        choices=PUBLISH_TYPE_CHOICES,
        default="immediate",
    )

    publish_datetime = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Required only for scheduled publishing.",
    )

    published_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Actual time when the batch becomes live.",
    )

    admission_close_datetime = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Leave blank to keep admissions open.",
    )

    course_end_date = models.DateField(
        blank=True,
        null=True,
    )

    # --------------------------------------------------
    # Timestamps
    # --------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Batch"
        verbose_name_plural = "Batches"

        indexes = [
            models.Index(fields=["batch_status"]),
            models.Index(fields=["publish_datetime"]),
            models.Index(fields=["admission_close_datetime"]),
        ]

    def __str__(self):
        return self.batch_name

    # ==================================================
    # Helper Properties
    # ==================================================

    @property
    def marketplace_status(self):
        """
        Returns:
        hidden
        coming_soon
        buy_now
        admissions_closed
        """

        now = timezone.now()

        if self.batch_status == "draft":
            return "hidden"

        if self.batch_status == "archived":
            return "admissions_closed"

        if (
            self.publish_type == "scheduled"
            and self.publish_datetime
            and now < self.publish_datetime
        ):
            return "coming_soon"

        if (
            self.admission_close_datetime
            and now >= self.admission_close_datetime
        ):
            return "admissions_closed"

        return "buy_now"

    @property
    def is_new(self):
        """
        Show NEW badge for first 30 days after publishing.
        """

        if not self.published_at:
            return False

        return (
            timezone.now()
            <= self.published_at + timedelta(days=30)
        )

    @property
    def is_offer_active(self):
        """
        Returns True if offer is currently active.
        """

        now = timezone.now()

        if self.discount_type == "none":
            return False

        if self.offer_start_date and now < self.offer_start_date:
            return False

        if self.offer_end_date and now > self.offer_end_date:
            return False

        return True

    # ==================================================
    # Validation
    # ==================================================

    def clean(self):

        if (
            self.offer_start_date
            and self.offer_end_date
            and self.offer_end_date <= self.offer_start_date
        ):
            raise ValidationError(
                "Offer end date must be after offer start date."
            )

        if (
            self.discount_type == "percentage"
            and self.discount_value > 100
        ):
            raise ValidationError(
                "Percentage discount cannot exceed 100."
            )

        if (
            self.discount_type == "fixed"
            and self.discount_value > self.original_price
        ):
            raise ValidationError(
                "Discount cannot exceed original price."
            )

        if (
            self.publish_type == "scheduled"
            and not self.publish_datetime
        ):
            raise ValidationError(
                "Publish date and time is required for scheduled publishing."
            )

        if (
            self.publish_datetime
            and self.admission_close_datetime
            and self.admission_close_datetime <= self.publish_datetime
        ):
            raise ValidationError(
                "Admission close must be after publish date."
            )

        if (
            self.course_end_date
            and self.admission_close_datetime
            and self.course_end_date <= self.admission_close_datetime.date()
        ):
            raise ValidationError(
                "Course end date must be after admission close date."
            )

    # ==================================================
    # Save
    # ==================================================

    def save(self, *args, **kwargs):

        # -----------------------------------------
        # Calculate Final Price
        # -----------------------------------------

        if self.discount_type == "none":

            self.final_price = self.original_price

        elif self.discount_type == "percentage":

            discount_amount = (
                self.original_price *
                (self.discount_value / Decimal("100"))
            )

            self.final_price = max(
                Decimal("0"),
                self.original_price - discount_amount
            )

        elif self.discount_type == "fixed":

            self.final_price = max(
                Decimal("0"),
                self.original_price - self.discount_value
            )

        else:

            self.final_price = self.original_price

        # -----------------------------------------
        # Published Time
        # -----------------------------------------

        if (
            self.batch_status == "published"
            and self.publish_type == "immediate"
            and not self.published_at
        ):
            self.published_at = timezone.now()

        # -----------------------------------------
        # Save
        # -----------------------------------------
        # -----------------------------------------
        # Marketplace Visibility
        # -----------------------------------------

        if self.batch_status == "draft":
            self.marketplace_visible = False
        else:
            self.marketplace_visible = True

        super().save(*args, **kwargs)
    


class Subject(models.Model):

    STATUS_CHOICES = [('draft', 'Draft'),('published', 'Published'),('archived', 'Archived')]
    batch = models.ForeignKey(Batch,on_delete=models.CASCADE,related_name='subjects')
    subject_name = models.CharField(max_length=200)
    subject_description = models.TextField()
    subject_thumbnail = CloudinaryField('subject_thumbnail')
    subject_status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at']
        unique_together = ['batch', 'subject_name']
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
    def __str__(self):
        return f"{self.batch.batch_name} - {self.subject_name}"
    




class Teacher(models.Model):

    user = models.OneToOneField(User,on_delete=models.CASCADE,related_name="teacher_profile")
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=10, unique=True)
    profile_image = models.ImageField(upload_to="teachers/profile/",blank=True,null=True)
    is_first_login = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    qualification = models.CharField(max_length=255,blank=True)
    specialization = models.CharField(max_length=255,blank=True)
    experience = models.PositiveIntegerField(default=0,help_text="Years of experience")
    bio = models.TextField(blank=True)
    linkedin = models.URLField(blank=True)
    website = models.URLField(blank=True)
    language = models.CharField(max_length=100,blank=True)
    profile_completed = models.BooleanField(default=False)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,related_name="created_teachers",null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def initials(self):

        if not self.full_name:
            return "NA"

        words = self.full_name.split()

        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()

        return self.full_name[:2].upper()
    def __str__(self):

        return self.full_name
    
    
class TeacherBatch(models.Model):

    teacher = models.ForeignKey(Teacher,on_delete=models.CASCADE,related_name="assigned_batches")
    batch = models.ForeignKey(Batch,on_delete=models.CASCADE,related_name="assigned_teachers")
    assigned_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="teacher_batch_assignments")
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ("teacher", "batch")
    def __str__(self):
        return f"{self.teacher.full_name} → {self.batch.batch_name}"
    
class TeacherSubject(models.Model):

    teacher = models.ForeignKey(Teacher,on_delete=models.CASCADE,related_name="assigned_subjects")
    batch = models.ForeignKey(Batch,on_delete=models.CASCADE,related_name="teacher_subject_batches")
    subject = models.ForeignKey(Subject,on_delete=models.CASCADE,related_name="assigned_teachers")
    assigned_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="teacher_subject_assignments")
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = (
            "teacher",
            "batch",
            "subject",
        )

    def __str__(self):
        return (f"{self.teacher.full_name} → " f"{self.subject.subject_name}")
    
# =========================================================
# COUPON MANAGEMENT
# =========================================================


class Coupon(models.Model):

    # -----------------------------------------------------
    # Coupon Type
    # -----------------------------------------------------

    COUPON_TYPE_CHOICES = [
        ("general", "General Coupon"),
        ("batch_specific", "Batch-Specific Coupon"),
        ("multi_checkout", "Multi Checkout Coupon"),
    ]

    # -----------------------------------------------------
    # Discount Type
    # -----------------------------------------------------

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    ]

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    # -----------------------------------------------------
    # Basic Information
    # -----------------------------------------------------

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique coupon code, for example NEO30.",
    )

    description = models.TextField(
        blank=True,
        help_text="Internal description of this coupon.",
    )

    coupon_thumbnail = CloudinaryField(
        "coupon_thumbnail",
        blank=True,
        null=True,
        help_text="Promotional image for this coupon.",
    )

    # -----------------------------------------------------
    # Coupon Type
    # -----------------------------------------------------

    coupon_type = models.CharField(
        max_length=20,
        choices=COUPON_TYPE_CHOICES,
        default="general",
        db_index=True,
    )

    # -----------------------------------------------------
    # Batch-Specific Coupon Marketplace Visibility
    # -----------------------------------------------------

    marketplace_visible = models.BooleanField(
        default=True,
        help_text=(
            "Controls whether a batch-specific coupon "
            "is shown in the student's available coupon list. "
            "Manual coupon-code entry can still be used when "
            "the coupon is otherwise valid."
        ),
    )

    # -----------------------------------------------------
    # Discount Settings
    # -----------------------------------------------------

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default="percentage",
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Percentage value or fixed discount amount.",
    )

    # -----------------------------------------------------
    # Order / Checkout Amount Restrictions
    # -----------------------------------------------------

    minimum_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=(
            "For General Coupon: minimum order amount. "
            "For Multi Checkout Coupon: minimum combined "
            "checkout amount."
        ),
    )

    maximum_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=(
            "For General Coupon: maximum order amount. "
            "For Multi Checkout Coupon: maximum combined "
            "checkout amount."
        ),
    )

    # -----------------------------------------------------
    # Percentage Coupon Maximum Discount
    # -----------------------------------------------------

    # Legacy field retained for schema compatibility.
    # It is no longer used by coupon validation,
    # discount calculation, create forms, or edit forms.

    maximum_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Legacy field — no longer used.",
    )

    # -----------------------------------------------------
    # Validity
    # -----------------------------------------------------

    valid_from = models.DateTimeField(
        help_text=(
            "Date and time from which the coupon becomes valid."
        ),
    )

    valid_until = models.DateTimeField(
        help_text=(
            "Date and time after which the coupon expires."
        ),
    )

    # -----------------------------------------------------
    # Usage Limits
    # -----------------------------------------------------

    usage_limit = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=(
            "Maximum total number of successful uses. "
            "Leave blank for unlimited usage."
        ),
    )

    per_user_limit = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=(
            "Maximum successful uses per student. "
            "Leave blank for unlimited usage."
        ),
    )

    used_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Number of successful coupon uses.",
    )

    total_discount_given = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
        help_text=(
            "Actual total discount granted across successful "
            "coupon checkouts."
        ),
    )

    # -----------------------------------------------------
    # Status Fields
    # -----------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )

    # Kept for compatibility with existing code.
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    # -----------------------------------------------------
    # Timestamps
    # -----------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # -----------------------------------------------------
    # Meta
    # -----------------------------------------------------

    class Meta:
        ordering = ["-created_at"]

        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"

        indexes = [
            models.Index(
                fields=["coupon_type"],
                name="coupon_type_idx",
            ),
            models.Index(
                fields=["status"],
                name="coupon_status_idx",
            ),
            models.Index(
                fields=["is_active"],
                name="coupon_active_idx",
            ),
            models.Index(
                fields=["valid_from"],
                name="coupon_valid_from_idx",
            ),
            models.Index(
                fields=["valid_until"],
                name="coupon_valid_until_idx",
            ),
        ]

    # -----------------------------------------------------
    # String Representation
    # -----------------------------------------------------

    def __str__(self):
        return self.code

    # -----------------------------------------------------
    # Helper Properties
    # -----------------------------------------------------

    @property
    def is_expired(self):
        """
        Returns True when the coupon validity period has ended.
        """

        return timezone.now() > self.valid_until

    @property
    def is_started(self):
        """
        Returns True when the coupon validity period has started.
        """

        return timezone.now() >= self.valid_from

    @property
    def usage_limit_reached(self):
        """
        Returns True when the total usage limit has been reached.
        """

        if self.usage_limit is None:
            return False

        return self.used_count >= self.usage_limit

    @property
    def is_valid_now(self):
        """
        Returns True when the coupon is active,
        within the validity period, and usable.
        """

        now = timezone.now()

        return (
            self.status == "active"
            and self.is_active
            and self.valid_from <= now <= self.valid_until
            and not self.usage_limit_reached
        )

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    def clean(self):
        """
        Validate coupon information before saving.

        Coupon types:

        General:
            Uses minimum_order_amount and
            maximum_order_amount.

        Batch-Specific:
            Does not use minimum_order_amount or
            maximum_order_amount.

        Multi Checkout:
            Uses minimum_order_amount and
            maximum_order_amount as the combined
            checkout amount range.

        maximum_discount_amount is a legacy field
        and is intentionally not validated.
        """

        # -------------------------------------------------
        # Normalize Coupon Code
        # -------------------------------------------------

        if self.code:
            self.code = self.code.strip().upper()

        # -------------------------------------------------
        # Discount Value
        # -------------------------------------------------

        if self.discount_value is None:
            raise ValidationError(
                {
                    "discount_value": (
                        "Discount value is required."
                    )
                }
            )

        if self.discount_value <= Decimal("0.00"):
            raise ValidationError(
                {
                    "discount_value": (
                        "Discount value must be greater than zero."
                    )
                }
            )

        # -------------------------------------------------
        # Percentage Discount Validation
        # -------------------------------------------------

        if (
            self.discount_type == "percentage"
            and self.discount_value > Decimal("100.00")
        ):
            raise ValidationError(
                {
                    "discount_value": (
                        "Percentage discount cannot exceed 100%."
                    )
                }
            )

        # -------------------------------------------------
        # Minimum Order / Checkout Amount
        # -------------------------------------------------

        if self.minimum_order_amount is None:
            self.minimum_order_amount = Decimal("0.00")

        if self.minimum_order_amount < Decimal("0.00"):
            raise ValidationError(
                {
                    "minimum_order_amount": (
                        "Minimum order amount cannot be negative."
                    )
                }
            )

        # -------------------------------------------------
        # Maximum Order / Checkout Amount
        # -------------------------------------------------

        if (
            self.maximum_order_amount is not None
            and self.maximum_order_amount < Decimal("0.00")
        ):
            raise ValidationError(
                {
                    "maximum_order_amount": (
                        "Maximum order amount cannot be negative."
                    )
                }
            )

        # -------------------------------------------------
        # General / Multi Checkout Amount Relationship
        # -------------------------------------------------

        if (
            self.maximum_order_amount is not None
            and self.maximum_order_amount
            < self.minimum_order_amount
        ):
            raise ValidationError(
                {
                    "maximum_order_amount": (
                        "Maximum amount cannot be less "
                        "than minimum amount."
                    )
                }
            )

        # -------------------------------------------------
        # Batch-Specific Restrictions
        # -------------------------------------------------

        if self.coupon_type == "batch_specific":

            if self.minimum_order_amount != Decimal("0.00"):
                raise ValidationError(
                    {
                        "minimum_order_amount": (
                            "Minimum order amount is not applicable "
                            "to batch-specific coupons."
                        )
                    }
                )

            if self.maximum_order_amount is not None:
                raise ValidationError(
                    {
                        "maximum_order_amount": (
                            "Maximum order amount is not applicable "
                            "to batch-specific coupons."
                        )
                    }
                )

        # -------------------------------------------------
        # Multi Checkout Restrictions
        # -------------------------------------------------

        if self.coupon_type == "multi_checkout":

            if self.minimum_order_amount <= Decimal("0.00"):
                raise ValidationError(
                    {
                        "minimum_order_amount": (
                            "Minimum checkout amount must be "
                            "greater than zero for a "
                            "multi-checkout coupon."
                        )
                    }
                )

            if self.maximum_order_amount is None:
                raise ValidationError(
                    {
                        "maximum_order_amount": (
                            "Maximum checkout amount is required "
                            "for a multi-checkout coupon."
                        )
                    }
                )

            if self.maximum_order_amount <= Decimal("0.00"):
                raise ValidationError(
                    {
                        "maximum_order_amount": (
                            "Maximum checkout amount must be "
                            "greater than zero for a "
                            "multi-checkout coupon."
                        )
                    }
                )

            if (
                self.maximum_order_amount
                < self.minimum_order_amount
            ):
                raise ValidationError(
                    {
                        "maximum_order_amount": (
                            "Maximum checkout amount cannot be "
                            "less than minimum checkout amount."
                        )
                    }
                )

        # -------------------------------------------------
        # Validity Dates
        # -------------------------------------------------

        if self.valid_from is None:
            raise ValidationError(
                {
                    "valid_from": (
                        "Valid from date and time is required."
                    )
                }
            )

        if self.valid_until is None:
            raise ValidationError(
                {
                    "valid_until": (
                        "Valid until date and time is required."
                    )
                }
            )

        if self.valid_until <= self.valid_from:
            raise ValidationError(
                {
                    "valid_until": (
                        "Coupon expiry date must be after "
                        "the start date."
                    )
                }
            )

        # -------------------------------------------------
        # Usage Limits
        # -------------------------------------------------

        if (
            self.usage_limit is not None
            and self.usage_limit == 0
        ):
            raise ValidationError(
                {
                    "usage_limit": (
                        "Usage limit must be greater than zero "
                        "or left blank for unlimited usage."
                    )
                }
            )

        if (
            self.per_user_limit is not None
            and self.per_user_limit == 0
        ):
            raise ValidationError(
                {
                    "per_user_limit": (
                        "Per-student usage limit must be "
                        "greater than zero or left blank "
                        "for unlimited usage."
                    )
                }
            )

        if (
            self.usage_limit is not None
            and self.per_user_limit is not None
            and self.per_user_limit > self.usage_limit
        ):
            raise ValidationError(
                {
                    "per_user_limit": (
                        "Per-student usage limit cannot exceed "
                        "the total usage limit."
                    )
                }
            )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    def save(self, *args, **kwargs):
        """
        Normalize coupon code and keep status fields synchronized.
        """

        if self.code:
            self.code = self.code.strip().upper()

        if self.status == "inactive":
            self.is_active = False
        else:
            self.status = "active"
            self.is_active = True

        super().save(*args, **kwargs)


# =========================================================
# COUPON BATCH RULE
# =========================================================


class CouponBatchRule(models.Model):
    """
    Connects coupons with batches.

    General coupon:
        Can connect to multiple batches.

    Batch-specific coupon:
        Can connect to only one batch.

    Multi-checkout coupon:
        Cannot connect to batches.

    This model is used for admin coupon configuration.
    Student coupon application will be handled separately.
    """

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="batch_rules",
    )

    batch = models.ForeignKey(
        "Batch",
        on_delete=models.CASCADE,
        related_name="coupon_rules",
    )

    is_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Enable or disable this coupon for this batch."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        verbose_name = "Coupon Batch Rule"
        verbose_name_plural = "Coupon Batch Rules"

        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "batch"],
                name="unique_coupon_batch_rule",
            ),
        ]

    def __str__(self):
        return (
            f"{self.coupon.code} - "
            f"{self.batch.batch_name}"
        )

    def clean(self):
        """
        Validate coupon-to-batch relationships.

        Batch-specific:
            Only one batch is allowed.

        General:
            Multiple batches are allowed.

        Multi-checkout:
            Batch rules are not allowed.
        """

        if not self.coupon_id or not self.batch_id:
            return

        # -------------------------------------------------
        # Multi Checkout Cannot Use Batch Rules
        # -------------------------------------------------

        if self.coupon.coupon_type == "multi_checkout":
            raise ValidationError(
                {
                    "coupon": (
                        "Multi-checkout coupons cannot be "
                        "connected to batches."
                    )
                }
            )

        # -------------------------------------------------
        # Batch-Specific Can Use Only One Batch
        # -------------------------------------------------

        if self.coupon.coupon_type == "batch_specific":

            existing_rule = (
                CouponBatchRule.objects
                .filter(coupon=self.coupon)
                .exclude(pk=self.pk)
            )

            if existing_rule.exists():
                raise ValidationError(
                    (
                        "A batch-specific coupon can be "
                        "connected to only one batch."
                    )
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)