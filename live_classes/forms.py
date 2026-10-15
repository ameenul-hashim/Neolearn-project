from datetime import datetime, time, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from admins.models import (
    Batch,
    Subject,
    Teacher,
    TeacherBatch,
    TeacherSubject,
)
from courses.models import CourseChapter


# ============================================================
# BOOKING RULES
# ============================================================

BOOKING_WINDOW_DAYS = 7

EARLIEST_START_TIME = time(5, 0)
LATEST_START_TIME = time(23, 0)

ALLOWED_DURATIONS = {
    60: "1 hour",
    120: "2 hours",
    180: "3 hours",
}

ALLOWED_BATCH_STATUSES = ("published", "archived")


# ============================================================
# SHARED HELPERS
# ============================================================

def get_booking_date_range():
    """Return today and the next six calendar dates."""
    today = timezone.localdate()
    return today, today + timedelta(days=BOOKING_WINDOW_DAYS - 1)


def _submitted_pk(form, field_name):
    """Safely read a submitted primary key."""
    if not form.is_bound:
        return None

    value = form.data.get(field_name)

    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _initial_pk(form, field_name):
    """Resolve an initial model instance or primary key."""
    value = form.initial.get(field_name)

    if value in (None, ""):
        value = form.fields[field_name].initial

    return getattr(value, "pk", value)


def get_hourly_start_choices():
    """Return hourly start times in 12-hour AM/PM format."""
    choices = [("", "Select start time")]

    current = datetime.combine(
        timezone.localdate(),
        EARLIEST_START_TIME,
    )
    last = datetime.combine(
        timezone.localdate(),
        LATEST_START_TIME,
    )

    while current <= last:
        choices.append((
            current.strftime("%H:%M"),
            current.strftime("%I:%M %p").lstrip("0"),
        ))
        current += timedelta(hours=1)

    return choices


def get_active_teacher_batch_ids(teacher):
    return TeacherBatch.objects.filter(
        teacher=teacher,
        is_active=True,
    ).values_list("batch_id", flat=True)


def get_active_teacher_subject_ids(teacher):
    return TeacherSubject.objects.filter(
        teacher=teacher,
        is_active=True,
    ).values_list("subject_id", flat=True)


def get_eligible_teachers(batch_id=None, subject_id=None):
    """
    Return active, unblocked teachers who have an active batch
    assignment and, when supplied, an active subject assignment.
    """
    teachers = Teacher.objects.filter(
        is_blocked=False,
        user__is_active=True,
    )

    if batch_id:
        batch_teacher_ids = TeacherBatch.objects.filter(
            batch_id=batch_id,
            is_active=True,
        ).values_list("teacher_id", flat=True)

        teachers = teachers.filter(pk__in=batch_teacher_ids)

    if subject_id:
        subject_assignments = TeacherSubject.objects.filter(
            subject_id=subject_id,
            is_active=True,
        )

        if batch_id:
            subject_assignments = subject_assignments.filter(
                batch_id=batch_id,
            )

        teachers = teachers.filter(
            pk__in=subject_assignments.values_list(
                "teacher_id",
                flat=True,
            ),
        )

    return teachers.order_by("full_name", "pk").distinct()


# ============================================================
# LIVE CLASS BOOKING FORM
# Shared by Admin and Teacher
# ============================================================

class LiveClassBookingForm(forms.Form):

    batch = forms.ModelChoiceField(
        queryset=Batch.objects.none(),
        label="Batch",
        empty_label="Select batch",
        error_messages={
            "required": "Please select a batch.",
            "invalid_choice": (
                "Select a valid published or archived batch."
            ),
        },
        widget=forms.Select(attrs={
            "class": "booking-input",
        }),
    )

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        label="Subject",
        empty_label="Select subject",
        error_messages={
            "required": "Please select a subject.",
            "invalid_choice": (
                "Select a published subject belonging to the selected batch."
            ),
        },
        widget=forms.Select(attrs={
            "class": "booking-input",
        }),
    )

    chapter = forms.ModelChoiceField(
        queryset=CourseChapter.objects.none(),
        label="Chapter",
        empty_label="Select published chapter",
        error_messages={
            "required": "Please select a chapter.",
            "invalid_choice": (
                "Select a published chapter belonging to the selected subject."
            ),
        },
        widget=forms.Select(attrs={
            "class": "booking-input",
        }),
    )

    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.none(),
        label="Teacher",
        empty_label="Select teacher",
        error_messages={
            "required": "Please select a teacher.",
            "invalid_choice": (
                "The selected teacher is not eligible for this booking."
            ),
        },
        widget=forms.Select(attrs={
            "class": "booking-input",
        }),
    )

    class_date = forms.DateField(
        label="Class date",
        input_formats=["%Y-%m-%d"],
        error_messages={
            "required": "Please select a class date.",
            "invalid": "Enter a valid class date.",
        },
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "booking-input",
        }),
    )

    start_time = forms.TimeField(
        label="Start time",
        input_formats=["%H:%M"],
        error_messages={
            "required": "Please select a class start time.",
            "invalid": "Select a valid hourly start time.",
        },
        widget=forms.Select(
            choices=get_hourly_start_choices(),
            attrs={"class": "booking-input"},
        ),
    )

    duration_minutes = forms.TypedChoiceField(
        label="Duration",
        choices=[
            ("", "Select duration"),
            ("60", "1 hour"),
            ("120", "2 hours"),
            ("180", "3 hours"),
        ],
        coerce=int,
        empty_value=None,
        error_messages={
            "required": "Please select a class duration.",
            "invalid_choice": "Choose a duration of 1, 2 or 3 hours.",
        },
        widget=forms.Select(attrs={
            "class": "booking-input",
        }),
    )

    def __init__(
        self,
        *args,
        teacher=None,
        admin_mode=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.teacher_profile = teacher
        self.admin_mode = admin_mode

        if admin_mode and teacher is not None:
            raise ValueError(
                "Admin booking mode must not receive a fixed teacher."
            )

        if not admin_mode and teacher is None:
            raise ValueError(
                "Teacher booking mode requires the logged-in teacher profile."
            )

        # ----------------------------------------------------
        # DATE INPUT LIMITS
        # ----------------------------------------------------

        first_date, last_date = get_booking_date_range()

        self.fields["class_date"].widget.attrs.update({
            "min": first_date.isoformat(),
            "max": last_date.isoformat(),
        })

        # ----------------------------------------------------
        # IDENTIFY SELECTED BATCH AND SUBJECT
        # ----------------------------------------------------

        if self.is_bound:
            selected_batch_id = _submitted_pk(self, "batch")
            selected_subject_id = _submitted_pk(self, "subject")
        else:
            selected_batch_id = _initial_pk(self, "batch")
            selected_subject_id = _initial_pk(self, "subject")

        # ----------------------------------------------------
        # BATCH QUERYSET
        # ----------------------------------------------------

        batches = Batch.objects.filter(
            batch_status__in=ALLOWED_BATCH_STATUSES,
        )

        if not admin_mode:
            batches = batches.filter(
                pk__in=get_active_teacher_batch_ids(teacher),
            )

        self.fields["batch"].queryset = batches.order_by(
            "batch_name",
            "pk",
        )

        # Admin booking batch remains visible and independent from the
        # timetable batch filter.

        # ----------------------------------------------------
        # SUBJECT QUERYSET
        # ----------------------------------------------------

        subjects = Subject.objects.filter(
            batch__batch_status__in=ALLOWED_BATCH_STATUSES,
            subject_status="published",
        )

        if selected_batch_id:
            subjects = subjects.filter(
                batch_id=selected_batch_id,
            )
        else:
            subjects = subjects.none()

        if not admin_mode:
            subjects = subjects.filter(
                pk__in=get_active_teacher_subject_ids(teacher),
                batch_id__in=get_active_teacher_batch_ids(teacher),
            )

        self.fields["subject"].queryset = (
            subjects
            .select_related("batch")
            .order_by("batch__batch_name", "subject_name", "pk")
        )

        # ----------------------------------------------------
        # CHAPTER QUERYSET
        # ----------------------------------------------------

        chapters = CourseChapter.objects.filter(
            batch__batch_status__in=ALLOWED_BATCH_STATUSES,
            subject__subject_status="published",
            status="published",
        )

        if selected_batch_id:
            chapters = chapters.filter(
                batch_id=selected_batch_id,
            )
        else:
            chapters = chapters.none()

        if selected_subject_id:
            chapters = chapters.filter(
                subject_id=selected_subject_id,
            )
        else:
            chapters = chapters.none()

        if not admin_mode:
            chapters = chapters.filter(
                batch_id__in=get_active_teacher_batch_ids(teacher),
                subject_id__in=get_active_teacher_subject_ids(teacher),
            )

        self.fields["chapter"].queryset = (
            chapters
            .select_related("batch", "subject")
            .order_by(
                "batch__batch_name",
                "subject__subject_name",
                "chapter_order",
                "pk",
            )
        )

        # ----------------------------------------------------
        # TEACHER QUERYSET
        # ----------------------------------------------------

        eligible_teachers = get_eligible_teachers(
            batch_id=selected_batch_id,
            subject_id=selected_subject_id,
        )

        if not admin_mode:
            eligible_teachers = eligible_teachers.filter(
                pk=teacher.pk,
            )

            self.fields["teacher"].initial = teacher.pk
            self.fields["teacher"].widget = forms.HiddenInput()

        self.fields["teacher"].queryset = eligible_teachers

    # ========================================================
    # DATE VALIDATION
    # ========================================================

    def clean_class_date(self):
        class_date = self.cleaned_data["class_date"]
        first_date, last_date = get_booking_date_range()

        if class_date < first_date:
            raise forms.ValidationError(
                "You cannot book a class for a past date."
            )

        if class_date > last_date:
            raise forms.ValidationError(
                "Bookings are limited to today and the next six dates."
            )

        return class_date

    # ========================================================
    # START-TIME VALIDATION
    # ========================================================

    def clean_start_time(self):
        start_time = self.cleaned_data["start_time"]

        if start_time < EARLIEST_START_TIME:
            raise forms.ValidationError(
                "Classes cannot start before 5:00 AM."
            )

        if start_time > LATEST_START_TIME:
            raise forms.ValidationError(
                "Choose an hourly start time no later than 11:00 PM."
            )

        if start_time.minute != 0 or start_time.second != 0:
            raise forms.ValidationError(
                "Classes must start on the hour."
            )

        return start_time

    # ========================================================
    # CROSS-FIELD VALIDATION
    # ========================================================

    def clean(self):
        cleaned_data = super().clean()

        batch = cleaned_data.get("batch")
        subject = cleaned_data.get("subject")
        chapter = cleaned_data.get("chapter")
        selected_teacher = cleaned_data.get("teacher")
        class_date = cleaned_data.get("class_date")
        start_time = cleaned_data.get("start_time")
        duration_minutes = cleaned_data.get("duration_minutes")

        # ----------------------------------------------------
        # BATCH / SUBJECT RELATIONSHIP
        # ----------------------------------------------------

        if batch and subject and subject.batch_id != batch.pk:
            self.add_error(
                "subject",
                "Choose a subject belonging to the selected batch.",
            )

        # ----------------------------------------------------
        # BATCH / CHAPTER RELATIONSHIP
        # ----------------------------------------------------

        if batch and chapter and chapter.batch_id != batch.pk:
            self.add_error(
                "chapter",
                "Choose a chapter belonging to the selected batch.",
            )

        # ----------------------------------------------------
        # SUBJECT / CHAPTER RELATIONSHIP
        # ----------------------------------------------------

        if subject and chapter and chapter.subject_id != subject.pk:
            self.add_error(
                "chapter",
                "Choose a chapter belonging to the selected subject.",
            )

        # ----------------------------------------------------
        # VERIFY THE TEACHER'S CURRENT ASSIGNMENTS
        # ----------------------------------------------------

        if batch and subject and selected_teacher:
            if selected_teacher.is_blocked:
                self.add_error(
                    "teacher",
                    "A blocked teacher cannot teach a live class.",
                )
            elif not selected_teacher.user.is_active:
                self.add_error(
                    "teacher",
                    "An inactive teacher cannot teach a live class.",
                )
            else:
                if not TeacherBatch.objects.filter(
                    teacher=selected_teacher,
                    batch=batch,
                    is_active=True,
                ).exists():
                    self.add_error(
                        "teacher",
                        "This teacher is not actively assigned to the batch.",
                    )

                if not TeacherSubject.objects.filter(
                    teacher=selected_teacher,
                    batch=batch,
                    subject=subject,
                    is_active=True,
                ).exists():
                    self.add_error(
                        "teacher",
                        "This teacher is not actively assigned to the subject.",
                    )

        # ----------------------------------------------------
        # TEACHER BOOKING PERMISSION
        # ----------------------------------------------------

        if not self.admin_mode and self.teacher_profile:
            if (
                selected_teacher
                and selected_teacher.pk != self.teacher_profile.pk
            ):
                self.add_error(
                    "teacher",
                    "You can only book a class using your own teacher account.",
                )

        # ----------------------------------------------------
        # FUTURE START AND DURATION
        # ----------------------------------------------------

        if class_date and start_time:
            start_datetime = timezone.make_aware(
                datetime.combine(class_date, start_time),
                timezone.get_current_timezone(),
            )

            if start_datetime <= timezone.now():
                self.add_error(
                    "start_time",
                    "The class start time must be in the future.",
                )

            if duration_minutes is not None:
                if duration_minutes not in ALLOWED_DURATIONS:
                    self.add_error(
                        "duration_minutes",
                        "Choose a duration of 1, 2 or 3 hours.",
                    )
                else:
                    end_datetime = start_datetime + timedelta(
                        minutes=duration_minutes,
                    )

                    if end_datetime <= start_datetime:
                        self.add_error(
                            "duration_minutes",
                            "The class end time must be after its start time.",
                        )

        return cleaned_data