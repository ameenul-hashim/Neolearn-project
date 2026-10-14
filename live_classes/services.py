
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from admins.models import (
    Batch,
    Subject,
    Teacher,
    TeacherBatch,
    TeacherSubject,
)
from courses.models import CourseChapter
from .models import (
    CancellationRequest,
    CancellationStatus,
    LiveClass,
    LiveClassStatus)



# ============================================================
# BOOKING CONFIGURATION
# ============================================================

BOOKING_WINDOW_DAYS = 7

EARLIEST_START_TIME = time(5, 0)
LATEST_START_TIME = time(23, 0)

ALLOWED_DURATION_MINUTES = {60, 120, 180}


# ============================================================
# COMMON VALIDATION HELPERS
# ============================================================

def _raise_error(message):
    """Raise a user-friendly Django validation error."""
    raise ValidationError(message)


def _get_booking_dates():
    """Return today and the following six calendar dates."""
    today = timezone.localdate()

    return (
        today,
        today + timedelta(days=BOOKING_WINDOW_DAYS - 1),
    )


def _validate_datetime(start_at, end_at):
    """
    Validate class start and end datetimes.

    Start:
    - Must be timezone-aware and in the future.
    - Must be within the seven-calendar-date booking window.
    - Must start on an exact hour from 5 AM through 11 PM.

    Duration:
    - Must be exactly 1, 2 or 3 hours.

    A class may finish at midnight or on the following date.
    """

    if start_at is None or end_at is None:
        _raise_error(
            "Class start time and end time are required."
        )

    if not isinstance(start_at, datetime) or not isinstance(
        end_at, datetime
    ):
        _raise_error(
            "Valid class start and end datetimes are required."
        )

    if not timezone.is_aware(start_at) or not timezone.is_aware(
        end_at
    ):
        _raise_error(
            "Class start and end times must be timezone-aware."
        )

    if end_at <= start_at:
        _raise_error(
            "Class end time must be after its start time."
        )

    duration = end_at - start_at

    allowed_durations = {
        timedelta(minutes=minutes)
        for minutes in ALLOWED_DURATION_MINUTES
    }

    if duration not in allowed_durations:
        _raise_error(
            "Class duration must be exactly 1, 2 or 3 hours."
        )

    now = timezone.now()

    if start_at <= now:
        _raise_error(
            "You can only book a class in the future."
        )

    local_start = timezone.localtime(start_at)
    first_date, last_date = _get_booking_dates()

    if not first_date <= local_start.date() <= last_date:
        _raise_error(
            "Classes can only be booked for today or "
            "the following six calendar dates."
        )

    local_start_time = local_start.time().replace(tzinfo=None)

    if local_start_time < EARLIEST_START_TIME:
        _raise_error(
            "Classes cannot start before 5:00 AM."
        )

    if local_start_time > LATEST_START_TIME:
        _raise_error(
            "Classes cannot start after 11:00 PM."
        )

    if (
        local_start_time.minute != 0
        or local_start_time.second != 0
        or local_start_time.microsecond != 0
    ):
        _raise_error(
            "Classes must start on the hour, "
            "for example 5:00 AM or 6:00 AM."
        )


# ============================================================
# TEACHER ASSIGNMENT VALIDATION
# ============================================================

def validate_teacher_assignment(teacher, batch, subject):
    """
    Require an active teacher account and active assignments
    to the selected batch and subject.
    """

    if not getattr(teacher, "pk", None):
        _raise_error("Select a valid teacher.")

    teacher = (
        Teacher.objects
        .select_related("user")
        .filter(pk=teacher.pk)
        .first()
    )

    if teacher is None:
        _raise_error(
            "The selected teacher does not exist."
        )

    if teacher.is_blocked:
        _raise_error(
            "This teacher is blocked and cannot teach live classes."
        )

    linked_user = getattr(teacher, "user", None)

    if linked_user is not None and not linked_user.is_active:
        _raise_error(
            "This teacher's account is inactive "
            "and cannot be scheduled."
        )

    batch_assignment = TeacherBatch.objects.filter(
        teacher=teacher,
        batch=batch,
        is_active=True,
    ).exists()

    if not batch_assignment:
        _raise_error(
            "This teacher is not actively assigned "
            "to the selected batch."
        )

    subject_assignment = TeacherSubject.objects.filter(
        teacher=teacher,
        batch=batch,
        subject=subject,
        is_active=True,
    ).exists()

    if not subject_assignment:
        _raise_error(
            "This teacher is not actively assigned "
            "to the selected subject."
        )

    return teacher


# ============================================================
# BATCH, SUBJECT AND CHAPTER VALIDATION
# ============================================================

def validate_class_content(batch, subject, chapter):
    """
    Verify that the selected batch, subject and chapter belong
    together and that the subject and chapter are published.

    Published and archived batches are both permitted.
    """

    if not (
        getattr(batch, "pk", None)
        and getattr(subject, "pk", None)
        and getattr(chapter, "pk", None)
    ):
        _raise_error(
            "A batch, subject and chapter are required."
        )

    if subject.batch_id != batch.pk:
        _raise_error(
            "The selected subject does not belong to this batch."
        )

    if chapter.batch_id != batch.pk:
        _raise_error(
            "The selected chapter does not belong to this batch."
        )

    if chapter.subject_id != subject.pk:
        _raise_error(
            "The selected chapter does not belong to this subject."
        )

    if getattr(batch, "batch_status", None) not in {
        "published",
        "archived",
    }:
        _raise_error(
            "Only published or archived batches can be scheduled."
        )

    if getattr(subject, "subject_status", None) != "published":
        _raise_error(
            "Live classes can only be booked for published subjects."
        )

    if getattr(chapter, "status", None) != "published":
        _raise_error(
            "Live classes can only be booked for published chapters."
        )


# ============================================================
# BATCH-WISE AND TEACHER-WISE CONFLICT VALIDATION
# ============================================================

def validate_class_conflicts(
    teacher,
    batch,
    start_at,
    end_at,
    buffer_minutes=0,
    exclude_class_id=None,
):
    """
    Reject overlapping confirmed classes for:

    1. The same batch, across every subject and teacher.
    2. The same teacher, across every batch.

    Different batches may overlap if their teachers differ
    and neither batch has a conflicting class.

    Back-to-back classes are allowed when buffer_minutes is 0.
    Cancelled, completed and no-show classes do not block booking.
    """

    if buffer_minutes < 0:
        _raise_error(
            "The class buffer cannot be negative."
        )

    buffer = timedelta(minutes=buffer_minutes)

    protected_start = start_at - buffer
    protected_end = end_at + buffer

    conflicts = LiveClass.objects.filter(
        status=LiveClassStatus.CONFIRMED,
        start_at__lt=protected_end,
        end_at__gt=protected_start,
    )

    if exclude_class_id is not None:
        conflicts = conflicts.exclude(pk=exclude_class_id)

    if conflicts.filter(batch_id=batch.pk).exists():
        _raise_error(
            "This batch already has a confirmed class "
            "during the requested time."
        )

    if conflicts.filter(teacher_id=teacher.pk).exists():
        _raise_error(
            "This teacher already has a confirmed class "
            "during the requested time in another batch."
        )


# ============================================================
# CREATE A LIVE CLASS
# ============================================================

@transaction.atomic
def create_live_class(
    *,
    teacher,
    batch,
    subject,
    chapter,
    start_at,
    end_at,
    created_by,
):
    """
    Create a confirmed live class after checking:

    - Authenticated creator.
    - Seven-day booking window.
    - Hourly start times from 5 AM through 11 PM.
    - Duration of exactly 1, 2 or 3 hours.
    - Published or archived batch.
    - Published subject and chapter.
    - Active teacher account and assignments.
    - Batch-wise and teacher-wise scheduling conflicts.

    Both Admin and Teacher booking views must use this service.

    BatchScheduleRule is intentionally not enforced here.
    """

    if not getattr(created_by, "is_authenticated", False):
        _raise_error(
            "An authenticated user is required to create a booking."
        )

    if not getattr(batch, "pk", None):
        _raise_error("Select a valid batch.")

    if not getattr(teacher, "pk", None):
        _raise_error("Select a valid teacher.")

    if not getattr(subject, "pk", None):
        _raise_error("Select a valid subject.")

    if not getattr(chapter, "pk", None):
        _raise_error("Select a valid chapter.")

    # Validate submitted times before acquiring database locks.
    _validate_datetime(start_at, end_at)

    # Lock the batch to serialize bookings for that batch.
    locked_batch = (
        Batch.objects
        .select_for_update()
        .filter(pk=batch.pk)
        .first()
    )

    if locked_batch is None:
        _raise_error(
            "The selected batch no longer exists."
        )

    # Lock the teacher to serialize bookings across batches.
    locked_teacher = (
        Teacher.objects
        .select_for_update()
        .filter(pk=teacher.pk)
        .first()
    )

    if locked_teacher is None:
        _raise_error(
            "The selected teacher no longer exists."
        )

    # Reload objects after acquiring the locks.
    batch = Batch.objects.filter(
        pk=locked_batch.pk
    ).first()

    teacher = Teacher.objects.filter(
        pk=locked_teacher.pk
    ).first()

    if batch is None or teacher is None:
        _raise_error(
            "The selected batch or teacher no longer exists."
        )

    subject = Subject.objects.filter(
        pk=subject.pk,
        batch=batch,
    ).first()

    if subject is None:
        _raise_error(
            "The selected subject does not belong "
            "to the selected batch."
        )

    chapter = CourseChapter.objects.filter(
        pk=chapter.pk,
        batch=batch,
        subject=subject,
    ).first()

    if chapter is None:
        _raise_error(
            "The selected chapter does not belong "
            "to the selected batch and subject."
        )

    # Recheck teacher eligibility inside the transaction.
    teacher = validate_teacher_assignment(
        teacher=teacher,
        batch=batch,
        subject=subject,
    )

    validate_class_content(
        batch=batch,
        subject=subject,
        chapter=chapter,
    )

    # Recheck the complete booking interval immediately
    # before checking conflicts and saving.
    _validate_datetime(start_at, end_at)

    validate_class_conflicts(
        teacher=teacher,
        batch=batch,
        start_at=start_at,
        end_at=end_at,
        buffer_minutes=0,
    )

    live_class = LiveClass(
        teacher=teacher,
        batch=batch,
        subject=subject,
        chapter=chapter,
        start_at=start_at,
        end_at=end_at,
        status=LiveClassStatus.CONFIRMED,
        created_by=created_by,
    )

    # Run the model's existing validation as an extra safeguard.
    live_class.full_clean()
    live_class.save()

    return live_class

# ============================================================
# RESCHEDULE A LIVE CLASS
# ============================================================

@transaction.atomic
def reschedule_live_class(
    *,
    live_class_id,
    start_at,
    end_at,
    updated_by,
    teacher=None,
):
    """
    Reschedule an existing confirmed class.

    Admin callers may omit teacher.
    Teacher callers must supply their own Teacher profile.
    """

    if not getattr(updated_by, "is_authenticated", False):
        _raise_error("Authentication is required.")

    live_class = (
        LiveClass.objects
        .select_for_update()
        .filter(pk=live_class_id)
        .first()
    )

    if live_class is None:
        _raise_error("The requested live class was not found.")

    if teacher is not None and live_class.teacher_id != teacher.pk:
        _raise_error("You cannot reschedule another teacher's class.")

    if live_class.status != LiveClassStatus.CONFIRMED:
        _raise_error("Only confirmed classes can be rescheduled.")

    if live_class.start_at <= timezone.now():
        _raise_error("A class that has already started cannot be rescheduled.")

    pending_request = CancellationRequest.objects.filter(
        live_class=live_class,
        status=CancellationStatus.PENDING,
    ).exists()

    if pending_request:
        _raise_error(
            "This class has a pending cancellation request. "
            "Wait for the Admin's decision before rescheduling."
        )

    _validate_datetime(start_at, end_at)

    validate_class_conflicts(
        teacher=live_class.teacher,
        batch=live_class.batch,
        start_at=start_at,
        end_at=end_at,
        exclude_class_id=live_class.pk,
    )

    live_class.start_at = start_at
    live_class.end_at = end_at

    live_class.full_clean()
    live_class.save(update_fields=["start_at", "end_at", "updated_at"])

    return live_class


# ============================================================
# REQUEST LIVE CLASS CANCELLATION
# ============================================================

@transaction.atomic
def request_live_class_cancellation(
    *,
    live_class_id,
    teacher,
    reason,
):
    """
    Submit a cancellation request for the assigned teacher.

    A request does not cancel the class.
    """

    if not reason or not reason.strip():
        _raise_error("Please provide a cancellation reason.")

    live_class = (
        LiveClass.objects
        .select_for_update()
        .filter(pk=live_class_id)
        .first()
    )

    if live_class is None:
        _raise_error("The requested live class was not found.")

    if live_class.teacher_id != teacher.pk:
        _raise_error("You can only request cancellation of your own class.")

    if live_class.status != LiveClassStatus.CONFIRMED:
        _raise_error("Only confirmed classes can be cancelled.")

    if live_class.start_at <= timezone.now():
        _raise_error(
            "A class that has already started cannot use the normal "
            "cancellation-request workflow."
        )

    pending_exists = CancellationRequest.objects.filter(
        live_class=live_class,
        status=CancellationStatus.PENDING,
    ).exists()

    if pending_exists:
        _raise_error(
            "A cancellation request is already awaiting Admin review."
        )

    request_record = CancellationRequest(
        live_class=live_class,
        requested_by=teacher,
        reason=reason.strip(),
        status=CancellationStatus.PENDING,
    )

    request_record.full_clean()
    request_record.save()

    return request_record


# ============================================================
# REVIEW A CANCELLATION REQUEST
# ============================================================

@transaction.atomic
def review_live_class_cancellation(
    *,
    request_id,
    reviewed_by,
    approve,
    review_note="",
):
    """
    Admin-only callers may approve or reject a request.

    The calling view must enforce Admin authorization.
    """

    if not getattr(reviewed_by, "is_authenticated", False):
        _raise_error("Authentication is required.")

    request_record = (
        CancellationRequest.objects
        .select_for_update()
        .select_related("live_class")
        .filter(pk=request_id)
        .first()
    )

    if request_record is None:
        _raise_error("The cancellation request was not found.")

    if request_record.status != CancellationStatus.PENDING:
        _raise_error("This cancellation request has already been reviewed.")

    live_class = (
        LiveClass.objects
        .select_for_update()
        .filter(pk=request_record.live_class_id)
        .first()
    )

    if live_class is None:
        _raise_error("The associated live class was not found.")

    if live_class.status != LiveClassStatus.CONFIRMED:
        _raise_error(
            "This class is no longer confirmed and cannot be cancelled "
            "through this request."
        )

    if approve:
        live_class.status = LiveClassStatus.CANCELLED
        live_class.save(update_fields=["status", "updated_at"])

        request_record.status = CancellationStatus.APPROVED
    else:
        request_record.status = CancellationStatus.REJECTED

    request_record.reviewed_by = reviewed_by
    request_record.review_note = (review_note or "").strip()
    request_record.reviewed_at = timezone.now()

    request_record.full_clean()
    request_record.save(
        update_fields=[
            "status",
            "reviewed_by",
            "review_note",
            "reviewed_at",
        ]
    )

    return request_record