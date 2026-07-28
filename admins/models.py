from django.db import models
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField
from decimal import Decimal
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.utils import timezone


from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from cloudinary.models import CloudinaryField
from datetime import timedelta

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