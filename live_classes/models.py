from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from admins.models import Batch, Subject, Teacher
from courses.models import CourseChapter


class LiveClassStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmed"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"
    NO_SHOW = "no_show", "No Show"


class CancellationStatus(models.TextChoices):
    PENDING = "pending", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class RecordingStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not Started"
    RECORDING = "recording", "Recording"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class ParticipantActionType(models.TextChoices):
    SUSPENDED = "suspended", "Suspended"
    RESTORED = "restored", "Restored"


class ChatMessageType(models.TextChoices):
    MESSAGE = "message", "Message"
    SYSTEM = "system", "System Message"


class BatchScheduleRule(models.Model):
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="live_schedule_rules",
    )
    weekday = models.PositiveSmallIntegerField(
        choices=[
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ],
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    default_duration_minutes = models.PositiveSmallIntegerField(default=60)
    max_advance_days = models.PositiveSmallIntegerField(default=30)
    minimum_notice_minutes = models.PositiveSmallIntegerField(default=0)
    buffer_minutes = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="live_schedule_rules_created",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["batch", "weekday"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "weekday"],
                name="live_rule_batch_weekday_uniq",
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0, weekday__lte=6),
                name="live_rule_weekday_valid",
            ),
            models.CheckConstraint(
                condition=Q(default_duration_minutes__gt=0),
                name="live_rule_duration_positive",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="live_rule_end_after_start",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.weekday is not None and not 0 <= self.weekday <= 6:
            errors["weekday"] = "Choose a valid weekday."

        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            errors["end_time"] = "End time must be later than start time."

        if self.default_duration_minutes <= 0:
            errors["default_duration_minutes"] = (
                "Class duration must be greater than zero."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.batch} - {self.get_weekday_display()} "
            f"({self.start_time}–{self.end_time})"
        )


class LiveClass(models.Model):
    batch = models.ForeignKey(
        Batch,
        on_delete=models.PROTECT,
        related_name="live_classes",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="live_classes",
    )
    chapter = models.ForeignKey(
        CourseChapter,
        on_delete=models.PROTECT,
        related_name="live_classes",
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="live_classes",
    )
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=15,
        choices=LiveClassStatus.choices,
        default=LiveClassStatus.CONFIRMED,
        db_index=True,
    )
    meeting_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Configured meeting provider identifier.",
    )
    provider_room_id = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="live_classes_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at", "pk"]
        indexes = [
            models.Index(
                fields=["batch", "start_at"],
                name="live_class_batch_start_idx",
            ),
            models.Index(
                fields=["teacher", "start_at"],
                name="live_class_teacher_start_idx",
            ),
            models.Index(
                fields=["status", "start_at"],
                name="live_class_status_start_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="live_class_end_after_start",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.start_at and self.end_at and self.end_at <= self.start_at:
            errors["end_at"] = "Class end time must be later than start time."

        if self.batch_id and self.subject_id:
            if self.subject.batch_id != self.batch_id:
                errors["subject"] = (
                    "The selected subject does not belong to this batch."
                )

        if self.batch_id and self.chapter_id:
            if self.chapter.batch_id != self.batch_id:
                errors["chapter"] = (
                    "The selected chapter does not belong to this batch."
                )

        if self.subject_id and self.chapter_id:
            if self.chapter.subject_id != self.subject_id:
                errors["chapter"] = (
                    "The selected chapter does not belong to this subject."
                )

        if self.teacher_id and self.teacher.is_blocked:
            errors["teacher"] = (
                "A blocked teacher cannot be assigned to a live class."
            )

        if self.teacher_id and self.teacher.user_id:
            if not self.teacher.user.is_active:
                errors["teacher"] = "An inactive teacher cannot teach a live class."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.batch} - {self.subject} - "
            f"{self.start_at:%d %b %Y %I:%M %p}"
        )


class CancellationRequest(models.Model):
    live_class = models.ForeignKey(
        LiveClass,
        on_delete=models.PROTECT,
        related_name="cancellation_requests",
    )
    requested_by = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="live_cancellation_requests",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=12,
        choices=CancellationStatus.choices,
        default=CancellationStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="live_cancellation_reviews",
    )
    review_note = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(
                fields=["status", "requested_at"],
                name="live_cancel_status_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if not self.reason or not self.reason.strip():
            errors["reason"] = "A cancellation reason is required."

        if self.live_class_id and self.requested_by_id:
            if self.live_class.teacher_id != self.requested_by_id:
                errors["requested_by"] = (
                    "Only the currently assigned teacher can request cancellation."
                )

        if self.status in (
            CancellationStatus.APPROVED,
            CancellationStatus.REJECTED,
        ):
            if not self.reviewed_by_id:
                errors["reviewed_by"] = (
                    "A reviewer is required for a completed decision."
                )
            if not self.reviewed_at:
                errors["reviewed_at"] = (
                    "The review timestamp is required for a completed decision."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Cancellation request #{self.pk} - {self.get_status_display()}"


class TeacherReassignmentHistory(models.Model):
    live_class = models.ForeignKey(
        LiveClass,
        on_delete=models.PROTECT,
        related_name="reassignment_history",
    )
    previous_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="live_classes_reassigned_from",
    )
    new_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="live_classes_reassigned_to",
    )
    reassigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="live_class_reassignments",
    )
    reason = models.TextField()
    reassigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reassigned_at"]

    def clean(self):
        super().clean()
        errors = {}

        if self.previous_teacher_id == self.new_teacher_id:
            errors["new_teacher"] = (
                "The replacement teacher must be different."
            )

        if not self.reason or not self.reason.strip():
            errors["reason"] = "A reassignment reason is required."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Class #{self.live_class_id}: "
            f"{self.previous_teacher} → {self.new_teacher}"
        )


class LiveRecording(models.Model):
    live_class = models.ForeignKey(
        LiveClass,
        on_delete=models.PROTECT,
        related_name="recordings",
    )
    status = models.CharField(
        max_length=15,
        choices=RecordingStatus.choices,
        default=RecordingStatus.NOT_STARTED,
        db_index=True,
    )
    storage_provider = models.CharField(max_length=50, blank=True)
    provider_recording_id = models.CharField(max_length=255, blank=True)
    private_storage_key = models.CharField(max_length=500, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["live_class", "status"],
                name="live_rec_class_status_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.duration_seconds is not None and self.duration_seconds < 0:
            errors["duration_seconds"] = "Duration cannot be negative."

        if self.file_size_bytes is not None and self.file_size_bytes < 0:
            errors["file_size_bytes"] = "File size cannot be negative."

        if self.started_at and self.finished_at:
            if self.finished_at < self.started_at:
                errors["finished_at"] = (
                    "Recording finish time cannot precede its start time."
                )

        if self.status == RecordingStatus.READY and not (
            self.private_storage_key or self.provider_recording_id
        ):
            errors["private_storage_key"] = (
                "A ready recording must have a storage key or provider recording ID."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Recording for class #{self.live_class_id} "
            f"({self.get_status_display()})"
        )


class LiveAttendance(models.Model):
    live_class = models.ForeignKey(
        LiveClass,
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="live_class_attendance",
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    attended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["live_class", "student"]
        constraints = [
            models.UniqueConstraint(
                fields=["live_class", "student"],
                name="live_attendance_student_class_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.joined_at and self.left_at and self.left_at < self.joined_at:
            errors["left_at"] = "Leave time cannot precede join time."

        if self.duration_seconds < 0:
            errors["duration_seconds"] = "Attendance duration cannot be negative."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Attendance: student #{self.student_id}, "
            f"class #{self.live_class_id}"
        )


class LiveParticipantAction(models.Model):
    live_class = models.ForeignKey(
        LiveClass,
        on_delete=models.PROTECT,
        related_name="participant_actions",
    )
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="live_participant_actions",
    )
    action = models.CharField(
        max_length=12,
        choices=ParticipantActionType.choices,
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="live_moderation_actions",
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["live_class", "participant", "created_at"],
                name="live_participant_action_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_action_display()} - user #{self.participant_id}, "
            f"class #{self.live_class_id}"
        )


class LiveChatMessage(models.Model):
    live_class = models.ForeignKey(
        LiveClass,
        on_delete=models.PROTECT,
        related_name="chat_messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="live_chat_messages",
    )
    message_type = models.CharField(
        max_length=10,
        choices=ChatMessageType.choices,
        default=ChatMessageType.MESSAGE,
    )
    message = models.TextField(max_length=2000)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(
                fields=["live_class", "created_at"],
                name="live_chat_class_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.message or not self.message.strip():
            raise ValidationError({
                "message": "A chat message cannot be empty."
            })

    def __str__(self):
        return f"Chat message #{self.pk} for class #{self.live_class_id}"