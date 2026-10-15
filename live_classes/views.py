from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_POST

from admins.decorators import admin_required
from admins.models import Batch, Subject, Teacher, TeacherBatch, TeacherSubject

from .forms import LiveClassBookingForm
from .models import (
    CancellationRequest,
    CancellationStatus,
    LiveClass,
    LiveClassStatus,
)
from .services import (
    create_live_class,
    reschedule_live_class,
    request_live_class_cancellation,
    review_live_class_cancellation,
)


# ============================================================
# SHARED TIMETABLE CONFIGURATION
# ============================================================

BOOKING_WINDOW_DAYS = 7
FIRST_HOUR = 5
LAST_START_HOUR = 23
ALLOWED_DURATIONS = {60, 120, 180}
ALLOWED_BATCH_STATUSES = ("published", "archived")


def _local_datetime(class_date, start_time):
    """Build a timezone-aware datetime in the project's current timezone."""
    return timezone.make_aware(
        datetime.combine(class_date, start_time),
        timezone.get_current_timezone(),
    )


def _format_time(value):
    """Format a datetime as 5:00 AM without a leading zero."""
    return timezone.localtime(value).strftime("%I:%M %p").lstrip("0")


def _decorate_classes(classes, now):
    """Attach display-only local times and live-state flags to class objects."""
    for live_class in classes:
        live_class.local_start = timezone.localtime(live_class.start_at)
        live_class.local_end = timezone.localtime(live_class.end_at)
        live_class.time_range = (
            f"{_format_time(live_class.start_at)} – "
            f"{_format_time(live_class.end_at)}"
        )
        live_class.is_live = (
            live_class.status == LiveClassStatus.CONFIRMED
            and live_class.start_at <= now < live_class.end_at
        )
    return classes


def _booking_context(form, teacher=None):
    """Context shared by the Admin and Teacher booking templates."""
    today = timezone.localdate()
    return {
        "form": form,
        "today": today,
        "booking_start_date": today,
        "booking_end_date": today + timedelta(days=BOOKING_WINDOW_DAYS - 1),
        "booking_window_days": BOOKING_WINDOW_DAYS,
        "first_hour": FIRST_HOUR,
        "last_start_hour": LAST_START_HOUR,
        "teacher": teacher,
    }


def _get_reschedule_times(request):
    """Validate submitted reschedule fields; service validation remains final."""
    class_date = parse_date(request.POST.get("class_date", ""))
    start_time = parse_time(request.POST.get("start_time", ""))

    try:
        duration_minutes = int(request.POST.get("duration_minutes", ""))
    except (TypeError, ValueError):
        duration_minutes = None

    if class_date is None:
        raise ValidationError("Select a valid class date.")
    if start_time is None:
        raise ValidationError("Select a valid start time.")
    if start_time.minute != 0 or start_time.second != 0 or start_time.microsecond != 0:
        raise ValidationError("Classes must start on an hourly time slot.")
    if not FIRST_HOUR <= start_time.hour <= LAST_START_HOUR:
        raise ValidationError("Choose a start time between 5:00 AM and 11:00 PM.")
    if duration_minutes not in ALLOWED_DURATIONS:
        raise ValidationError("Choose a duration of 1, 2 or 3 hours.")

    start_at = _local_datetime(class_date, start_time)
    end_at = start_at + timedelta(minutes=duration_minutes)
    local_end = timezone.localtime(end_at)

    # Finishing exactly at midnight is allowed; continuing past midnight is not.
    midnight = timezone.make_aware(
        datetime.combine(class_date + timedelta(days=1), datetime.min.time()),
        timezone=timezone.get_current_timezone(),
    )
    if end_at > midnight:
        raise ValidationError(
            "A class must finish by midnight and cannot continue into the next day."
        )

    today = timezone.localdate()
    if not today <= class_date <= today + timedelta(days=BOOKING_WINDOW_DAYS - 1):
        raise ValidationError("Rescheduling is limited to today and the next six dates.")
    if start_at <= timezone.now():
        raise ValidationError("The class start time must be in the future.")

    return start_at, end_at


def _eligible_admin_filter_teachers(batch_id=None, subject_id=None):
    """Return only active teachers assigned to the selected batch/subject."""
    teachers = Teacher.objects.filter(
        is_blocked=False,
        user__is_active=True,
    )

    if not batch_id:
        return teachers.none()

    batch_teacher_ids = TeacherBatch.objects.filter(
        batch_id=batch_id,
        is_active=True,
    ).values_list("teacher_id", flat=True)

    subject_assignments = TeacherSubject.objects.filter(
        batch_id=batch_id,
        is_active=True,
        teacher_id__in=batch_teacher_ids,
    )

    if subject_id:
        subject_assignments = subject_assignments.filter(subject_id=subject_id)

    return (
        teachers.filter(
            pk__in=subject_assignments.values_list("teacher_id", flat=True)
        )
        .order_by("full_name", "pk")
        .distinct()
    )


def _calendar_days(start_date):
    return [
        {
            "date": start_date + timedelta(days=offset),
            "weekday": (start_date + timedelta(days=offset)).strftime("%a"),
        }
        for offset in range(BOOKING_WINDOW_DAYS)
    ]


def _build_calendar_rows(days, classes, now, selected_batch_id=None, all_week_classes=None):
    """
    Build one row per hourly start time from 5 AM through 11 PM.

    Batch availability is deliberately independent:
    - Only confirmed classes in selected_batch_id block a batch slot.
    - Classes in other batches never block this batch's slot.
    - Teacher conflicts are validated by create_live_class() on submission.
    - A multi-hour class is displayed only in its starting cell; its remaining
      occupied hours are marked Busy instead of rendering duplicate class cards.
    """
    current_tz = timezone.get_current_timezone()
    all_week_classes = (
        all_week_classes if all_week_classes is not None else classes
    )
    rows = []

    for hour in range(FIRST_HOUR, LAST_START_HOUR + 1):
        slot_time = datetime.min.time().replace(hour=hour)
        slot_label = datetime.combine(
            days[0]["date"], slot_time
        ).strftime("%I:%M %p").lstrip("0")
        row = {"label": slot_label, "cells": []}

        for day in days:
            cell_start = timezone.make_aware(
                datetime.combine(day["date"], slot_time),
                current_tz,
            )
            cell_end = cell_start + timedelta(hours=1)

            # Render the same class card in every hourly cell occupied by
            # the class. The end time is exclusive: a class from 11:00 AM
            # to 1:00 PM appears in the 11 AM and 12 PM cells, while the
            # 1 PM cell can be available for another class.
            cell_classes = []
            for item in classes:
                local_start = timezone.localtime(item.start_at)
                local_end = timezone.localtime(item.end_at)
                if (
                    local_start.date() == day["date"]
                    and local_start < cell_end
                    and local_end > cell_start
                ):
                    cell_classes.append(item)

            # Conflicts are calculated from the unfiltered schedule and are
            # scoped to the selected batch. A class in another batch is never
            # treated as a batch conflict here.
            # Only a confirmed class belonging to the selected batch blocks
            # this batch's slot. Other batches and cancelled/completed/no-show
            # classes must not make this slot appear Busy.
            batch_conflict = (
                selected_batch_id is not None
                and any(
                    item.batch_id == selected_batch_id
                    and item.status == LiveClassStatus.CONFIRMED
                    and item.start_at < cell_end
                    and item.end_at > cell_start
                    for item in all_week_classes
                )
            )

            is_past = cell_start <= now

            # A future slot is available only when the selected batch has no
            # confirmed class overlapping this hour. The service still performs
            # the authoritative conflict check when a booking is submitted.
            booking_today = timezone.localdate()
            booking_last_day = booking_today + timedelta(days=BOOKING_WINDOW_DAYS - 1)
            within_booking_window = booking_today <= day["date"] <= booking_last_day
            is_available = (
                selected_batch_id is not None
                and within_booking_window
                and not is_past
                and not batch_conflict
            )

            row["cells"].append({
                "date": day["date"],
                "time": slot_time,
                "label": slot_label,
                "classes": cell_classes,
                "past": is_past,
                "available": is_available,
                "occupied": batch_conflict,
                "busy": batch_conflict and not cell_classes,
                "batch_conflict": batch_conflict,
            })

        rows.append(row)

    return rows


# ============================================================
# TEACHER: MY TIMETABLE AND BOOKING
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_live_classes_view(request):
    teacher = getattr(request.user, "teacher_profile", None)

    if teacher is None:
        messages.error(request, "Access denied.")
        return redirect("teacher_login")

    if not request.user.is_active or teacher.is_blocked:
        messages.error(request, "Your account cannot access Live Classes.")
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    form = LiveClassBookingForm(request.POST or None, teacher=teacher)

    if request.method == "POST" and form.is_valid():
        class_date = form.cleaned_data["class_date"]
        start_time = form.cleaned_data["start_time"]
        duration_minutes = form.cleaned_data["duration_minutes"]
        start_at = _local_datetime(class_date, start_time)
        end_at = start_at + timedelta(minutes=duration_minutes)

        try:
            create_live_class(
                teacher=teacher,
                batch=form.cleaned_data["batch"],
                subject=form.cleaned_data["subject"],
                chapter=form.cleaned_data["chapter"],
                start_at=start_at,
                end_at=end_at,
                created_by=request.user,
            )
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        else:
            messages.success(request, "Live class booked successfully and confirmed.")
            return redirect("live_classes:teacher_live_classes")

    now = timezone.now()
    today = timezone.localdate()
    window_end_date = today + timedelta(days=BOOKING_WINDOW_DAYS)
    current_tz = timezone.get_current_timezone()
    window_start_at = timezone.make_aware(
        datetime.combine(today, datetime.min.time()), current_tz
    )
    window_end_at = timezone.make_aware(
        datetime.combine(window_end_date, datetime.min.time()), current_tz
    )

    teacher_classes = (
        LiveClass.objects.filter(teacher=teacher)
        .select_related("batch", "subject", "chapter", "teacher", "created_by")
        .order_by("start_at", "pk")
    )

    week_classes_qs = teacher_classes.filter(
        start_at__gte=window_start_at,
        start_at__lt=window_end_at,
    )
    timetable_classes = _decorate_classes(list(week_classes_qs), now)

    upcoming_classes = _decorate_classes(
        list(teacher_classes.filter(
            status=LiveClassStatus.CONFIRMED,
            end_at__gt=now,
        ).order_by("start_at", "pk")),
        now,
    )
    recent_classes = _decorate_classes(
        list(
            teacher_classes.exclude(
                status=LiveClassStatus.CONFIRMED,
                end_at__gt=now,
            ).order_by("-start_at", "-pk")[:12]
        ),
        now,
    )

    assigned_batch_ids = TeacherBatch.objects.filter(
        teacher=teacher,
        is_active=True,
    ).values_list("batch_id", flat=True)
    assigned_batches = Batch.objects.filter(
        pk__in=assigned_batch_ids,
        batch_status__in=ALLOWED_BATCH_STATUSES,
    ).order_by("batch_name", "pk")

    days = _calendar_days(today)
    rows = _build_calendar_rows(
        days,
        timetable_classes,
        now,
        all_week_classes=timetable_classes,
    )

    context = _booking_context(form, teacher)
    context.update({
        "upcoming_classes": upcoming_classes,
        "recent_classes": recent_classes,
        "timetable_classes": timetable_classes,
        "assigned_batches": assigned_batches,
        "calendar_days": days,
        "calendar_rows": rows,
        "week_start": today,
        "week_end": today + timedelta(days=BOOKING_WINDOW_DAYS - 1),
        "upcoming_count": len(upcoming_classes),
        "live_now_count": sum(1 for item in upcoming_classes if item.is_live),
        "now": now,
    })

    return render(request, "live_classes/teacher_live_classes.html", context)


# ============================================================
# ADMIN: LIVE SCHEDULE AND BOOKING
# ============================================================

def _admin_booking_options(request):
    """Return dependent choices for the admin booking form via this same URL."""
    from courses.models import CourseChapter

    option_type = request.GET.get("ajax", "").strip()
    batch_id = request.GET.get("batch_id", "").strip()
    subject_id = request.GET.get("subject_id", "").strip()

    if option_type == "subjects":
        if not batch_id.isdigit():
            return JsonResponse({"results": []})
        items = Subject.objects.filter(
            batch_id=int(batch_id),
            batch__batch_status__in=ALLOWED_BATCH_STATUSES,
            subject_status="published",
        ).order_by("subject_name", "pk")
        return JsonResponse({"results": [{"id": x.pk, "text": x.subject_name} for x in items]})

    if option_type == "chapters":
        if not batch_id.isdigit() or not subject_id.isdigit():
            return JsonResponse({"results": []})
        items = CourseChapter.objects.filter(
            batch_id=int(batch_id),
            subject_id=int(subject_id),
            batch__batch_status__in=ALLOWED_BATCH_STATUSES,
            subject__subject_status="published",
            status="published",
        ).order_by("chapter_order", "pk")
        return JsonResponse({"results": [{"id": x.pk, "text": x.chapter_name} for x in items]})

    if option_type == "teachers":
        if not batch_id.isdigit() or not subject_id.isdigit():
            return JsonResponse({"results": []})
        batch_teacher_ids = TeacherBatch.objects.filter(
            batch_id=int(batch_id), is_active=True
        ).values_list("teacher_id", flat=True)
        subject_teacher_ids = TeacherSubject.objects.filter(
            batch_id=int(batch_id),
            subject_id=int(subject_id),
            is_active=True,
        ).values_list("teacher_id", flat=True)
        eligible_ids = set(batch_teacher_ids).intersection(subject_teacher_ids)
        items = Teacher.objects.filter(
            pk__in=eligible_ids,
            is_blocked=False,
            user__is_active=True,
        ).order_by("full_name", "pk").distinct()
        return JsonResponse({"results": [{"id": x.pk, "text": x.full_name} for x in items]})

    return JsonResponse({"results": []}, status=400)


@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_live_schedule_view(request):
    today = timezone.localdate()
    now = timezone.now()
    current_tz = timezone.get_current_timezone()

    # Dependent dropdown requests reuse this URL; urls.py does not change.
    if request.method == "GET" and request.GET.get("ajax"):
        return _admin_booking_options(request)

    # Calendar navigation displays any requested seven-day period. Booking
    # dates remain restricted by the form and service validation.
    requested_week = parse_date(request.GET.get("week", ""))
    week_start = requested_week or today
    week_end_exclusive = week_start + timedelta(days=BOOKING_WINDOW_DAYS)
    week_start_at = timezone.make_aware(
        datetime.combine(week_start, datetime.min.time()), current_tz
    )
    week_end_at = timezone.make_aware(
        datetime.combine(week_end_exclusive, datetime.min.time()), current_tz
    )

    batches = Batch.objects.filter(
        batch_status__in=ALLOWED_BATCH_STATUSES,
    ).order_by("batch_name", "pk")

    # Filters are for the timetable only; they do not prefill or hide the
    # separate booking form. A selected calendar cell can prefill date/time.
    requested_batch = request.GET.get("batch", "").strip()

    # The timetable is batch-specific, never a combined "all batches" calendar.
    # On the first visit, select the first eligible batch so the user immediately
    # sees that batch's independent slots. An explicitly supplied valid batch
    # always takes precedence.
    requested_batch_id = (
        int(requested_batch)
        if requested_batch.isdigit()
        and batches.filter(pk=int(requested_batch)).exists()
        else None
    )
    selected_batch_id = requested_batch_id
    if selected_batch_id is None:
        selected_batch_id = batches.values_list("pk", flat=True).first()

    selected_batch = str(selected_batch_id) if selected_batch_id is not None else ""

    subjects = Subject.objects.none()
    if selected_batch_id is not None:
        subjects = Subject.objects.filter(
            batch_id=selected_batch_id,
            subject_status="published",
        ).order_by("subject_name", "pk")

    requested_subject = request.GET.get("subject", "").strip()
    selected_subject_id = (
        int(requested_subject)
        if requested_subject.isdigit() and subjects.filter(pk=int(requested_subject)).exists()
        else None
    )
    selected_subject = str(selected_subject_id) if selected_subject_id is not None else ""

    teachers = _eligible_admin_filter_teachers(
        selected_batch_id, selected_subject_id
    )
    requested_teacher = request.GET.get("teacher", "").strip()
    selected_teacher_id = (
        int(requested_teacher)
        if requested_teacher.isdigit() and teachers.filter(pk=int(requested_teacher)).exists()
        else None
    )
    selected_teacher = str(selected_teacher_id) if selected_teacher_id is not None else ""

    valid_statuses = {value for value, _label in LiveClassStatus.choices}
    selected_status = request.GET.get("status", "").strip()
    if selected_status not in valid_statuses:
        selected_status = ""

    # The timetable filter and booking form are independent.
    # A clicked calendar slot may prefill only its date and start time.
    # Do not preselect the booking form's batch from the timetable filter.
    initial = {}

    requested_date = parse_date(request.GET.get("class_date", ""))
    requested_time = parse_time(request.GET.get("start_time", ""))
    if requested_date and today <= requested_date <= today + timedelta(days=BOOKING_WINDOW_DAYS - 1):
        initial["class_date"] = requested_date
    if requested_time and requested_time.minute == 0 and requested_time.second == 0:
        initial["start_time"] = requested_time

    form = LiveClassBookingForm(
        request.POST or None,
        initial=initial if request.method == "GET" else None,
        admin_mode=True,
    )

    if request.method == "POST" and form.is_valid():
        class_date = form.cleaned_data["class_date"]
        start_time = form.cleaned_data["start_time"]
        duration_minutes = form.cleaned_data["duration_minutes"]
        start_at = _local_datetime(class_date, start_time)
        end_at = start_at + timedelta(minutes=duration_minutes)

        try:
            create_live_class(
                teacher=form.cleaned_data["teacher"],
                batch=form.cleaned_data["batch"],
                subject=form.cleaned_data["subject"],
                chapter=form.cleaned_data["chapter"],
                start_at=start_at,
                end_at=end_at,
                created_by=request.user,
            )
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        else:
            messages.success(request, "Live class booked successfully and confirmed.")
            return redirect("live_classes:admin_live_schedule")

    # Query the complete seven-day schedule before applying filters. This
    # separate list is used to calculate batch conflicts correctly.
    all_week_classes = list(
        LiveClass.objects.filter(
            start_at__gte=week_start_at,
            start_at__lt=week_end_at,
        )
        .select_related("batch", "subject", "chapter", "teacher", "created_by")
        .order_by("start_at", "pk")
    )
    _decorate_classes(all_week_classes, now)

    classes_qs = LiveClass.objects.filter(
        start_at__gte=week_start_at,
        start_at__lt=week_end_at,
    ).select_related("batch", "subject", "chapter", "teacher", "created_by")

    if selected_batch_id is not None:
        classes_qs = classes_qs.filter(batch_id=selected_batch_id)
    if selected_subject_id is not None:
        classes_qs = classes_qs.filter(subject_id=selected_subject_id)
    if selected_teacher_id is not None:
        classes_qs = classes_qs.filter(teacher_id=selected_teacher_id)
    if selected_status:
        classes_qs = classes_qs.filter(status=selected_status)

    visible_classes = _decorate_classes(
        list(classes_qs.order_by("start_at", "pk")), now
    )

    filtered_ids = [item.pk for item in visible_classes]
    filtered_queryset = LiveClass.objects.filter(pk__in=filtered_ids)
    confirmed = filtered_queryset.filter(status=LiveClassStatus.CONFIRMED)

    upcoming_count = confirmed.filter(start_at__gte=now).count()
    live_now_count = confirmed.filter(start_at__lte=now, end_at__gt=now).count()
    completed_count = filtered_queryset.filter(status=LiveClassStatus.COMPLETED).count()
    cancelled_count = filtered_queryset.filter(status=LiveClassStatus.CANCELLED).count()

    # The calendar headings/cells must use the navigated week, not today.
    # The class query above already uses week_start.
    days = _calendar_days(week_start)
    rows = _build_calendar_rows(
        days,
        visible_classes,
        now,
        selected_batch_id=selected_batch_id,
        all_week_classes=all_week_classes,
    )

    pending_cancellation_requests = (
        CancellationRequest.objects.filter(status=CancellationStatus.PENDING)
        .select_related(
            "live_class",
            "live_class__batch",
            "live_class__subject",
            "live_class__teacher",
            "requested_by",
        )
        .order_by("requested_at", "pk")
    )

    context = _booking_context(form)
    context.update({
        "classes": visible_classes,
        "batches": batches,
        "subjects": subjects,
        "teachers": teachers,
        "selected_batch": selected_batch,
        "selected_subject": selected_subject,
        "selected_teacher": selected_teacher,
        "selected_status": selected_status,
        "selected_date": week_start,
        "week_start": week_start,
        "week_end": week_start + timedelta(days=BOOKING_WINDOW_DAYS - 1),
        "previous_week": week_start - timedelta(days=BOOKING_WINDOW_DAYS),
        "next_week": week_start + timedelta(days=BOOKING_WINDOW_DAYS),
        "week_classes_count": len(visible_classes),
        "upcoming_count": upcoming_count,
        "live_now_count": live_now_count,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "calendar_days": days,
        "calendar_rows": rows,
        "now": now,
        "pending_cancellation_requests": pending_cancellation_requests,
    })

    return render(request, "admins/live_classes/live_schedule.html", context)


# ============================================================
# TEACHER: RESCHEDULE AND CANCELLATION REQUEST
# ============================================================

@login_required(login_url="teacher_login")
@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_reschedule_live_class_view(request, class_id):
    teacher = getattr(request.user, "teacher_profile", None)

    if teacher is None or not request.user.is_active or teacher.is_blocked:
        messages.error(request, "You cannot reschedule this class.")
        return redirect("teacher_login")
    if teacher.is_first_login:
        return redirect("teacher_change_password")

    try:
        start_at, end_at = _get_reschedule_times(request)
        reschedule_live_class(
            live_class_id=class_id,
            start_at=start_at,
            end_at=end_at,
            updated_by=request.user,
            teacher=teacher,
        )
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
    else:
        messages.success(request, "Live class rescheduled successfully.")

    return redirect("live_classes:teacher_live_classes")


@login_required(login_url="teacher_login")
@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_request_live_class_cancellation_view(request, class_id):
    teacher = getattr(request.user, "teacher_profile", None)

    if teacher is None or not request.user.is_active or teacher.is_blocked:
        messages.error(request, "You cannot request this cancellation.")
        return redirect("teacher_login")
    if teacher.is_first_login:
        return redirect("teacher_change_password")

    reason = request.POST.get("reason", "").strip()
    try:
        request_live_class_cancellation(
            live_class_id=class_id,
            teacher=teacher,
            reason=reason,
        )
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
    else:
        messages.success(request, "Cancellation request submitted for Admin review.")

    return redirect("live_classes:teacher_live_classes")


# ============================================================
# ADMIN: RESCHEDULE AND REVIEW CANCELLATION
# ============================================================

@admin_required
@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_reschedule_live_class_view(request, class_id):
    try:
        start_at, end_at = _get_reschedule_times(request)
        reschedule_live_class(
            live_class_id=class_id,
            start_at=start_at,
            end_at=end_at,
            updated_by=request.user,
        )
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
    else:
        messages.success(request, "Live class rescheduled successfully.")

    return redirect("live_classes:admin_live_schedule")


@admin_required
@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_review_cancellation_view(request, request_id):
    decision = request.POST.get("decision", "").strip().lower()
    if decision not in {"approve", "reject"}:
        messages.error(request, "Choose approve or reject.")
        return redirect("live_classes:admin_live_schedule")

    try:
        review_live_class_cancellation(
            request_id=request_id,
            reviewed_by=request.user,
            approve=(decision == "approve"),
            review_note=request.POST.get("review_note", "").strip(),
        )
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
    else:
        messages.success(
            request,
            "Cancellation approved and class cancelled."
            if decision == "approve"
            else "Cancellation request rejected.",
        )

    return redirect("live_classes:admin_live_schedule")