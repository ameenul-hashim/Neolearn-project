from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_POST

from admins.decorators import admin_required
from admins.models import Batch, Subject, Teacher, TeacherBatch, TeacherSubject

from .forms import LiveClassBookingForm
from .models import CancellationRequest, CancellationStatus, LiveClass, LiveClassStatus
from .services import (
    create_live_class,
    reschedule_live_class,
    request_live_class_cancellation,
    review_live_class_cancellation,
)

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
        start_at = timezone.make_aware(
            datetime.combine(class_date, start_time),
            timezone.get_current_timezone(),
        )
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
            messages.success(
                request,
                "Live class booked successfully and confirmed.",
            )
            return redirect("live_classes:teacher_live_classes")
    now = timezone.now()
    teacher_classes = (
        LiveClass.objects.filter(teacher=teacher)
        .select_related("batch", "subject", "chapter", "teacher")
    )
    upcoming_classes = teacher_classes.filter(
        status=LiveClassStatus.CONFIRMED,
        start_at__gte=now,
    ).order_by("start_at", "pk")
    recent_classes = (
        teacher_classes.exclude(
            status=LiveClassStatus.CONFIRMED,
            start_at__gte=now,
        )
        .order_by("-start_at", "-pk")[:8]
    )
    return render(
        request,
        "live_classes/teacher_live_classes.html",
        {
            "teacher": teacher,
            "form": form,
            "upcoming_classes": upcoming_classes,
            "recent_classes": recent_classes,
            "upcoming_count": upcoming_classes.count(),
            "now": now,
        },
    )

@admin_required
def admin_live_schedule_view(request):
    today = timezone.localdate()
    now = timezone.now()
    current_tz = timezone.get_current_timezone()
    selected_date = parse_date(request.GET.get("week", "")) or today
    week_start = selected_date
    week_end = week_start + timedelta(days=7)
    week_start_at = timezone.make_aware(
        datetime.combine(week_start, datetime.min.time()),
        current_tz,
    )
    week_end_at = timezone.make_aware(
        datetime.combine(week_end, datetime.min.time()),
        current_tz,
    )
    batches = Batch.objects.filter(
        batch_status__in=("published", "archived"),
    ).order_by("batch_name", "pk")
    requested_batch = request.GET.get("batch", "").strip()
    selected_batch_id = None
    if requested_batch.isdigit():
        if batches.filter(pk=int(requested_batch)).exists():
            selected_batch_id = int(requested_batch)
    if selected_batch_id is None:
        selected_batch_id = batches.values_list("pk", flat=True).first()
    selected_batch = (
        str(selected_batch_id) if selected_batch_id is not None else ""
    )
    subjects = Subject.objects.none()
    if selected_batch_id is not None:
        subjects = Subject.objects.filter(
            batch_id=selected_batch_id,
            subject_status="published",
        ).order_by("subject_name", "pk")
    requested_subject = request.GET.get("subject", "").strip()
    selected_subject_id = None
    if requested_subject.isdigit():
        if subjects.filter(pk=int(requested_subject)).exists():
            selected_subject_id = int(requested_subject)
    selected_subject = (
        str(selected_subject_id)
        if selected_subject_id is not None
        else ""
    )
    teachers = Teacher.objects.none()
    if selected_batch_id is not None:
        active_batch_teacher_ids = TeacherBatch.objects.filter(
            batch_id=selected_batch_id,
            is_active=True,
            teacher__is_blocked=False,
            teacher__user__is_active=True,
        ).values_list("teacher_id", flat=True)
        active_subject_assignments = TeacherSubject.objects.filter(
            batch_id=selected_batch_id,
            is_active=True,
            teacher_id__in=active_batch_teacher_ids,
            teacher__is_blocked=False,
            teacher__user__is_active=True,
        )
        if selected_subject_id is not None:
            active_subject_assignments = active_subject_assignments.filter(
                subject_id=selected_subject_id,
            )
        teachers = Teacher.objects.filter(
            pk__in=active_subject_assignments.values_list(
                "teacher_id",
                flat=True,
            ),
            is_blocked=False,
            user__is_active=True,
        ).order_by("full_name", "pk").distinct()
    requested_teacher = request.GET.get("teacher", "").strip()
    selected_teacher_id = None
    if requested_teacher.isdigit():
        if teachers.filter(pk=int(requested_teacher)).exists():
            selected_teacher_id = int(requested_teacher)
    selected_teacher = (
        str(selected_teacher_id)
        if selected_teacher_id is not None
        else ""
    )
    selected_status = request.GET.get("status", "").strip()
    valid_statuses = {value for value, label in LiveClassStatus.choices}
    if selected_status not in valid_statuses:
        selected_status = ""
    initial = {}
    if request.method == "GET":
        requested_class_date = parse_date(
            request.GET.get("class_date", ""),
        )
        requested_start_time = parse_time(
            request.GET.get("start_time", ""),
        )
        if requested_class_date:
            initial["class_date"] = requested_class_date
        if requested_start_time:
            initial["start_time"] = requested_start_time
        if selected_batch_id is not None:
            initial["batch"] = selected_batch_id
        if selected_subject_id is not None:
            initial["subject"] = selected_subject_id
        if selected_teacher_id is not None:
            initial["teacher"] = selected_teacher_id
    form = LiveClassBookingForm(
        request.POST or None,
        initial=initial if request.method == "GET" else None,
        admin_mode=True,
    )
    if request.method == "POST" and form.is_valid():
        class_date = form.cleaned_data["class_date"]
        start_time = form.cleaned_data["start_time"]
        duration_minutes = form.cleaned_data["duration_minutes"]
        start_at = timezone.make_aware(
            datetime.combine(class_date, start_time),
            current_tz,
        )
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
            messages.success(
                request,
                "Live class booked successfully and confirmed.",
            )
            return redirect("live_classes:admin_live_schedule")
    week_classes = (
        LiveClass.objects.filter(
            start_at__gte=week_start_at,
            start_at__lt=week_end_at,
        )
        .select_related(
            "batch",
            "subject",
            "chapter",
            "teacher",
            "created_by",
        )
        .order_by("start_at", "pk")
    )
    classes = week_classes
    if selected_batch_id is not None:
        classes = classes.filter(batch_id=selected_batch_id)
    else:
        classes = classes.none()
    if selected_subject_id is not None:
        classes = classes.filter(subject_id=selected_subject_id)
    if selected_teacher_id is not None:
        classes = classes.filter(teacher_id=selected_teacher_id)
    if selected_status:
        classes = classes.filter(status=selected_status)
    visible_classes = list(
        classes.select_related("batch", "subject", "chapter", "teacher"),
    )
    local_now = timezone.localtime(now)
    for live_class in visible_classes:
        local_start = timezone.localtime(live_class.start_at)
        local_end = timezone.localtime(live_class.end_at)
        live_class.local_start = local_start
        live_class.local_end = local_end
        live_class.time_range = (
            f"{local_start.strftime('%I:%M %p').lstrip('0')} – "
            f"{local_end.strftime('%I:%M %p').lstrip('0')}"
        )
        live_class.is_live = (
            live_class.status == LiveClassStatus.CONFIRMED
            and local_start <= local_now < local_end
        )
    confirmed_classes = classes.filter(status=LiveClassStatus.CONFIRMED)
    week_classes_count = classes.count()
    upcoming_count = confirmed_classes.filter(start_at__gte=now).count()
    live_now_count = confirmed_classes.filter(
        start_at__lte=now,
        end_at__gt=now,
    ).count()
    completed_count = classes.filter(
        status=LiveClassStatus.COMPLETED,
    ).count()
    cancelled_count = classes.filter(
        status=LiveClassStatus.CANCELLED,
    ).count()
    calendar_days = [
        {
            "date": week_start + timedelta(days=day_offset),
            "weekday": (week_start + timedelta(days=day_offset)).strftime("%a"),
        }
        for day_offset in range(7)
    ]
    slot_starts = [(hour, 0) for hour in range(5, 24)]
    calendar_rows = []
    for slot_hour, slot_minute in slot_starts:
        slot_time = datetime.min.time().replace(
            hour=slot_hour,
            minute=slot_minute,
        )
        slot_label = datetime.combine(
            week_start,
            slot_time,
        ).strftime("%I:%M %p").lstrip("0")
        row = {"label": slot_label, "cells": []}
        for day in calendar_days:
            cell_start = timezone.make_aware(
                datetime.combine(day["date"], slot_time),
                current_tz,
            )
            cell_end = cell_start + timedelta(hours=1)
            cell_classes = [
                live_class
                for live_class in visible_classes
                if (
                    live_class.start_at < cell_end
                    and live_class.end_at > cell_start
                )
            ]
            row["cells"].append(
                {
                    "date": day["date"],
                    "time": slot_time,
                    "label": slot_label,
                    "classes": cell_classes,
                    "past": cell_end <= now,
                    "available": cell_end > now and cell_start > now,
                }
            )
        calendar_rows.append(row)
    pending_cancellation_requests = (
        CancellationRequest.objects.filter(
            status=CancellationStatus.PENDING,
        )
        .select_related(
            "live_class",
            "live_class__batch",
            "live_class__subject",
            "live_class__teacher",
            "requested_by",
        )
        .order_by("requested_at", "pk")
    )
    context = {
        "form": form,
        "classes": visible_classes,
        "batches": batches,
        "subjects": subjects,
        "teachers": teachers,
        "selected_batch": selected_batch,
        "selected_subject": selected_subject,
        "selected_teacher": selected_teacher,
        "selected_status": selected_status,
        "today": today,
        "selected_date": selected_date,
        "week_start": week_start,
        "week_end": week_end - timedelta(days=1),
        "previous_week": week_start - timedelta(days=7),
        "next_week": week_start + timedelta(days=7),
        "week_classes_count": week_classes_count,
        "upcoming_count": upcoming_count,
        "live_now_count": live_now_count,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "calendar_days": calendar_days,
        "calendar_rows": calendar_rows,
        "now": now,
        "pending_cancellation_requests": pending_cancellation_requests,
    }
    return render(
        request,
        "admins/live_classes/live_schedule.html",
        context,
    )

# ============================================================
# LIVE CLASS RESCHEDULING AND CANCELLATION WORKFLOWS

# ============================================================

def _get_reschedule_times(request):
    """Read and validate the date, start time and duration from POST data."""
    class_date = parse_date(request.POST.get("class_date", ""))
    start_time = parse_time(request.POST.get("start_time", ""))
    try:
        duration_minutes = int(request.POST.get("duration_minutes", ""))
    except (TypeError, ValueError):
        duration_minutes = None
    if not class_date:
        raise ValidationError("Select a valid class date.")
    if not start_time:
        raise ValidationError("Select a valid start time.")
    if duration_minutes not in {60, 120, 180}:
        raise ValidationError(
            "Choose a duration of 1, 2 or 3 hours."
        )
    start_at = timezone.make_aware(
        datetime.combine(class_date, start_time),
        timezone.get_current_timezone(),
    )
    end_at = start_at + timedelta(minutes=duration_minutes)
    return start_at, end_at

@login_required(login_url="teacher_login")

@require_POST

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def teacher_reschedule_live_class_view(request, class_id):
    """Allow a teacher to reschedule their own eligible class."""
    teacher = getattr(request.user, "teacher_profile", None)
    if (
        teacher is None
        or not request.user.is_active
        or teacher.is_blocked
    ):
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
    """Allow the assigned teacher to request cancellation with a reason."""
    teacher = getattr(request.user, "teacher_profile", None)
    if (
        teacher is None
        or not request.user.is_active
        or teacher.is_blocked
    ):
        messages.error(request, "You cannot request this cancellation.")
        return redirect("teacher_login")
    if teacher.is_first_login:
        return redirect("teacher_change_password")
    try:
        request_live_class_cancellation(
            live_class_id=class_id,
            teacher=teacher,
            reason=request.POST.get("reason", "").strip(),
        )
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
    else:
        messages.success(
            request,
            "Cancellation request submitted for Admin review.",
        )
    return redirect("live_classes:teacher_live_classes")

@admin_required

@require_POST
def admin_reschedule_live_class_view(request, class_id):
    """Allow Admin to reschedule an eligible class."""
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
def admin_review_cancellation_view(request, request_id):
    """Approve or reject a pending teacher cancellation request."""
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
            (
                "Cancellation approved and class cancelled."
                if decision == "approve"
                else "Cancellation request rejected."
            ),
        )
    return redirect("live_classes:admin_live_schedule")
