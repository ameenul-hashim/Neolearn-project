from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from .models import Batch


# ==========================================================
# CONSTANTS
# ==========================================================

ALLOWED_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_BATCH_IMAGES = 5
MAX_BATCH_NAME_LENGTH = 150
MAX_DESCRIPTION_LENGTH = 250
MAX_OVERVIEW_LENGTH = 3000
MAX_FEATURES = 10
MIN_FEATURES = 3
MAX_FEATURE_LENGTH = 150
MAX_DEMO_VIDEO_SIZE = 500 * 1024 * 1024

DISCOUNT_TYPES = ("none", "percentage", "fixed")
PUBLISH_TYPES = ("immediate", "scheduled")
CREATE_BATCH_STATUS = ("draft", "published")
EDIT_BATCH_STATUS_WITH_STUDENTS = ("published", "archived")

COURSE_LANGUAGES = ("english", "malayalam", "both")
LEARNING_LEVELS = ("beginner", "intermediate", "advanced", "all_level")


# Current Batch model choices used by the new Create Batch workflow.
CREATE_COURSE_LANGUAGES = ("english", "malayalam", "malayalam_english")
CREATE_LEARNING_LEVELS = ("beginner", "intermediate", "advanced", "all_levels")
MAX_DEMO_TITLE_LENGTH = 100  # Create Batch rule; do not change Create Batch behaviour.
MAX_EDIT_DEMO_TITLE_LENGTH = 150  # Edit Batch demo title limit.
MAX_DEMO_DESCRIPTION_LENGTH = 300
MAX_DEMO_URL_LENGTH = 200


# ==========================================================
# COMMON PARSERS
# ==========================================================

def _text(value):
    return str(value or "").strip()


def _first_post_value(request, *names, default=""):
    """Read the first non-empty value from one of the supplied POST keys."""
    for name in names:
        values = request.POST.getlist(name)
        for value in values:
            if value is not None and str(value).strip():
                return value
    return default


def _first_file_value(request, *names):
    for name in names:
        files = request.FILES.getlist(name)
        for uploaded_file in files:
            if uploaded_file:
                return uploaded_file
    return None


def parse_datetime(value, field_name):
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value).strip(), "%Y-%m-%dT%H:%M")
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    except (TypeError, ValueError):
        raise ValidationError(f"Invalid {field_name}.")


def parse_date(value, field_name):
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValidationError(f"Invalid {field_name}.")


# ==========================================================
# BASIC FIELD VALIDATORS
# ==========================================================

def validate_thumbnail(image, required=True):
    if required and not image:
        raise ValidationError("Batch thumbnail is required.")
    if not image:
        return None

    extension = image.name.rsplit(".", 1)[-1].lower() if "." in image.name else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Only JPG, JPEG, PNG and WEBP images are allowed.")
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError("Thumbnail must be 5 MB or smaller.")
    return image


def validate_batch_name(batch_name, batch=None, student_count=0):
    batch_name = _text(batch_name)
    if student_count > 0 and batch:
        return batch.batch_name
    if not batch_name:
        raise ValidationError("Batch name is required.")
    if len(batch_name) > MAX_BATCH_NAME_LENGTH:
        raise ValidationError("Batch name cannot exceed 150 characters.")

    queryset = Batch.objects.filter(batch_name__iexact=batch_name)
    if batch:
        queryset = queryset.exclude(id=batch.id)
    if queryset.exists():
        raise ValidationError("Batch name already exists.")
    return batch_name


def validate_description(description):
    description = _text(description)
    if not description:
        raise ValidationError("Batch description is required.")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError("Batch description cannot exceed 250 characters.")
    return description


def validate_original_price(value):
    if value is None or not str(value).strip():
        raise ValidationError("Original price is required.")
    try:
        price = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Enter a valid original price.")
    if not price.is_finite() or price <= 0:
        raise ValidationError("Original price must be greater than zero.")
    return price


def validate_future_datetime(dt, field_name):
    if dt and dt <= timezone.now():
        raise ValidationError(f"{field_name} must be in the future.")


def validate_future_date(value, field_name):
    if value and value <= timezone.localdate():
        raise ValidationError(f"{field_name} must be a future date.")


# ==========================================================
# PRICING / PUBLISHING VALIDATORS
# ==========================================================

def validate_discount(discount_type, discount_value, original_price):
    discount_type = _text(discount_type) or "none"
    if discount_type not in DISCOUNT_TYPES:
        raise ValidationError("Invalid discount type.")

    if discount_type == "none":
        return discount_type, Decimal("0")

    if discount_value is None or not str(discount_value).strip():
        raise ValidationError("Discount value is required.")

    try:
        amount = Decimal(str(discount_value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Enter a valid discount value.")

    if not amount.is_finite() or amount <= 0:
        raise ValidationError("Discount value must be greater than zero.")

    if discount_type == "percentage":
        if amount > 100:
            raise ValidationError("Percentage discount cannot exceed 100.")
    elif discount_type == "fixed":
        if amount > original_price:
            raise ValidationError("Discount cannot exceed the original price.")

    return discount_type, amount

def validate_batch_status(batch_status, student_count=0):
    batch_status = _text(batch_status) or "draft"
    allowed = CREATE_BATCH_STATUS if student_count == 0 else EDIT_BATCH_STATUS_WITH_STUDENTS
    if batch_status not in allowed:
        if student_count:
            raise ValidationError("Cannot move batch back to Draft after students are enrolled.")
        raise ValidationError("Invalid batch status.")
    return batch_status


def validate_publish_settings(batch_status, publish_type, publish_datetime, existing_publish_time=None):
    if batch_status != "published":
        return "immediate", None

    publish_type = _text(publish_type) or "immediate"
    if publish_type not in PUBLISH_TYPES:
        raise ValidationError("Invalid publish type.")

    if publish_type == "immediate":
        return publish_type, existing_publish_time or timezone.now()

    publish_time = parse_datetime(publish_datetime, "publish date and time")
    if publish_time is None:
        raise ValidationError("Publish date and time is required for scheduled publishing.")
    validate_future_datetime(publish_time, "Publish date")
    return publish_type, publish_time


def validate_admission(batch_status, admission_close_datetime, publish_time):
    if batch_status != "published":
        return None

    admission_close = parse_datetime(admission_close_datetime, "admission close date and time")
    if admission_close is None:
        raise ValidationError("Admission close date and time is required.")
    validate_future_datetime(admission_close, "Admission close date")
    if publish_time and admission_close <= publish_time:
        raise ValidationError("Admission close date must be after the publish date.")
    return admission_close


def _same_local_minute(value, existing_value):
    """Compare a datetime-local value with a stored aware datetime to minute precision."""
    if not value or not existing_value:
        return False
    submitted = parse_datetime(value, "admission close date and time")
    existing_local = timezone.localtime(existing_value)
    return submitted.replace(second=0, microsecond=0) == existing_local.replace(
        second=0, microsecond=0
    )


def _validate_edit_publish_and_admission(request, batch, batch_status):
    """Validate Edit Batch publication settings while preserving publication history.

    An already-published batch keeps its original publication timestamp. Its
    admission-close date can remain unchanged, or be moved to a new future date.

    An archived batch keeps its historical publication and admission dates while
    it remains archived. When it is republished, the new Immediate/Scheduled
    choice is validated as a fresh publication and requires a new admission-close
    date. Existing course dates and student access are not changed here.
    """
    current_status = getattr(batch, "batch_status", None)

    # Keep the original publication/admission history when the batch is being
    # saved as Archived. Archiving must not erase the dates needed for history
    # or for a later republish.
    if batch_status == "archived":
        return (
            getattr(batch, "publish_type", None) or "immediate",
            getattr(batch, "published_at", None),
            getattr(batch, "publish_datetime", None),
            getattr(batch, "admission_close_datetime", None),
        )

    already_published = (
        current_status == "published"
        and batch_status == "published"
    )

    if already_published:
        publish_type = getattr(batch, "publish_type", None) or "immediate"
        if publish_type not in PUBLISH_TYPES:
            publish_type = "immediate"
        published_at = getattr(batch, "published_at", None)
        publish_datetime = getattr(batch, "publish_datetime", None)

        submitted_close = _text(request.POST.get("admission_close_datetime"))
        existing_close = getattr(batch, "admission_close_datetime", None)

        if not submitted_close:
            # Blank means retain the current admission setting; it does not
            # silently reopen an admission window that has already closed.
            admission_close = existing_close
        elif existing_close and _same_local_minute(submitted_close, existing_close):
            # Allow an unchanged historical close date on an already-published batch.
            admission_close = existing_close
        else:
            admission_close = parse_datetime(
                submitted_close, "admission close date and time"
            )
            if admission_close is None:
                raise ValidationError("Admission close date and time is required.")
            validate_future_datetime(admission_close, "New admission close date")
            publication_reference = published_at or publish_datetime
            if publication_reference and admission_close <= publication_reference:
                raise ValidationError(
                    "New admission close date must be after the original publish date."
                )

        return publish_type, published_at, publish_datetime, admission_close

    # Draft -> Published and Archived -> Published both use a fresh publication
    # setting. In particular, Immediate republishing must use the current time,
    # not the archived batch's old published_at timestamp.
    is_republishing = current_status == "archived" and batch_status == "published"
    publish_type, published_at = validate_publish_settings(
        batch_status=batch_status,
        publish_type=request.POST.get("publish_type"),
        publish_datetime=request.POST.get("publish_datetime"),
        existing_publish_time=(
            None if is_republishing else getattr(batch, "published_at", None)
        ),
    )
    admission_close = validate_admission(
        batch_status=batch_status,
        admission_close_datetime=request.POST.get("admission_close_datetime"),
        publish_time=published_at,
    )
    publish_datetime = (
        parse_datetime(request.POST.get("publish_datetime"), "publish date and time")
        if batch_status == "published" and publish_type == "scheduled"
        else None
    )
    return publish_type, published_at, publish_datetime, admission_close


def validate_offer_dates(
    discount_type,
    offer_start_date,
    offer_end_date,
    publish_time,
    admission_close_datetime,
    *,
    enabled=None,
):
    """
    Validate the optional limited-time offer window.

    `enabled` is supplied by the Create Batch checkbox. When it is False,
    offer dates are ignored and cleared from cleaned data, even if a regular
    percentage/fixed discount is selected. When enabled is None, retain the
    previous discount-type-based behaviour for Edit Batch compatibility.
    """
    if enabled is False:
        return None, None

    if discount_type not in DISCOUNT_TYPES:
        raise ValidationError("Invalid discount type.")

    if enabled is None and discount_type == "none":
        return None, None

    if enabled is True and discount_type == "none":
        raise ValidationError(
            "Select a percentage or fixed discount before enabling a limited-time offer."
        )

    if not offer_start_date:
        raise ValidationError("Offer start date and time is required.")

    if not offer_end_date:
        raise ValidationError("Offer end date and time is required.")

    offer_start = parse_datetime(offer_start_date, "offer start date and time")
    offer_end = parse_datetime(offer_end_date, "offer end date and time")

    # Check the relationship between the two selected values first.
    # This rejects reversed dates (for example, start 11 Nov and end 10 Nov)
    # regardless of whether the end date is also in the past.
    if offer_end <= offer_start:
        raise ValidationError(
            "Offer end date and time must be after the offer start date and time."
        )

    now = timezone.now()

    # The start must be strictly later than the current moment. A value in
    # the current minute is NOT accepted: datetime-local has minute precision,
    # so e.g. 11:05 is rejected when the current time is 11:05:01 or later.
    if offer_start <= now:
        raise ValidationError(
            "Offer start date and time must be in the future. Select a time later than now."
        )

    # The end must also be strictly later than now, and the ordering check
    # above guarantees it is later than the selected start.
    if offer_end <= now:
        raise ValidationError(
            "Offer end date and time must be in the future. Select a time later than now."
        )

    # For scheduled publishing, an offer cannot begin before publication.
    if publish_time and offer_start < publish_time:
        raise ValidationError(
            "Offer start date and time must be on or after the publish date and time."
        )

    if admission_close_datetime and admission_close_datetime <= offer_end:
        raise ValidationError(
            "Admission close date must be after the offer end date and time."
        )

    return offer_start, offer_end



def validate_course_end_date(
    batch_status,
    course_end_date,
    admission_close_datetime,
    *,
    required=False,
):
    # Create Batch requires an end date for both Draft and Published batches.
    # Edit Batch keeps its previous behaviour unless `required` is enabled.
    if batch_status != "published" and not required:
        return None

    course_end = parse_date(course_end_date, "course end date")
    if course_end is None:
        raise ValidationError("Course end date is required.")

    validate_future_date(course_end, "Course end date")

    if admission_close_datetime and course_end <= admission_close_datetime.date():
        raise ValidationError("Course end date must be after the admission close date.")

    return course_end


# ==========================================================
# COURSE INFORMATION VALIDATORS
# ==========================================================

def validate_batch_overview(value, *, required=False):
    """Validate the batch overview using consistent newline counting."""
    value = str(value or "")

    # Browsers may submit textarea line endings as CRLF (\r\n).
    # Normalize them so each visible line break counts as one character,
    # matching the frontend textarea counter.
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()

    if required and not value:
        raise ValidationError("Batch overview is required.")

    # Exactly 3,000 normalized characters is valid.
    if len(value) > MAX_OVERVIEW_LENGTH:
        raise ValidationError("Batch overview cannot exceed 3,000 characters.")

    return value


def validate_key_features(
    values,
    batch_status="draft",
    *,
    minimum_required=False,
):
    """
    Validate non-empty key features.

    Create Batch enables `minimum_required`, so drafts and published batches
    both require at least 3 completed features. Edit Batch keeps its previous
    behaviour unless it explicitly enables this option.
    """
    features = [_text(value) for value in (values or [])]
    features = [value for value in features if value]

    if minimum_required and len(features) < MIN_FEATURES:
        raise ValidationError("Add at least 3 key features.")

    if len(features) > MAX_FEATURES:
        raise ValidationError("You can add a maximum of 10 key features.")

    for index, feature in enumerate(features, start=1):
        if len(feature) > MAX_FEATURE_LENGTH:
            raise ValidationError(
                f"Key feature {index} cannot exceed 150 characters."
            )

    return features


def validate_course_language(value):
    value = _text(value)
    if value and value not in COURSE_LANGUAGES:
        raise ValidationError("Select a valid course language.")
    return value


def validate_course_duration(years, months, *, require_positive=False):
    try:
        years = int(years or 0)
        months = int(months or 0)
    except (TypeError, ValueError):
        raise ValidationError("Select a valid course duration in years and months.")

    if years < 0 or months < 0 or months > 11:
        raise ValidationError("Enter a valid course duration.")

    if years > 10 or (years * 12 + months) > 120:
        raise ValidationError("Course duration cannot exceed 10 years.")

    if require_positive and (years * 12 + months) <= 0:
        raise ValidationError("Select a course duration greater than zero.")

    return years, months


def validate_learning_level(value):
    value = _text(value)
    if value and value not in LEARNING_LEVELS:
        raise ValidationError("Select a valid learning level.")
    return value


def validate_limited_text(value, field_name, max_length):
    value = _text(value)
    if len(value) > max_length:
        raise ValidationError(f"{field_name} cannot exceed {max_length} characters.")
    return value


def _validate_additional_image_content(image):
    """Check the actual image data, not only the uploaded filename extension."""
    extension = image.name.rsplit(".", 1)[-1].lower() if "." in image.name else ""
    expected_formats = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
        "webp": "WEBP",
    }

    if extension not in expected_formats:
        raise ValidationError("Only JPG, JPEG, PNG and WEBP images are allowed.")

    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError("Each additional image must be 5 MB or smaller.")

    try:
        image.seek(0)
        with Image.open(image) as opened_image:
            actual_format = (opened_image.format or "").upper()
            if actual_format != expected_formats[extension]:
                raise ValidationError(
                    "The image content does not match its file extension. "
                    "Upload a valid JPG, JPEG, PNG or WEBP image."
                )
            opened_image.verify()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ValidationError(
            "This file is not a valid image. Upload a JPG, JPEG, PNG or WEBP image."
        )
    finally:
        try:
            image.seek(0)
        except (AttributeError, OSError):
            pass

    return image


def validate_additional_images(files, require_minimum=False):
    """Validate the Create Batch gallery; edit flows can retain their old optional behavior."""
    images = [file for file in (files or []) if file]

    if len(images) > MAX_BATCH_IMAGES:
        raise ValidationError(
            "You can upload a maximum of 5 additional images. Remove the extra images and try again."
        )

    if require_minimum and len(images) < 2:
        raise ValidationError(
            "Please upload at least 2 additional images. You can upload a maximum of 5."
        )

    validated = []
    for index, image in enumerate(images, start=1):
        try:
            validate_thumbnail(image, required=False)
            validated.append(_validate_additional_image_content(image))
        except ValidationError as exc:
            raise ValidationError(f"Additional image {index}: {exc.messages[0]}")

    return validated


def validate_demo_video(video):
    if not video:
        return None
    extension = video.name.rsplit(".", 1)[-1].lower() if "." in video.name else ""
    if extension not in ("mp4", "mov", "avi", "mkv", "webm"):
        raise ValidationError("Demo video must be MP4, MOV, AVI, MKV or WEBM.")
    if video.size > MAX_DEMO_VIDEO_SIZE:
        raise ValidationError("Demo video cannot exceed 500 MB.")
    return video


def validate_demo_url(value):
    value = _text(value)
    if not value:
        return ""
    try:
        URLValidator(schemes=("http", "https"))(value)
    except ValidationError:
        raise ValidationError("Enter a valid demo video URL.")
    return value


def validate_batch_demo(video, url, batch_status):
    video = validate_demo_video(video)
    url = validate_demo_url(url)

    if video and url:
        raise ValidationError("Upload a demo video or provide a demo URL, not both.")
    if batch_status == "published" and not (video or url):
        raise ValidationError("A batch demo video or demo URL is required before publishing.")
    return video, url


def _existing_batch_demo(batch):
    try:
        return batch.demo
    except Exception:
        return None


def _existing_subject_demo(subject):
    try:
        return subject.demo
    except Exception:
        return None


def _posted_subject_value(request, subject_id, *suffixes):
    """
    Read the subject-specific edit controls.

    Canonical HTML names:
      subject_demo_<subject_id>_type
      subject_demo_<subject_id>_title
      subject_demo_<subject_id>_description
      subject_demo_<subject_id>_video
      subject_demo_<subject_id>_url
      subject_demo_<subject_id>_remove
    """
    names = []
    for suffix in suffixes:
        names.extend((
            f"subject_demo_{subject_id}_{suffix}",
            f"subject_demo_{suffix}_{subject_id}",
        ))
    return _first_post_value(request, *names)


def _posted_subject_file(request, subject_id, *suffixes):
    names = []
    for suffix in suffixes:
        names.extend((
            f"subject_demo_{subject_id}_{suffix}",
            f"subject_demo_{suffix}_{subject_id}",
        ))
    return _first_file_value(request, *names)


def _validate_one_edit_demo(
    *,
    request,
    batch_status,
    existing_demo,
    title_names,
    description_names,
    type_names,
    file_names,
    url_names,
    required=False,
    label="Demo",
):
    """Validate one edit demo while retaining an existing unchanged asset."""
    video = _first_file_value(request, *file_names)
    submitted_url = _first_post_value(request, *url_names)
    submitted_title = _first_post_value(request, *title_names)
    submitted_description = _first_post_value(request, *description_names)
    submitted_type = _first_post_value(request, *type_names).strip().lower()

    if submitted_type and submitted_type not in ("upload", "external"):
        raise ValidationError(f"Select a valid {label.lower()} source type.")

    if video:
        video = validate_demo_video(video)

    # A blank URL control means "keep the existing URL" when the existing
    # demo already uses the external source. A nonblank URL replaces it.
    if submitted_url:
        external_url = validate_demo_url(submitted_url)
    elif (
        existing_demo
        and existing_demo.demo_type == "external"
        and submitted_type != "upload"
    ):
        # Keep an existing external URL only when the admin has not explicitly
        # switched this editor to uploaded-video mode. An explicit "upload"
        # selection must allow replacing an old external URL with a new file.
        external_url = existing_demo.external_url or ""
    else:
        external_url = ""

    if video and external_url:
        raise ValidationError(
            f"Choose either an uploaded {label.lower()} video or an external URL, not both."
        )

    if video:
        demo_type = "upload"
    elif external_url:
        demo_type = "external"
    elif submitted_type:
        demo_type = submitted_type
    elif existing_demo:
        demo_type = existing_demo.demo_type
    else:
        demo_type = ""

    # The Edit form submits these controls even when the admin clears them.
    # Distinguish an intentionally blank submitted value from a field that was
    # not part of a partial request; otherwise an old title could silently be
    # reused and a missing required title would incorrectly pass validation.
    if any(name in request.POST for name in title_names):
        title = _text(submitted_title)
    elif existing_demo:
        title = existing_demo.title
    else:
        title = ""

    if any(name in request.POST for name in description_names):
        description = _text(submitted_description)
    elif existing_demo:
        description = existing_demo.description or ""
    else:
        description = ""

    # Retain an existing uploaded file when the form has not submitted a new
    # file and the selected source remains "upload".
    if demo_type == "upload":
        if not video and existing_demo and existing_demo.demo_type == "upload":
            video = existing_demo.video_file
        external_url = ""
    elif demo_type == "external":
        video = None
    else:
        video = None
        external_url = ""

    has_demo = bool((video or external_url) and title)

    if required and not has_demo:
        raise ValidationError(
            f"A {label.lower()} video or external URL with a title is required before publishing."
        )

    if not (video or external_url):
        # The edit template posts a hidden default source type (usually
        # "upload") for every subject card. That default alone is not a
        # partially completed demo; an otherwise empty subject card is valid.
        if title or description or submitted_url:
            raise ValidationError(
                f"Select a {label.lower()} video or enter an external URL."
            )
        return None

    if not title:
        raise ValidationError(f"{label} title is required.")
    if len(title) > MAX_EDIT_DEMO_TITLE_LENGTH:
        raise ValidationError(f"{label} title cannot exceed 150 characters.")
    if len(description) > MAX_DEMO_DESCRIPTION_LENGTH:
        raise ValidationError(
            f"{label} description cannot exceed 300 characters."
        )
    if len(external_url) > MAX_DEMO_URL_LENGTH:
        raise ValidationError(
            f"External {label.lower()} URL cannot exceed 200 characters."
        )

    return {
        "demo_type": demo_type,
        "title": title,
        "description": description,
        "video_file": video if demo_type == "upload" else None,
        "external_url": external_url if demo_type == "external" else "",
    }


def _validate_edit_demo_mode(request, batch, batch_status, cleaned_data):
    """
    Validate only the Batch Edit demo workflow.

    The source selector (`batch_demo_type`) is deliberately NOT used as the
    scope selector: it continues to mean upload/external source. The scope is
    read from `demo_mode` (or the UI radio `demo_type_ui`).
    """
    mode = _first_post_value(
        request, "demo_mode", "batch_demo_mode", "demo_type_ui", default=""
    ).strip().lower()

    if not mode:
        mode = getattr(batch, "demo_mode", "batch") or "batch"

    if mode not in ("batch", "subject"):
        raise ValidationError("Select Batch-wise or Subject-wise demo mode.")

    subjects = list(batch.subjects.all().order_by("subject_name", "id"))
    if mode == "subject" and not subjects:
        raise ValidationError(
            "Subject-wise demos are available only after subjects have been created."
        )

    cleaned_data["demo_mode"] = mode
    cleaned_data["_batch_demo"] = None
    cleaned_data["_subject_demos"] = []

    if mode == "batch":
        existing = _existing_batch_demo(batch)
        payload = _validate_one_edit_demo(
            request=request,
            batch_status=batch_status,
            existing_demo=existing,
            title_names=("batch_demo_title", "batch_demo_url_title", "demo_title"),
            description_names=(
                "batch_demo_description",
                "batch_demo_url_description",
                "demo_description",
            ),
            type_names=("batch_demo_type",),
            file_names=("batch_demo_video", "overall_demo_video"),
            url_names=(
                "batch_demo_external_url",
                "batch_demo_url",
                "overall_demo_url",
                "video_url",
            ),
            required=(batch_status == "published"),
            label="Batch demo",
        )
        cleaned_data["_batch_demo"] = payload
        # Retain these legacy keys for any existing edit helper code that
        # still reads them. The source type remains upload/external.
        cleaned_data["batch_demo_video"] = (
            payload["video_file"] if payload and payload["demo_type"] == "upload" else None
        )
        cleaned_data["batch_demo_url"] = (
            payload["external_url"] if payload and payload["demo_type"] == "external" else ""
        )
        return

    active_subject_demo_count = 0

    for subject in subjects:
        existing = _existing_subject_demo(subject)
        subject_id = subject.pk
        remove_requested = parse_checkbox(
            _posted_subject_value(request, subject_id, "remove", "delete")
        )

        if remove_requested:
            cleaned_data["_subject_demos"].append({
                "subject_id": subject_id,
                "remove": True,
                "demo": None,
            })
            continue

        payload = _validate_one_edit_demo(
            request=request,
            batch_status=batch_status,
            existing_demo=existing,
            title_names=(
                f"subject_demo_{subject_id}_title",
                f"subject_demo_title_{subject_id}",
            ),
            description_names=(
                f"subject_demo_{subject_id}_description",
                f"subject_demo_description_{subject_id}",
            ),
            type_names=(
                f"subject_demo_{subject_id}_type",
                f"subject_demo_type_{subject_id}",
            ),
            file_names=(
                f"subject_demo_{subject_id}_video",
                f"subject_demo_video_{subject_id}",
            ),
            url_names=(
                f"subject_demo_{subject_id}_url",
                f"subject_demo_url_{subject_id}",
                f"subject_demo_{subject_id}_external_url",
            ),
            required=False,
            label=f"{subject.subject_name} demo",
        )

        if (
            payload
            and payload.get("demo_type") == "upload"
            and payload.get("video_file")
            and _text(payload.get("title"))
        ):
            active_subject_demo_count += 1

        cleaned_data["_subject_demos"].append({
            "subject_id": subject_id,
            "remove": False,
            "demo": payload,
        })

    if active_subject_demo_count < 1:
        raise ValidationError(
            "Subject-wise demo requires at least one subject video with a demo title. "
            "Add a video and title to at least one subject before continuing."
        )


# ==========================================================
# BOOLEAN PARSER
# ==========================================================

def parse_checkbox(value):
    return str(value).strip().lower() in ("true", "1", "on", "yes")


# ==========================================================
# CREATE / EDIT VALIDATION
# ==========================================================

def _validate_course_fields(request, cleaned_data, batch_status, batch=None):
    """Validate Edit Batch course details with the same required fields as Create Batch."""
    cleaned_data["batch_overview"] = validate_batch_overview(
        request.POST.get("batch_overview"), required=True
    )
    cleaned_data["key_features"] = validate_key_features(
        request.POST.getlist("batch_features")
        or request.POST.getlist("batch_features[]")
        or request.POST.getlist("key_features[]"),
        batch_status=batch_status,
        minimum_required=True,
    )
    cleaned_data["course_language"] = _validate_create_course_language(
        request.POST.get("course_language")
    )

    years_value = request.POST.get("course_duration_years")
    months_value = request.POST.get("course_duration_months")
    if years_value is None and request.POST.get("course_duration"):
        duration = _text(request.POST.get("course_duration"))
        unit = _text(request.POST.get("course_duration_unit")).lower()
        try:
            amount = int(duration)
        except (TypeError, ValueError):
            raise ValidationError("Course duration must be a whole number.")
        years_value, months_value = (
            (amount, 0) if unit in ("year", "years") else (0, amount)
        )

    years, months = validate_course_duration(
        years_value, months_value, require_positive=True
    )
    cleaned_data["course_duration_years"] = years
    cleaned_data["course_duration_months"] = months
    cleaned_data["target_audience"] = validate_limited_text(
        request.POST.get("target_audience"), "Target audience", 100
    )
    cleaned_data["prerequisites"] = validate_limited_text(
        request.POST.get("prerequisites"), "Prerequisites", 150
    )
    cleaned_data["learning_level"] = _validate_create_learning_level(
        request.POST.get("learning_level")
    )

    start_date = request.POST.get("course_start_date")
    cleaned_data["course_start_date"] = (
        parse_date(start_date, "course start date")
        if start_date
        else getattr(batch, "course_start_date", None)
    )
    cleaned_data["course_end_date"] = validate_course_end_date(
        batch_status="draft",
        course_end_date=request.POST.get("course_end_date"),
        admission_close_datetime=None,
        required=True,
    )

    cleaned_data["_additional_images"] = validate_additional_images(
        _get_uploaded_gallery_images(request), require_minimum=False
    )



# ==========================================================
# CREATE-ONLY VALIDATION FOR THE CURRENT BATCH STRUCTURE
# ==========================================================

def _validate_create_course_language(value):
    value = _text(value)
    if not value:
        raise ValidationError("Please select a course language.")
    if value not in CREATE_COURSE_LANGUAGES:
        raise ValidationError("Select a valid course language.")
    return value


def _validate_create_learning_level(value):
    value = _text(value)
    if value and value not in CREATE_LEARNING_LEVELS:
        raise ValidationError("Select a valid learning level.")
    return value


def _get_uploaded_gallery_images(request):
    """Read gallery uploads from the supported Create Batch input names."""
    for field_name in (
        "additional_images",
        "additional_images[]",
        "additional_batch_images",
        "batch_images",
        "batch_images[]",
    ):
        files = request.FILES.getlist(field_name)
        if files:
            return files
    return []


def _validate_create_demo(request, batch_status):
    """Return one BatchDemo payload, or None when a draft has no demo."""
    video = _first_file_value(
        request, "batch_demo_video", "overall_demo_video"
    )
    external_url = _first_post_value(
        request,
        "batch_demo_external_url",
        "batch_demo_url",
        "overall_demo_url",
        "video_url",
    )
    external_url = validate_demo_url(external_url)
    video = validate_demo_video(video)

    submitted_type = _first_post_value(
        request, "batch_demo_type", "demo_type"
    ).strip().lower()

    if submitted_type and submitted_type not in ("upload", "external"):
        raise ValidationError("Select a valid batch demo type.")

    if video and external_url:
        raise ValidationError(
            "Choose either an uploaded demo video or an external demo URL, not both."
        )

    if submitted_type == "upload" and external_url:
        raise ValidationError(
            "Remove the external URL when using an uploaded demo video."
        )
    if submitted_type == "external" and video:
        raise ValidationError(
            "Remove the uploaded video when using an external demo URL."
        )

    if video:
        demo_type = "upload"
    elif external_url:
        demo_type = "external"
    else:
        demo_type = submitted_type or ""

    # The URL-mode controls currently have IDs but may not yet have name
    # attributes. Read both sets of names so the small HTML correction can
    # be made without changing this validator again.
    if demo_type == "external":
        title = _first_post_value(
            request, "batch_demo_url_title", "batch_demo_title", "demo_title"
        )
        description = _first_post_value(
            request,
            "batch_demo_url_description",
            "batch_demo_description",
            "demo_description",
        )
    else:
        title = _first_post_value(
            request, "batch_demo_title", "demo_title"
        )
        description = _first_post_value(
            request, "batch_demo_description", "demo_description"
        )

    title = _text(title)
    description = _text(description)

    has_demo_input = bool(
        video or external_url or title or description or submitted_type
    )

    if not has_demo_input:
        if batch_status == "published":
            raise ValidationError(
                "A batch demo video or external demo URL is required before publishing."
            )
        return None

    if not (video or external_url):
        raise ValidationError(
            "Select a demo video or enter an external demo URL."
        )
    if not title:
        raise ValidationError("Batch demo title is required.")
    if len(title) > MAX_DEMO_TITLE_LENGTH:
        raise ValidationError("Batch demo title cannot exceed 100 characters.")
    if len(description) > MAX_DEMO_DESCRIPTION_LENGTH:
        raise ValidationError("Batch demo description cannot exceed 300 characters.")
    if len(external_url) > MAX_DEMO_URL_LENGTH:
        raise ValidationError("External demo URL cannot exceed 200 characters.")

    return {
        "demo_type": demo_type,
        "title": title,
        "description": description,
        "video_file": video if demo_type == "upload" else None,
        "external_url": external_url if demo_type == "external" else "",
    }


def _validate_create_course_fields(request, cleaned_data, batch_status):
    """Validate only fields and related records used by the new create flow."""
    cleaned_data["batch_overview"] = validate_batch_overview(
        request.POST.get("batch_overview"),
        required=True,
    )

    cleaned_data["key_features"] = validate_key_features(
        request.POST.getlist("batch_features")
        or request.POST.getlist("batch_features[]")
        or request.POST.getlist("key_features[]"),
        batch_status=batch_status,
        minimum_required=True,
    )

    cleaned_data["course_language"] = _validate_create_course_language(
        request.POST.get("course_language")
    )

    years, months = validate_course_duration(
        request.POST.get("course_duration_years"),
        request.POST.get("course_duration_months"),
        require_positive=True,
    )
    cleaned_data["course_duration_years"] = years
    cleaned_data["course_duration_months"] = months

    cleaned_data["target_audience"] = validate_limited_text(
        request.POST.get("target_audience"), "Target audience", 100
    )
    cleaned_data["prerequisites"] = validate_limited_text(
        request.POST.get("prerequisites"), "Prerequisites", 150
    )
    cleaned_data["learning_level"] = _validate_create_learning_level(
        request.POST.get("learning_level")
    )

    cleaned_data["_additional_images"] = validate_additional_images(
        _get_uploaded_gallery_images(request),
        require_minimum=True,
    )
    cleaned_data["_batch_demo"] = _validate_create_demo(
        request, batch_status
    )

    return cleaned_data

def _validate_shared_fields(
    request,
    cleaned_data,
    *,
    batch=None,
    student_count=0,
    require_course_end_date=False,
    use_limited_offer_toggle=False,
):
    cleaned_data["batch_name"] = validate_batch_name(
        request.POST.get("batch_name"), batch=batch, student_count=student_count
    )
    cleaned_data["batch_description"] = validate_description(
        request.POST.get("batch_description")
    )
    cleaned_data["batch_thumbnail"] = validate_thumbnail(
        request.FILES.get("batch_thumbnail"), required=(batch is None)
    )

    original_price = validate_original_price(request.POST.get("original_price"))
    cleaned_data["original_price"] = original_price
    discount_type, discount_value = validate_discount(
        request.POST.get("discount_type"),
        request.POST.get("discount_value"),
        original_price,
    )
    cleaned_data["discount_type"] = discount_type
    cleaned_data["discount_value"] = discount_value

    batch_status = validate_batch_status(
        request.POST.get("batch_status"), student_count=student_count
    )
    cleaned_data["batch_status"] = batch_status

    if batch is not None:
        (
            publish_type,
            published_at,
            publish_datetime,
            admission_close,
        ) = _validate_edit_publish_and_admission(request, batch, batch_status)
    else:
        publish_type, published_at = validate_publish_settings(
            batch_status=batch_status,
            publish_type=request.POST.get("publish_type"),
            publish_datetime=request.POST.get("publish_datetime"),
            existing_publish_time=None,
        )
        publish_datetime = published_at if publish_type == "scheduled" else None
        admission_close = validate_admission(
            batch_status=batch_status,
            admission_close_datetime=request.POST.get("admission_close_datetime"),
            publish_time=published_at,
        )

    cleaned_data["publish_type"] = publish_type
    cleaned_data["published_at"] = published_at
    cleaned_data["publish_datetime"] = publish_datetime
    cleaned_data["admission_close_datetime"] = admission_close

    offer_enabled = (
        parse_checkbox(request.POST.get("limited_time_offer"))
        if use_limited_offer_toggle
        else None
    )

    offer_start, offer_end = validate_offer_dates(
        discount_type=discount_type,
        offer_start_date=request.POST.get("offer_start_date"),
        offer_end_date=request.POST.get("offer_end_date"),
        publish_time=published_at,
        admission_close_datetime=admission_close,
        enabled=offer_enabled,
    )
    cleaned_data["offer_start_date"] = offer_start
    cleaned_data["offer_end_date"] = offer_end

    cleaned_data["course_end_date"] = validate_course_end_date(
        batch_status=batch_status,
        course_end_date=request.POST.get("course_end_date"),
        admission_close_datetime=admission_close,
        required=require_course_end_date,
    )
    cleaned_data["marketplace_visible"] = parse_checkbox(
        request.POST.get("marketplace_visible")
    )
    cleaned_data["featured"] = (
        parse_checkbox(request.POST.get("featured"))
        if "featured" in request.POST
        else bool(getattr(batch, "featured", False))
    )
    return batch_status


def validate_create_batch(request):
    """Validate the Create Batch form without changing Edit Batch behavior."""
    cleaned_data = {}
    batch_status = _validate_shared_fields(
        request,
        cleaned_data,
        require_course_end_date=True,
        use_limited_offer_toggle=True,
    )
    _validate_create_course_fields(request, cleaned_data, batch_status)
    return cleaned_data


def validate_edit_batch(request, batch, student_count=0):
    cleaned_data = {}
    batch_status = _validate_shared_fields(
        request,
        cleaned_data,
        batch=batch,
        student_count=student_count,
        require_course_end_date=True,
        use_limited_offer_toggle=True,
    )
    _validate_course_fields(request, cleaned_data, batch_status, batch=batch)

    if cleaned_data["batch_thumbnail"] is None:
        cleaned_data["batch_thumbnail"] = batch.batch_thumbnail

    # When editing, no newly uploaded additional images means keep existing images.
    if not cleaned_data["_additional_images"]:
        cleaned_data["_additional_images"] = None

    _validate_edit_demo_mode(
        request=request,
        batch=batch,
        batch_status=batch_status,
        cleaned_data=cleaned_data,
    )

    return cleaned_data


# ==========================================================
# EDIT BATCH — SECTION-BY-SECTION VALIDATION
# ==========================================================

def validate_edit_batch_step(request, batch, step, student_count=0):
    """Validate only the active Edit Batch step; never save during Next navigation."""
    try:
        step = int(step)
    except (TypeError, ValueError):
        raise ValidationError("Invalid batch editing step.")

    if step < 1 or step > 7:
        raise ValidationError("Invalid batch editing step.")

    if step == 1:
        validate_batch_name(
            request.POST.get("batch_name"), batch=batch, student_count=student_count
        )
        validate_description(request.POST.get("batch_description"))
        validate_thumbnail(
            request.FILES.get("batch_thumbnail"),
            required=not bool(batch.batch_thumbnail),
        )
        return True

    if step == 2:
        uploaded_images = _get_uploaded_gallery_images(request)
        validate_additional_images(uploaded_images, require_minimum=False)

        removed_ids = set()
        for raw_id in _text(request.POST.get("removed_gallery_image_ids")).split(","):
            raw_id = raw_id.strip()
            if raw_id.isdigit():
                removed_ids.add(int(raw_id))

        retained_count = batch.gallery_images.exclude(pk__in=removed_ids).count()
        total_count = retained_count + len(uploaded_images)
        if total_count < 2:
            raise ValidationError(
                "Add at least 2 additional batch images. Existing saved images count, "
                "so you only need to upload the missing images."
            )
        if total_count > MAX_BATCH_IMAGES:
            raise ValidationError(
                "A maximum of 5 additional batch images is allowed. Remove extra images and try again."
            )
        return True

    if step == 3:
        validate_batch_overview(request.POST.get("batch_overview"), required=True)
        submitted_features = (
            request.POST.getlist("batch_features")
            or request.POST.getlist("batch_features[]")
            or request.POST.getlist("key_features[]")
        )
        # Explicit Edit Batch guard: every non-empty feature must be at most
        # 150 characters, including dynamically added feature rows.
        for feature_index, raw_feature in enumerate(submitted_features, start=1):
            if len(_text(raw_feature)) > MAX_FEATURE_LENGTH:
                raise ValidationError(
                    f"Key feature {feature_index} cannot exceed 150 characters."
                )
        validate_key_features(
            submitted_features,
            batch_status="draft",
            minimum_required=True,
        )
        return True

    if step == 4:
        _validate_create_course_language(request.POST.get("course_language"))
        validate_course_duration(
            request.POST.get("course_duration_years"),
            request.POST.get("course_duration_months"),
            require_positive=True,
        )
        validate_limited_text(request.POST.get("target_audience"), "Target audience", 100)
        validate_limited_text(request.POST.get("prerequisites"), "Prerequisites", 150)
        _validate_create_learning_level(request.POST.get("learning_level"))
        validate_course_end_date(
            batch_status="draft",
            course_end_date=request.POST.get("course_end_date"),
            admission_close_datetime=None,
            required=True,
        )
        return True

    if step == 5:
        original_price = validate_original_price(request.POST.get("original_price"))
        discount_type, _discount_value = validate_discount(
            request.POST.get("discount_type"),
            request.POST.get("discount_value"),
            original_price,
        )
        offer_enabled = parse_checkbox(request.POST.get("limited_time_offer"))
        validate_offer_dates(
            discount_type=discount_type,
            offer_start_date=request.POST.get("offer_start_date"),
            offer_end_date=request.POST.get("offer_end_date"),
            publish_time=None,
            admission_close_datetime=None,
            enabled=offer_enabled,
        )
        return True

    if step == 6:
        batch_status = validate_batch_status(
            request.POST.get("batch_status") or getattr(batch, "batch_status", "draft"),
            student_count=student_count,
        )
        cleaned_data = {}
        _validate_edit_demo_mode(
            request=request,
            batch=batch,
            batch_status=batch_status,
            cleaned_data=cleaned_data,
        )
        return True

    batch_status = validate_batch_status(
        request.POST.get("batch_status") or getattr(batch, "batch_status", "draft"),
        student_count=student_count,
    )
    (
        _publish_type,
        published_at,
        _publish_datetime,
        admission_close,
    ) = _validate_edit_publish_and_admission(request, batch, batch_status)
    validate_course_end_date(
        batch_status=batch_status,
        course_end_date=request.POST.get("course_end_date"),
        admission_close_datetime=admission_close,
        required=True,
    )

    discount_type = _text(request.POST.get("discount_type")) or "none"
    offer_enabled = parse_checkbox(request.POST.get("limited_time_offer"))
    validate_offer_dates(
        discount_type=discount_type,
        offer_start_date=request.POST.get("offer_start_date"),
        offer_end_date=request.POST.get("offer_end_date"),
        publish_time=published_at,
        admission_close_datetime=admission_close,
        enabled=offer_enabled,
    )
    return True



# ==========================================================
# CREATE BATCH — SECTION-BY-SECTION VALIDATION
# ==========================================================

def validate_create_batch_step(request, step):
    """
    Validate only the requested Create Batch section.
    This function does not create or save any Batch records.
    """

    try:
        step = int(step)
    except (TypeError, ValueError):
        raise ValidationError("Invalid batch creation step.")

    if step < 1 or step > 7:
        raise ValidationError("Invalid batch creation step.")

    # ------------------------------------------------------
    # STEP 1 — BASIC INFORMATION
    # ------------------------------------------------------
    if step == 1:

        validate_batch_name(
            request.POST.get("batch_name")
        )

        validate_description(
            request.POST.get("batch_description")
        )

        validate_thumbnail(
            request.FILES.get("batch_thumbnail"),
            required=True,
        )

    # ------------------------------------------------------
    # STEP 2 — ADDITIONAL IMAGES
    # ------------------------------------------------------
    elif step == 2:

        validate_additional_images(
            _get_uploaded_gallery_images(request),
            require_minimum=True,
        )

    # ------------------------------------------------------
    # STEP 3 — OVERVIEW AND KEY FEATURES
    # ------------------------------------------------------
    elif step == 3:

        validate_batch_overview(
            request.POST.get("batch_overview"),
            required=True,
        )

        validate_key_features(
            request.POST.getlist("batch_features")
            or request.POST.getlist("batch_features[]")
            or request.POST.getlist("key_features[]"),
            batch_status="draft",
            minimum_required=True,
        )

    # ------------------------------------------------------
    # STEP 4 — COURSE INFORMATION
    # ------------------------------------------------------
    elif step == 4:

        _validate_create_course_language(
            request.POST.get("course_language")
        )

        validate_course_duration(
            request.POST.get("course_duration_years"),
            request.POST.get("course_duration_months"),
            require_positive=True,
        )

        validate_limited_text(
            request.POST.get("target_audience"),
            "Target audience",
            100,
        )

        validate_limited_text(
            request.POST.get("prerequisites"),
            "Prerequisites",
            150,
        )

        _validate_create_learning_level(
            request.POST.get("learning_level")
        )

        # Course End Date is required in Create Batch, including Drafts.
        validate_course_end_date(
            batch_status="draft",
            course_end_date=request.POST.get("course_end_date"),
            admission_close_datetime=None,
            required=True,
        )

    # ------------------------------------------------------
    # STEP 5 — PRICING AND OFFERS
    # ------------------------------------------------------
    elif step == 5:

        original_price = validate_original_price(
            request.POST.get("original_price")
        )

        discount_type, discount_value = validate_discount(
            request.POST.get("discount_type"),
            request.POST.get("discount_value"),
            original_price,
        )

        # Offer dates are validated only when the Create Batch toggle is ON.
        offer_enabled = parse_checkbox(request.POST.get("limited_time_offer"))
        validate_offer_dates(
            discount_type=discount_type,
            offer_start_date=request.POST.get("offer_start_date"),
            offer_end_date=request.POST.get("offer_end_date"),
            publish_time=None,
            admission_close_datetime=None,
            enabled=offer_enabled,
        )

    # ------------------------------------------------------
    # STEP 6 — BATCH DEMO
    # ------------------------------------------------------
    elif step == 6:

        _validate_create_demo(
            request,
            "draft",
        )

    # ------------------------------------------------------
    # STEP 7 — PUBLISH SETTINGS
    # ------------------------------------------------------
    elif step == 7:

        batch_status = validate_batch_status(
            request.POST.get("batch_status")
        )

        publish_type, published_at = validate_publish_settings(
            batch_status=batch_status,
            publish_type=request.POST.get("publish_type"),
            publish_datetime=request.POST.get("publish_datetime"),
        )

        admission_close = validate_admission(
            batch_status=batch_status,
            admission_close_datetime=request.POST.get(
                "admission_close_datetime"
            ),
            publish_time=published_at,
        )

        course_end_date = validate_course_end_date(
            batch_status=batch_status,
            course_end_date=request.POST.get("course_end_date"),
            admission_close_datetime=admission_close,
            required=True,
        )

        # Check offer dates against the publishing and admission dates.
        discount_type = (
            _text(request.POST.get("discount_type"))
            or "none"
        )

        if discount_type not in DISCOUNT_TYPES:
            raise ValidationError("Invalid discount type.")

        offer_enabled = parse_checkbox(request.POST.get("limited_time_offer"))
        validate_offer_dates(
            discount_type=discount_type,
            offer_start_date=request.POST.get("offer_start_date"),
            offer_end_date=request.POST.get("offer_end_date"),
            publish_time=published_at,
            admission_close_datetime=admission_close,
            enabled=offer_enabled,
        )