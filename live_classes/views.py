from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_POST
from courses.models import CourseChapter
from admins.decorators import admin_required
from admins.models import Batch, Subject, Teacher, TeacherBatch, TeacherSubject
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.core.paginator import Paginator
from .forms import LiveClassBookingForm
from .models import (CancellationRequest,CancellationStatus,LiveClass,LiveClassStatus,)
from .services import (create_live_class,reschedule_live_class,cancel_live_class,request_live_class_cancellation,review_live_class_cancellation,)

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
    """Attach display-only local times, duration and live-state flags."""
    for live_class in classes:
        live_class.local_start = timezone.localtime(live_class.start_at)
        live_class.local_end = timezone.localtime(live_class.end_at)

        live_class.time_range = (
            f"{_format_time(live_class.start_at)} – "
            f"{_format_time(live_class.end_at)}"
        )

        live_class.duration_minutes = int(
            (live_class.end_at - live_class.start_at).total_seconds() // 60
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
    """
    Teacher timetable and booking page.

    The timetable is filtered to one batch at a time, but displays every
    confirmed/previous class in that batch so a teacher can see slots occupied
    by colleagues. Booking permissions remain enforced by LiveClassBookingForm
    and create_live_class().
    """
    teacher = getattr(request.user, "teacher_profile", None)

    if teacher is None:
        messages.error(request, "Access denied.")
        return redirect("teacher_login")

    if not request.user.is_active or teacher.is_blocked:
        messages.error(request, "Your account cannot access Live Classes.")
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    today = timezone.localdate()
    now = timezone.now()
    current_tz = timezone.get_current_timezone()

    # Teacher-only dependent dropdown data. Reuse this view URL so no route
    # changes are needed; every option is restricted to active assignments.
    if request.method == "GET" and request.GET.get("ajax"):
        from courses.models import CourseChapter

        option_type = request.GET.get("ajax", "").strip()
        batch_id = request.GET.get("batch_id", "").strip()
        subject_id = request.GET.get("subject_id", "").strip()

        if not batch_id.isdigit():
            return JsonResponse({"results": []})

        assigned_batch = Batch.objects.filter(
            pk=int(batch_id),
            batch_status__in=ALLOWED_BATCH_STATUSES,
        ).exists() and TeacherBatch.objects.filter(
            teacher=teacher,
            batch_id=int(batch_id),
            is_active=True,
        ).exists()
        if not assigned_batch:
            return JsonResponse({"results": []})

        if option_type == "subjects":
            assigned_subject_ids = TeacherSubject.objects.filter(
                teacher=teacher,
                batch_id=int(batch_id),
                is_active=True,
            ).values_list("subject_id", flat=True)
            items = Subject.objects.filter(
                pk__in=assigned_subject_ids,
                batch_id=int(batch_id),
                subject_status="published",
            ).order_by("subject_name", "pk")
            return JsonResponse({"results": [
                {"id": item.pk, "text": item.subject_name} for item in items
            ]})

        if option_type == "chapters":
            if not subject_id.isdigit():
                return JsonResponse({"results": []})
            assigned_subject = Subject.objects.filter(
                pk=int(subject_id),
                batch_id=int(batch_id),
                subject_status="published",
            ).exists() and TeacherSubject.objects.filter(
                teacher=teacher,
                batch_id=int(batch_id),
                subject_id=int(subject_id),
                is_active=True,
            ).exists()
            if not assigned_subject:
                return JsonResponse({"results": []})
            items = CourseChapter.objects.filter(
                batch_id=int(batch_id),
                subject_id=int(subject_id),
                status="published",
            ).order_by("chapter_order", "pk")
            return JsonResponse({"results": [
                {"id": item.pk, "text": item.chapter_name} for item in items
            ]})

        return JsonResponse({"results": []}, status=400)

    # Keep the booking form independent from the timetable batch filter.
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
        teacher=teacher,
    )

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

    assigned_batch_ids = TeacherBatch.objects.filter(
        teacher=teacher,
        is_active=True,
    ).values_list("batch_id", flat=True)

    assigned_batches = Batch.objects.filter(
        pk__in=assigned_batch_ids,
        batch_status__in=ALLOWED_BATCH_STATUSES,
    ).order_by("batch_name", "pk")

    requested_batch = request.GET.get("batch", "").strip()
    selected_batch_id = (
        int(requested_batch)
        if requested_batch.isdigit()
        and assigned_batches.filter(pk=int(requested_batch)).exists()
        else assigned_batches.values_list("pk", flat=True).first()
    )
    selected_batch = str(selected_batch_id) if selected_batch_id is not None else ""

    # Week navigation is display-only. Actual booking remains restricted to
    # today and the next six dates by the form and service validators.
    requested_week = parse_date(request.GET.get("week", ""))
    week_start = requested_week or today
    week_end_exclusive = week_start + timedelta(days=BOOKING_WINDOW_DAYS)

    week_start_at = timezone.make_aware(
        datetime.combine(week_start, datetime.min.time()), current_tz
    )
    week_end_at = timezone.make_aware(
        datetime.combine(week_end_exclusive, datetime.min.time()), current_tz
    )

    # This teacher's own classes are used for upcoming/history lists and
    # for deciding which timetable cards may show teacher actions.
    teacher_classes = (
        LiveClass.objects.filter(teacher=teacher)
        .select_related("batch", "subject", "chapter", "teacher", "created_by")
        .order_by("start_at", "pk")
    )

    # The calendar must load the whole selected batch's schedule, not only
    # this teacher's classes, otherwise another teacher's booking looks free.
    all_week_classes = []
    visible_classes = []
    if selected_batch_id is not None:
        all_week_classes = list(
            LiveClass.objects.filter(
                batch_id=selected_batch_id,
                start_at__lt=week_end_at,
                end_at__gt=week_start_at,
            )
            .select_related("batch", "subject", "chapter", "teacher", "created_by")
            .order_by("start_at", "pk")
        )
        visible_classes = all_week_classes
    _decorate_classes(all_week_classes, now)
    _decorate_classes(visible_classes, now)

    upcoming_classes = _decorate_classes(
        list(
            teacher_classes.filter(
                status=LiveClassStatus.CONFIRMED,
                end_at__gt=now,
            ).order_by("start_at", "pk")
        ),
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

    confirmed = [item for item in visible_classes if item.status == LiveClassStatus.CONFIRMED]
    upcoming_count = sum(1 for item in confirmed if item.start_at > now)
    live_now_count = sum(1 for item in confirmed if item.start_at <= now < item.end_at)
    completed_count = sum(1 for item in visible_classes if item.status == LiveClassStatus.COMPLETED)
    cancelled_count = sum(1 for item in visible_classes if item.status == LiveClassStatus.CANCELLED)

    days = _calendar_days(week_start)
    rows = _build_calendar_rows(
        days,
        visible_classes,
        now,
        selected_batch_id=selected_batch_id,
        all_week_classes=all_week_classes,
    )

    context = _booking_context(form, teacher)
    context.update({
        "upcoming_classes": upcoming_classes,
        "recent_classes": recent_classes,
        "timetable_classes": visible_classes,
        "assigned_batches": assigned_batches,
        "batches": assigned_batches,
        "selected_batch": selected_batch,
        "calendar_days": days,
        "calendar_rows": rows,
        "week_start": week_start,
        "week_end": week_start + timedelta(days=BOOKING_WINDOW_DAYS - 1),
        "previous_week": week_start - timedelta(days=BOOKING_WINDOW_DAYS),
        "next_week": week_start + timedelta(days=BOOKING_WINDOW_DAYS),
        "week_classes_count": len(visible_classes),
        "upcoming_count": upcoming_count,
        "live_now_count": live_now_count,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "now": now,
    })

    return render(request, "live_classes/teacher_live_classes.html", context)


# ============================================================
# TEACHER: UPCOMING LIVE CLASSES
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_upcoming_classes_view(request):
    """
    Show this Teacher's confirmed future classes with batch/subject/search
    filters and server-side pagination (20 classes per page).
    """
    teacher = getattr(request.user, "teacher_profile", None)

    if teacher is None:
        messages.error(request, "Access denied.")
        return redirect("teacher_login")

    if not request.user.is_active or teacher.is_blocked:
        messages.error(request, "Your account cannot access Live Classes.")
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    now = timezone.now()
    today = timezone.localdate()

    # Only batches actively assigned to this teacher are available as filters.
    assigned_batch_ids = TeacherBatch.objects.filter(
        teacher=teacher,
        is_active=True,
    ).values_list("batch_id", flat=True)

    batches = Batch.objects.filter(
        pk__in=assigned_batch_ids,
        batch_status__in=ALLOWED_BATCH_STATUSES,
    ).order_by("batch_name", "pk")

    batch_value = request.GET.get("batch", "").strip()
    selected_batch = ""
    if batch_value.isdigit() and batches.filter(pk=int(batch_value)).exists():
        selected_batch = batch_value

    # Subjects are restricted to active TeacherSubject assignments and,
    # when a batch is selected, to that batch only.
    assigned_subject_ids = TeacherSubject.objects.filter(
        teacher=teacher,
        is_active=True,
    ).values_list("subject_id", flat=True)

    subjects = Subject.objects.filter(
        pk__in=assigned_subject_ids,
        subject_status="published",
        batch__batch_status__in=ALLOWED_BATCH_STATUSES,
    )
    if selected_batch:
        subjects = subjects.filter(batch_id=int(selected_batch))
    subjects = subjects.order_by("subject_name", "pk")

    subject_value = request.GET.get("subject", "").strip()
    selected_subject = ""
    if subject_value.isdigit() and subjects.filter(pk=int(subject_value)).exists():
        selected_subject = subject_value

    # Detect pending cancellation requests without changing the LiveClass model.
    # The class remains confirmed and visible until an Admin approves the request.
    pending_cancellation_requests = CancellationRequest.objects.filter(
        live_class_id=OuterRef("pk"),
        status=CancellationStatus.PENDING,
    )

    # Base queryset: only this teacher's confirmed classes that have not started.
    # has_pending_cancellation is consumed by the Upcoming Classes card template.
    classes = (
        LiveClass.objects.filter(
            teacher=teacher,
            status=LiveClassStatus.CONFIRMED,
            actual_start_at__isnull=True,
            actual_end_at__isnull=True,
            start_at__gt=now + timedelta(minutes=5),
        )
        .annotate(
            has_pending_cancellation=Exists(pending_cancellation_requests)
        )
        .select_related("batch", "subject", "chapter", "teacher")
    )

    if selected_batch:
        classes = classes.filter(batch_id=int(selected_batch))

    if selected_subject:
        classes = classes.filter(subject_id=int(selected_subject))

    search_query = request.GET.get("search", "").strip()
    if search_query:
        classes = classes.filter(
            Q(batch__batch_name__icontains=search_query)
            | Q(subject__subject_name__icontains=search_query)
            | Q(chapter__chapter_name__icontains=search_query)
        )

    # Date filtering is performed in the database before pagination,
    # so it searches every upcoming class, not only the visible 20 cards.
    date_value = request.GET.get("date", "").strip()
    selected_date = parse_date(date_value)
    if selected_date:
        local_start = timezone.make_aware(
            datetime.combine(selected_date, datetime.min.time()),
            timezone.get_current_timezone(),
        )
        local_end = local_start + timedelta(days=1)
        classes = classes.filter(
            start_at__gte=local_start,
            start_at__lt=local_end,
        )

    classes = classes.order_by("start_at", "pk")

    # Header statistics are calculated from the database, not hardcoded.
    # "This week" means upcoming confirmed classes from today through Sunday.
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    week_start_at = timezone.make_aware(
        datetime.combine(week_start, datetime.min.time()),
        timezone.get_current_timezone(),
    )
    week_end_at = timezone.make_aware(
        datetime.combine(week_end, datetime.min.time()),
        timezone.get_current_timezone(),
    )

    this_week_count = LiveClass.objects.filter(
        teacher=teacher,
        status=LiveClassStatus.CONFIRMED,
        actual_start_at__isnull=True,
        actual_end_at__isnull=True,
        start_at__gt=now + timedelta(minutes=5),
        start_at__gte=week_start_at,
        start_at__lt=week_end_at,
    ).count()

    live_now_count = LiveClass.objects.filter(
        teacher=teacher,
        status=LiveClassStatus.CONFIRMED,
        start_at__lte=now,
        end_at__gt=now,
    ).count()

    # 20 per page; get_page() safely handles invalid/out-of-range page values.
    paginator = Paginator(classes, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    upcoming_classes = list(page_obj.object_list)
    _decorate_classes(upcoming_classes, now)

    # Available hourly values for the reschedule popup. The service remains
    # the authoritative validator for booking window and schedule conflicts.
    reschedule_time_options = []
    for hour in range(FIRST_HOUR, LAST_START_HOUR + 1):
        value = f"{hour:02d}:00"
        label = datetime.strptime(value, "%H:%M").strftime("%I:%M %p").lstrip("0")
        reschedule_time_options.append((value, label))

    # Preserve active filters while changing pagination pages.
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    pagination_query = pagination_params.urlencode()

    context = {
        "teacher": teacher,
        "upcoming_classes": upcoming_classes,
        "page_obj": page_obj,
        "paginator": paginator,
        "upcoming_count": paginator.count,
        "this_week_count": this_week_count,
        "live_now_count": live_now_count,
        "batches": batches,
        "subjects": subjects,
        "selected_batch": selected_batch,
        "selected_subject": selected_subject,
        "search_query": search_query,
        "selected_date": selected_date,
        "pagination_query": pagination_query,
        "reschedule_time_options": reschedule_time_options,
        "now": now,
    }

    return render(
        request,
        "live_classes/teacher_upcoming_classes.html",
        context,
    )


# ============================================================
# TEACHER: LIVE NOW DASHBOARD
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_live_now_view(request):
    """Show only this teacher's classes inside the five-minute start window or already running."""
    teacher = getattr(request.user, "teacher_profile", None)
    if teacher is None:
        messages.error(request, "Access denied.")
        return redirect("teacher_login")
    if not request.user.is_active or teacher.is_blocked:
        messages.error(request, "Your account cannot access Live Classes.")
        return redirect("teacher_login")
    if teacher.is_first_login:
        return redirect("teacher_change_password")

    now = timezone.now()
    today = timezone.localdate()
    day_start = timezone.make_aware(
        datetime.combine(today, datetime.min.time()),
        timezone.get_current_timezone(),
    )
    day_end = day_start + timedelta(days=1)

    # Filter dropdowns are limited to this teacher's active assignments.
    assigned_batch_ids = TeacherBatch.objects.filter(
        teacher=teacher, is_active=True
    ).values_list("batch_id", flat=True)
    batches = Batch.objects.filter(
        pk__in=assigned_batch_ids,
        batch_status__in=ALLOWED_BATCH_STATUSES,
    ).order_by("batch_name", "pk")

    assigned_subject_ids = TeacherSubject.objects.filter(
        teacher=teacher, is_active=True
    ).values_list("subject_id", flat=True)
    subjects = Subject.objects.filter(
        pk__in=assigned_subject_ids,
        subject_status="published",
        batch__batch_status__in=ALLOWED_BATCH_STATUSES,
    ).order_by("subject_name", "pk")

    search_query = request.GET.get("search", "").strip()
    batch_value = request.GET.get("batch", "").strip()
    subject_value = request.GET.get("subject", "").strip()
    selected_batch = ""
    selected_subject = ""
    if batch_value.isdigit() and batches.filter(pk=int(batch_value)).exists():
        selected_batch = batch_value
        subjects = subjects.filter(batch_id=int(batch_value))
    if subject_value.isdigit() and subjects.filter(pk=int(subject_value)).exists():
        selected_subject = subject_value

    today_classes = LiveClass.objects.filter(
        teacher=teacher,
        status__in=[LiveClassStatus.CONFIRMED, LiveClassStatus.COMPLETED],
        start_at__gte=day_start,
        start_at__lt=day_end,
    )
    live_base = today_classes.filter(
        status=LiveClassStatus.CONFIRMED,
        actual_start_at__isnull=False,
        actual_end_at__isnull=True,
    )
    can_start_base = today_classes.filter(
        status=LiveClassStatus.CONFIRMED,
        actual_start_at__isnull=True,
        actual_end_at__isnull=True,
        start_at__lte=now + timedelta(minutes=5),
        end_at__gt=now,
    )
    completed_today = today_classes.filter(
        actual_end_at__gte=day_start,
        actual_end_at__lt=day_end,
    )

    # A class moves from Upcoming to Live Now at exactly T-5 minutes.
    # Once started, it remains visible until its actual end is recorded.
    classes = today_classes.filter(
        status=LiveClassStatus.CONFIRMED,
        actual_end_at__isnull=True,
    ).filter(
        Q(actual_start_at__isnull=False)
        | Q(
            actual_start_at__isnull=True,
            start_at__lte=now + timedelta(minutes=5),
            end_at__gt=now,
        )
    ).select_related("batch", "subject", "chapter", "teacher")

    if selected_batch:
        classes = classes.filter(batch_id=int(selected_batch))
    if selected_subject:
        classes = classes.filter(subject_id=int(selected_subject))
    if search_query:
        classes = classes.filter(
            Q(batch__batch_name__icontains=search_query)
            | Q(subject__subject_name__icontains=search_query)
            | Q(chapter__chapter_name__icontains=search_query)
        )

    classes = classes.order_by("start_at", "pk")
    paginator = Paginator(classes, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    live_now_classes = list(page_obj.object_list)

    for item in live_now_classes:
        item.local_start = timezone.localtime(item.start_at)
        item.local_end = timezone.localtime(item.end_at)
        item.time_range = f"{_format_time(item.start_at)} – {_format_time(item.end_at)}"
        item.duration_minutes = int((item.end_at - item.start_at).total_seconds() // 60)
        item.is_live_now = bool(item.actual_start_at and not item.actual_end_at)
        item.can_start_now = bool(
            not item.actual_start_at
            and not item.actual_end_at
            and item.start_at <= now + timedelta(minutes=5)
            and item.end_at > now
        )
        item.start_window_opens_at = item.start_at - timedelta(minutes=5)
        item.seconds_until_start_window = max(
            0, int((item.start_window_opens_at - now).total_seconds())
        )
        item.actual_elapsed_seconds = (
            max(0, int((now - item.actual_start_at).total_seconds()))
            if item.is_live_now else 0
        )

    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    context = {
        "teacher": teacher,
        "live_now_classes": live_now_classes,
        "page_obj": page_obj,
        "paginator": paginator,
        "today_classes_count": today_classes.count(),
        "live_now_count": live_base.count(),
        "can_start_now_count": can_start_base.count(),
        "completed_today_count": completed_today.count(),
        "batches": batches,
        "subjects": subjects,
        "selected_batch": selected_batch,
        "selected_subject": selected_subject,
        "search_query": search_query,
        "pagination_query": pagination_params.urlencode(),
        "now": now,
    }
    return render(request, "live_classes/teacher_live_now.html", context)


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
# ADMIN: UPCOMING LIVE CLASSES
# ============================================================

@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_upcoming_classes_view(request):
    """
    Separate Admin Upcoming Classes page.

    Shows confirmed future classes with filters, search
    and pagination. Does not change the timetable page.
    """

    now = timezone.now()
    today = timezone.localdate()

    classes = (
        LiveClass.objects
        .filter(
            status=LiveClassStatus.CONFIRMED,
            actual_start_at__isnull=True,
            start_at__gt=now + timedelta(minutes=5),
        )
        .select_related(
            "batch",
            "subject",
            "chapter",
            "teacher",
        )
        .order_by("start_at", "pk")
    )

    # -----------------------------
    # Read filters
    # -----------------------------

    search_query = request.GET.get("q", "").strip()
    batch_value = request.GET.get("batch", "").strip()
    subject_value = request.GET.get("subject", "").strip()
    teacher_value = request.GET.get("teacher", "").strip()
    chapter_value = request.GET.get("chapter", "").strip()
    date_value = request.GET.get("date", "").strip()

    # -----------------------------
    # Search
    # -----------------------------

    if search_query:
        classes = classes.filter(
            Q(batch__batch_name__icontains=search_query)
            | Q(subject__subject_name__icontains=search_query)
            | Q(chapter__chapter_name__icontains=search_query)
            | Q(teacher__full_name__icontains=search_query)
        )

    # -----------------------------
    # Batch filter
    # -----------------------------

    if batch_value.isdigit():
        classes = classes.filter(batch_id=int(batch_value))

    # -----------------------------
    # Subject filter
    # -----------------------------

    if subject_value.isdigit():
        classes = classes.filter(subject_id=int(subject_value))

    # -----------------------------
    # Teacher filter
    # -----------------------------

    if teacher_value.isdigit():
        classes = classes.filter(teacher_id=int(teacher_value))

    # -----------------------------
    # Chapter filter
    # -----------------------------

    if chapter_value.isdigit():
        classes = classes.filter(chapter_id=int(chapter_value))

    # -----------------------------
    # Date filter
    # -----------------------------

    selected_date = parse_date(date_value)

    if selected_date:
        local_start = timezone.make_aware(
            datetime.combine(selected_date, datetime.min.time()),
            timezone.get_current_timezone(),
        )

        local_end = local_start + timedelta(days=1)

        classes = classes.filter(
            start_at__gte=local_start,
            start_at__lt=local_end,
        )

    # -----------------------------
    # Filter dropdown data
    # -----------------------------

    upcoming_base = (
        LiveClass.objects
        .filter(
            status=LiveClassStatus.CONFIRMED,
            actual_start_at__isnull=True,
            start_at__gt=now + timedelta(minutes=5),
        )
    )

    batches = (
        Batch.objects
        .filter(
            pk__in=upcoming_base.values_list("batch_id", flat=True)
        )
        .order_by("batch_name", "pk")
    )

    teachers = (
        Teacher.objects
        .filter(
            pk__in=upcoming_base.values_list("teacher_id", flat=True)
        )
        .order_by("full_name", "pk")
    )

    subjects = Subject.objects.filter(
        pk__in=upcoming_base.values_list("subject_id", flat=True)
    )

    if batch_value.isdigit():
        subjects = subjects.filter(batch_id=int(batch_value))

    subjects = subjects.order_by("subject_name", "pk")

    chapters = CourseChapter.objects.filter(
        pk__in=upcoming_base.values_list("chapter_id", flat=True)
    )

    if batch_value.isdigit():
        chapters = chapters.filter(batch_id=int(batch_value))

    if subject_value.isdigit():
        chapters = chapters.filter(subject_id=int(subject_value))

    chapters = chapters.order_by("chapter_order", "pk")

    # -----------------------------
    # Pagination
    # -----------------------------

    paginator = Paginator(classes, 20)

    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    upcoming_classes = list(page_obj.object_list)
    _decorate_classes(upcoming_classes, now)

    context = {
        "upcoming_classes": upcoming_classes,
        "page_obj": page_obj,
        "paginator": paginator,

        "batches": batches,
        "teachers": teachers,
        "subjects": subjects,
        "chapters": chapters,

        "search_query": search_query,
        "selected_batch": batch_value,
        "selected_subject": subject_value,
        "selected_teacher": teacher_value,
        "selected_chapter": chapter_value,
        "selected_date": selected_date,

        "today": today,
        "booking_end_date": today + timedelta(days=BOOKING_WINDOW_DAYS - 1),
        "now": now,
        "upcoming_count": paginator.count,
    }

    return render(
        request,
        "admins/live_classes/admin_upcoming_classes.html",
        context,
    )


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

    # A pending cancellation request locks rescheduling until Admin reviews it.
    # Rejected requests no longer match PENDING, so rescheduling becomes available
    # again; approved requests cancel the class and cannot be rescheduled.
    has_pending_cancellation = CancellationRequest.objects.filter(
        live_class_id=class_id,
        requested_by=teacher,
        status=CancellationStatus.PENDING,
    ).exists()
    if has_pending_cancellation:
        messages.error(
            request,
            "This class cannot be rescheduled while its cancellation request is pending Admin review.",
        )
        return redirect("live_classes:teacher_upcoming_classes")

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

    return redirect("live_classes:teacher_upcoming_classes")


# ============================================================
# ADMIN: DIRECTLY CANCEL A LIVE CLASS
# ============================================================

@admin_required
@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_cancel_live_class_view(request, class_id):

    entered_batch_name = request.POST.get(
        "batch_name_confirmation", ""
    ).strip()

    live_class = (
        LiveClass.objects
        .select_related("batch")
        .filter(pk=class_id)
        .first()
    )

    if live_class is None:
        messages.error(request, "The requested live class was not found.")
        return redirect("live_classes:admin_upcoming_classes")

    actual_batch_name = live_class.batch.batch_name

    # Require the exact batch name before cancellation.
    if entered_batch_name != actual_batch_name:
        messages.error(
            request,
            "Batch name does not match. Live class was not cancelled."
        )
        return redirect("live_classes:admin_upcoming_classes")

    try:
        cancel_live_class(
            live_class_id=class_id,
            cancelled_by=request.user,
        )

    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)

    else:
        messages.success(
            request,
            "Live class cancelled successfully."
        )

    return redirect("live_classes:admin_upcoming_classes")

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

    # Validate the submitted reason on the server as well as in the browser.
    # Never rely on HTML maxlength because a request can be submitted manually.
    reason = request.POST.get("reason", "")
    trimmed_reason = reason.strip()

    if not trimmed_reason:
        messages.error(
            request,
            "Please fill in the cancellation reason field before submitting.",
        )
        return redirect(
            f"{reverse('live_classes:teacher_upcoming_classes')}?open_cancel={class_id}"
        )

    if len(reason) > 250:
        messages.error(
            request,
            "Cancellation reason cannot exceed 250 characters. "
            "Please shorten your reason and try again.",
        )
        return redirect(
            f"{reverse('live_classes:teacher_upcoming_classes')}?open_cancel={class_id}"
        )

    try:
        request_live_class_cancellation(
            live_class_id=class_id,
            teacher=teacher,
            reason=trimmed_reason,
        )
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
        return redirect(
            f"{reverse('live_classes:teacher_upcoming_classes')}?open_cancel={class_id}"
        )
    else:
        messages.success(
            request,
            "Cancellation request submitted for Admin review.",
        )

    return redirect("live_classes:teacher_upcoming_classes")


# ============================================================
# TEACHER: CANCELLATION REQUEST HISTORY
# ============================================================

@login_required(login_url="teacher_login")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_cancellation_requests_view(request):
    """Show this Teacher's cancellation requests with filters and 20-item pagination."""

    teacher = getattr(request.user, "teacher_profile", None)

    if teacher is None:
        messages.error(request, "Access denied.")
        return redirect("teacher_login")

    if not request.user.is_active or teacher.is_blocked:
        messages.error(
            request,
            "Your account cannot access cancellation request history.",
        )
        return redirect("teacher_login")

    if teacher.is_first_login:
        return redirect("teacher_change_password")

    # Base queryset is always limited to the logged-in teacher's own requests.
    base_requests = (
        CancellationRequest.objects
        .filter(requested_by=teacher)
        .select_related(
            "live_class",
            "live_class__batch",
            "live_class__subject",
            "live_class__chapter",
            "live_class__teacher",
            "reviewed_by",
        )
        .order_by("-requested_at", "-pk")
    )

    # Summary counts remain totals for this teacher, independent of active filters.
    pending_count = base_requests.filter(
        status=CancellationStatus.PENDING
    ).count()
    approved_count = base_requests.filter(
        status=CancellationStatus.APPROVED
    ).count()
    rejected_count = base_requests.filter(
        status=CancellationStatus.REJECTED
    ).count()

    # Read and validate filter values against this teacher's own request records.
    batch_value = request.GET.get("batch", "").strip()
    subject_value = request.GET.get("subject", "").strip()
    date_value = request.GET.get("date", "").strip()
    status_value = request.GET.get("status", "").strip().lower()
    search_query = request.GET.get("search", "").strip()

    batches = Batch.objects.filter(
        pk__in=base_requests.values_list("live_class__batch_id", flat=True)
    ).distinct().order_by("batch_name", "pk")

    subjects = Subject.objects.filter(
        pk__in=base_requests.values_list("live_class__subject_id", flat=True)
    ).distinct().order_by("subject_name", "pk")

    selected_batch = ""
    if batch_value.isdigit() and batches.filter(pk=int(batch_value)).exists():
        selected_batch = batch_value

    if selected_batch:
        subjects = subjects.filter(batch_id=int(selected_batch))

    selected_subject = ""
    if subject_value.isdigit() and subjects.filter(pk=int(subject_value)).exists():
        selected_subject = subject_value

    selected_date = parse_date(date_value)
    selected_status = (
        status_value
        if status_value in {
            CancellationStatus.PENDING,
            CancellationStatus.APPROVED,
            CancellationStatus.REJECTED,
        }
        else ""
    )

    cancellation_queryset = base_requests

    if selected_batch:
        cancellation_queryset = cancellation_queryset.filter(
            live_class__batch_id=int(selected_batch)
        )

    if selected_subject:
        cancellation_queryset = cancellation_queryset.filter(
            live_class__subject_id=int(selected_subject)
        )

    if selected_date:
        local_start = timezone.make_aware(
            datetime.combine(selected_date, datetime.min.time()),
            timezone.get_current_timezone(),
        )
        local_end = local_start + timedelta(days=1)
        cancellation_queryset = cancellation_queryset.filter(
            live_class__start_at__gte=local_start,
            live_class__start_at__lt=local_end,
        )

    if selected_status:
        cancellation_queryset = cancellation_queryset.filter(status=selected_status)

    if search_query:
        cancellation_queryset = cancellation_queryset.filter(
            Q(live_class__batch__batch_name__icontains=search_query)
            | Q(live_class__subject__subject_name__icontains=search_query)
            | Q(live_class__chapter__chapter_name__icontains=search_query)
        )

    cancellation_queryset = cancellation_queryset.order_by("-requested_at", "-pk")

    # Exactly 20 cancellation requests per page.
    paginator = Paginator(cancellation_queryset, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    cancellation_requests = list(page_obj.object_list)

    # Keep the current filters in pagination links.
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    pagination_query = pagination_params.urlencode()

    has_active_filters = any((
        selected_batch,
        selected_subject,
        selected_date,
        selected_status,
        search_query,
    ))

    context = {
        "teacher": teacher,
        "cancellation_requests": cancellation_requests,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "batches": batches,
        "subjects": subjects,
        "selected_batch": selected_batch,
        "selected_subject": selected_subject,
        "selected_date": selected_date,
        "selected_status": selected_status,
        "search_query": search_query,
        "paginator": paginator,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "has_active_filters": has_active_filters,
    }

    return render(
        request,
        "live_classes/teacher_cancellation_requests.html",
        context,
    )


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

    return redirect("live_classes:admin_upcoming_classes")


@admin_required
@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_review_cancellation_view(request, request_id):
    decision = request.POST.get("decision", "").strip().lower()
    if decision not in {"approve", "reject"}:
        messages.error(request, "Choose approve or reject.")
        return redirect("live_classes:admin_cancellation_requests")

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

    return redirect("live_classes:admin_cancellation_requests")

# ============================================================
# ADMIN: CANCELLATION REQUESTS PAGE
# ============================================================

@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_cancellation_requests_view(request):

    pending_requests = (
        CancellationRequest.objects
        .filter(status=CancellationStatus.PENDING)
        .select_related(
            "live_class",
            "live_class__batch",
            "live_class__subject",
            "live_class__chapter",
            "live_class__teacher",
            "requested_by",
        )
        .order_by("requested_at", "pk")
    )

    reviewed_requests = (
        CancellationRequest.objects
        .filter(
            status__in=[
                CancellationStatus.APPROVED,
                CancellationStatus.REJECTED,
            ]
        )
        .select_related(
            "live_class",
            "live_class__batch",
            "live_class__subject",
            "live_class__chapter",
            "live_class__teacher",
            "requested_by",
            "reviewed_by",
        )
        .order_by("-reviewed_at", "-requested_at")
    )

    context = {
        "pending_cancellation_requests": pending_requests,
        "reviewed_cancellation_requests": reviewed_requests,
        "approved_cancellation_count": reviewed_requests.filter(
            status=CancellationStatus.APPROVED
        ).count(),
        "rejected_cancellation_count": reviewed_requests.filter(
            status=CancellationStatus.REJECTED
        ).count(),
    }

    return render(
        request,
        "admins/live_classes/cancellation_requests.html",
        context,
    )

# ============================================================
# ADMIN: LIVE NOW DASHBOARD AND SESSION START
# ============================================================

@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_live_now_view(request):
    """Today's confirmed classes, live sessions and operational counts."""
    now = timezone.now()
    today = timezone.localdate()
    day_start = timezone.make_aware(
        datetime.combine(today, datetime.min.time()),
        timezone.get_current_timezone(),
    )
    day_end = day_start + timedelta(days=1)

    today_classes = LiveClass.objects.filter(
        start_at__gte=day_start,
        start_at__lt=day_end,
    ).filter(
        Q(status=LiveClassStatus.CONFIRMED)
        | Q(status=LiveClassStatus.COMPLETED)
    )

    live_base = today_classes.filter(
        status=LiveClassStatus.CONFIRMED,
        actual_start_at__isnull=False,
        actual_end_at__isnull=True,
    )
    completed_today = LiveClass.objects.filter(
        status=LiveClassStatus.COMPLETED,
        actual_end_at__gte=day_start,
        actual_end_at__lt=day_end,
    )
    can_start_base = today_classes.filter(
        status=LiveClassStatus.CONFIRMED,
        actual_start_at__isnull=True,
        actual_end_at__isnull=True,
        start_at__lte=now + timedelta(minutes=5),
        end_at__gt=now,
    )

    search_query = request.GET.get("q", "").strip()
    batch_value = request.GET.get("batch", "").strip()
    subject_value = request.GET.get("subject", "").strip()
    teacher_value = request.GET.get("teacher", "").strip()

    # Only show classes that have crossed the five-minute start boundary,
    # or sessions that have actually started and have not ended. Classes
    # more than five minutes away remain exclusively on Upcoming Classes.
    classes = today_classes.filter(
        status=LiveClassStatus.CONFIRMED,
        actual_end_at__isnull=True,
    ).filter(
        Q(
            actual_start_at__isnull=False,
        )
        | Q(
            actual_start_at__isnull=True,
            start_at__lte=now + timedelta(minutes=5),
            end_at__gt=now,
        )
    ).select_related("batch", "subject", "chapter", "teacher")

    if search_query:
        classes = classes.filter(
            Q(batch__batch_name__icontains=search_query)
            | Q(subject__subject_name__icontains=search_query)
            | Q(chapter__chapter_name__icontains=search_query)
            | Q(teacher__full_name__icontains=search_query)
        )
    if batch_value.isdigit():
        classes = classes.filter(batch_id=int(batch_value))
    if subject_value.isdigit():
        classes = classes.filter(subject_id=int(subject_value))
    if teacher_value.isdigit():
        classes = classes.filter(teacher_id=int(teacher_value))

    filter_base = today_classes.filter(status=LiveClassStatus.CONFIRMED)
    batches = Batch.objects.filter(
        pk__in=filter_base.values_list("batch_id", flat=True)
    ).order_by("batch_name", "pk")
    subjects = Subject.objects.filter(
        pk__in=filter_base.values_list("subject_id", flat=True)
    ).order_by("subject_name", "pk")
    teachers = Teacher.objects.filter(
        pk__in=filter_base.values_list("teacher_id", flat=True)
    ).order_by("full_name", "pk")

    paginator = Paginator(classes.order_by("start_at", "pk"), 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    live_now_classes = list(page_obj.object_list)

    for item in live_now_classes:
        item.local_start = timezone.localtime(item.start_at)
        item.time_range = f"{_format_time(item.start_at)} – {_format_time(item.end_at)}"
        item.duration_minutes = int((item.end_at - item.start_at).total_seconds() // 60)
        item.is_live_now = bool(item.actual_start_at and not item.actual_end_at)
        item.can_start_now = (
            item.status == LiveClassStatus.CONFIRMED
            and item.actual_start_at is None
            and item.actual_end_at is None
            and item.start_at <= now + timedelta(minutes=5)
            and item.end_at > now
        )
        item.start_window_opens_at = item.start_at - timedelta(minutes=5)
        item.seconds_until_start_window = max(
            0, int((item.start_window_opens_at - now).total_seconds())
        )
        item.actual_elapsed_seconds = (
            max(0, int((now - item.actual_start_at).total_seconds()))
            if item.is_live_now else 0
        )

    context = {
        "live_now_classes": live_now_classes,
        "page_obj": page_obj,
        "paginator": paginator,
        "today_classes_count": today_classes.count(),
        "live_now_count": live_base.count(),
        "can_start_now_count": can_start_base.count(),
        "completed_today_count": completed_today.count(),
        "batches": batches,
        "subjects": subjects,
        "teachers": teachers,
        "search_query": search_query,
        "selected_batch": batch_value,
        "selected_subject": subject_value,
        "selected_teacher": teacher_value,
        "now": now,
    }
    return render(request, "admins/live_classes/admin_live_now.html", context)


@admin_required
@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_start_live_class_view(request, class_id):
    """Start a confirmed class during its five-minute early-start window."""
    now = timezone.now()
    with transaction.atomic():
        live_class = (
            LiveClass.objects.select_for_update()
            .filter(pk=class_id)
            .first()
        )
        if live_class is None:
            messages.error(request, "The requested live class was not found.")
            return redirect("live_classes:admin_live_now")
        if live_class.status != LiveClassStatus.CONFIRMED:
            messages.error(request, "Only confirmed classes can be started.")
        elif live_class.actual_start_at is not None or live_class.actual_end_at is not None:
            messages.error(request, "This class session has already been started or ended.")
        elif now < live_class.start_at - timedelta(minutes=5):
            messages.error(request, "This class can only be started within five minutes of its scheduled start.")
        elif now >= live_class.end_at:
            messages.error(request, "The scheduled class time has ended. Reschedule it before starting.")
        else:
            live_class.actual_start_at = now
            live_class.save(update_fields=["actual_start_at", "updated_at"])
            messages.success(request, "Class started. It is now marked Live Now.")
    return redirect("live_classes:admin_live_now")


@login_required(login_url="teacher_login")
@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_start_live_class_view(request, class_id):
    """Allow only the assigned active teacher to start their confirmed class."""
    teacher = getattr(request.user, "teacher_profile", None)
    if teacher is None or not request.user.is_active or teacher.is_blocked:
        messages.error(request, "You are not permitted to start this class.")
        return redirect("live_classes:teacher_upcoming_classes")

    now = timezone.now()
    with transaction.atomic():
        live_class = (
            LiveClass.objects.select_for_update()
            .filter(pk=class_id, teacher=teacher)
            .first()
        )
        if live_class is None:
            messages.error(request, "This class is not assigned to your teacher account.")
        elif live_class.status != LiveClassStatus.CONFIRMED:
            messages.error(request, "Only confirmed classes can be started.")
        elif live_class.actual_start_at is not None or live_class.actual_end_at is not None:
            messages.error(request, "This class session has already been started or ended.")
        elif now < live_class.start_at - timedelta(minutes=5):
            messages.error(request, "You can start this class within five minutes of its scheduled start.")
        elif now >= live_class.end_at:
            messages.error(request, "The scheduled class time has ended. Contact Admin to reschedule.")
        else:
            live_class.actual_start_at = now
            live_class.save(update_fields=["actual_start_at", "updated_at"])
            messages.success(request, "Your class has started successfully.")
    return redirect("live_classes:teacher_upcoming_classes")