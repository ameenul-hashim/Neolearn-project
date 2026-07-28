from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Batch


# ==========================================================
# CONSTANTS
# ==========================================================

ALLOWED_IMAGE_EXTENSIONS = (
    "jpg",
    "jpeg",
    "png",
    "webp",
)

MAX_IMAGE_SIZE = 5 * 1024 * 1024


DISCOUNT_TYPES = (
    "none",
    "percentage",
    "fixed",
)

PUBLISH_TYPES = (
    "immediate",
    "scheduled",
)

CREATE_BATCH_STATUS = (
    "draft",
    "published",
)

EDIT_BATCH_STATUS_WITH_STUDENTS = (
    "published",
    "archived",
)

# ==========================================================
# DATETIME PARSER
# ==========================================================

def parse_datetime(value, field_name):

    if not value:
        return None

    try:

        return timezone.make_aware(
            datetime.strptime(
                value,
                "%Y-%m-%dT%H:%M"
            )
        )

    except ValueError:

        raise ValidationError(
            f"Invalid {field_name}."
        )


# ==========================================================
# DATE PARSER
# ==========================================================

def parse_date(value, field_name):

    if not value:
        return None

    try:

        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        raise ValidationError(
            f"Invalid {field_name}."
        )
        
# ==========================================================
# IMAGE VALIDATOR
# ==========================================================

def validate_thumbnail(
    image,
    required=True,
):

    if required and not image:

        raise ValidationError(
            "Batch thumbnail is required."
        )

    if not image:

        return None

    extension = image.name.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:

        raise ValidationError(
            "Only JPG, JPEG, PNG and WEBP images are allowed."
        )

    if image.size > MAX_IMAGE_SIZE:

        raise ValidationError(
            "Thumbnail must be less than 5 MB."
        )

    return image

# ==========================================================
# BATCH NAME
# ==========================================================

def validate_batch_name(
    batch_name,
    batch=None,
    student_count=0,
):

    batch_name = (
        batch_name or ""
    ).strip()

    if student_count > 0 and batch:

        return batch.batch_name

    if not batch_name:

        raise ValidationError(
            "Batch name is required."
        )

    queryset = Batch.objects.filter(
        batch_name__iexact=batch_name
    )

    if batch:

        queryset = queryset.exclude(
            id=batch.id
        )

    if queryset.exists():

        raise ValidationError(
            "Batch name already exists."
        )

    return batch_name

# ==========================================================
# DESCRIPTION
# ==========================================================

def validate_description(
    description,
):

    description = (
        description or ""
    ).strip()

    if not description:

        raise ValidationError(
            "Batch description is required."
        )

    return description

# ==========================================================
# ORIGINAL PRICE
# ==========================================================

def validate_original_price(
    value,
):

    if not value:

        raise ValidationError(
            "Original price is required."
        )

    try:

        price = Decimal(value)

    except InvalidOperation:

        raise ValidationError(
            "Enter a valid original price."
        )

    if price <= 0:

        raise ValidationError(
            "Original price must be greater than zero."
        )

    return price

# ==========================================================
# FUTURE DATETIME
# ==========================================================

def validate_future_datetime(
    dt,
    field_name,
):

    if not dt:

        return

    if dt <= timezone.now():

        raise ValidationError(
            f"{field_name} must be in the future."
        )
        
# ==========================================================
# FUTURE DATE
# ==========================================================

def validate_future_date(
    value,
    field_name,
):

    if not value:

        return

    if value <= timezone.now().date():

        raise ValidationError(
            f"{field_name} must be a future date."
        )
        
# ==========================================================
# DISCOUNT
# ==========================================================

def validate_discount(
    discount_type,
    discount_value,
    original_price,
):

    discount_type = (discount_type or "none").strip()

    if discount_type not in DISCOUNT_TYPES:

        raise ValidationError(
            "Invalid discount type."
        )

    # No Discount
    if discount_type == "none":

        return (
            discount_type,
            Decimal("0"),
        )

    if not discount_value:

        raise ValidationError(
            "Discount value is required."
        )

    try:

        discount_value = Decimal(discount_value)

    except InvalidOperation:

        raise ValidationError(
            "Enter a valid discount value."
        )

    if discount_value < 0:

        raise ValidationError(
            "Discount value cannot be negative."
        )

    if (
        discount_type == "percentage"
        and discount_value > 100
    ):

        raise ValidationError(
            "Percentage discount cannot exceed 100."
        )

    if (
        discount_type == "fixed"
        and discount_value > original_price
    ):

        raise ValidationError(
            "Discount cannot exceed the original price."
        )

    return (
        discount_type,
        discount_value,
    )
    
    
# ==========================================================
# BATCH STATUS
# ==========================================================

def validate_batch_status(
    batch_status,
    student_count=0,
):

    batch_status = (
        batch_status or "draft"
    ).strip()

    if student_count == 0:

        if batch_status not in CREATE_BATCH_STATUS:

            raise ValidationError(
                "Invalid batch status."
            )

    else:

        if batch_status not in EDIT_BATCH_STATUS_WITH_STUDENTS:

            raise ValidationError(
                "Cannot move batch back to Draft after students are enrolled."
            )

    return batch_status

# ==========================================================
# PUBLISH SETTINGS
# ==========================================================

def validate_publish_settings(
    batch_status,
    publish_type,
    publish_datetime,
    existing_publish_time=None,
):

    publish_time = existing_publish_time

    if batch_status != "published":

        return (
            "immediate",
            None,
        )

    if publish_type not in PUBLISH_TYPES:

        raise ValidationError(
            "Invalid publish type."
        )

    if publish_type == "immediate":

        if publish_time is None:

            publish_time = timezone.now()

        return (
            publish_type,
            publish_time,
        )

    publish_time = parse_datetime(
        publish_datetime,
        "publish date and time",
    )

    validate_future_datetime(
        publish_time,
        "Publish date",
    )

    return (
        publish_type,
        publish_time,
    )
    
# ==========================================================
# ADMISSION CLOSE
# ==========================================================

def validate_admission(
    batch_status,
    admission_close_datetime,
    publish_time,
):

    if batch_status != "published":

        return None

    admission_close = parse_datetime(
        admission_close_datetime,
        "admission close date and time",
    )

    if admission_close is None:

        raise ValidationError(
            "Admission close date and time is required."
        )

    validate_future_datetime(
        admission_close,
        "Admission close date",
    )

    if (
        publish_time
        and admission_close <= publish_time
    ):

        raise ValidationError(
            "Admission close date must be after the publish date."
        )

    return admission_close


# ==========================================================
# OFFER DATES
# ==========================================================

def validate_offer_dates(

    discount_type,

    offer_start_date,

    offer_end_date,

    publish_time,

    admission_close_datetime,

):

    if discount_type == "none":

        return (
            None,
            None,
        )

    if offer_start_date:

        offer_start = parse_datetime(
            offer_start_date,
            "offer start date",
        )

    else:

        offer_start = publish_time

    if offer_end_date:

        offer_end = parse_datetime(
            offer_end_date,
            "offer end date",
        )

    else:

        offer_end = None

    if (
        publish_time
        and offer_start
        and offer_start < publish_time
    ):

        raise ValidationError(
            "Offer start must be after publish date."
        )

    if (
        offer_start
        and offer_end
        and offer_end <= offer_start
    ):

        raise ValidationError(
            "Offer end date must be after offer start date."
        )

    if (
        offer_end
        and admission_close_datetime
        and admission_close_datetime <= offer_end
    ):

        raise ValidationError(
            "Admission close date must be after offer end date."
        )

    return (
        offer_start,
        offer_end,
    )
    
# ==========================================================
# COURSE END DATE
# ==========================================================

def validate_course_end_date(

    batch_status,

    course_end_date,

    admission_close_datetime,

):

    if batch_status != "published":

        return None

    course_end = parse_date(
        course_end_date,
        "course end date",
    )

    if course_end is None:

        raise ValidationError(
            "Course end date is required."
        )

    validate_future_date(
        course_end,
        "Course end date",
    )

    if (
        admission_close_datetime
        and course_end <= admission_close_datetime.date()
    ):

        raise ValidationError(
            "Course end date must be after the admission close date."
        )

    return course_end


# ==========================================================
# BOOLEAN PARSER
# ==========================================================

def parse_checkbox(value):
    return str(value).lower() in (
        "true",
        "1",
        "on",
        "yes",
    )
    

# ==========================================================
# CREATE BATCH VALIDATION
# ==========================================================

def validate_create_batch(request):

    cleaned_data = {}

    # ------------------------------------------------------
    # Basic Information
    # ------------------------------------------------------

    cleaned_data["batch_name"] = validate_batch_name(
        request.POST.get("batch_name")
    )

    cleaned_data["batch_description"] = validate_description(
        request.POST.get("batch_description")
    )

    cleaned_data["batch_thumbnail"] = validate_thumbnail(
        request.FILES.get("batch_thumbnail"),
        required=True,
    )

    # ------------------------------------------------------
    # Pricing
    # ------------------------------------------------------

    original_price = validate_original_price(
        request.POST.get("original_price")
    )

    cleaned_data["original_price"] = original_price

    (
        discount_type,
        discount_value,
    ) = validate_discount(
        request.POST.get("discount_type"),
        request.POST.get("discount_value"),
        original_price,
    )

    cleaned_data["discount_type"] = discount_type
    cleaned_data["discount_value"] = discount_value

    # ------------------------------------------------------
    # Batch Status
    # ------------------------------------------------------

    batch_status = validate_batch_status(
        request.POST.get("batch_status")
    )

    cleaned_data["batch_status"] = batch_status

        # ------------------------------------------------------
    # Publish Settings
    # ------------------------------------------------------

    (
        publish_type,
        published_at,
    ) = validate_publish_settings(
        batch_status=batch_status,
        publish_type=request.POST.get("publish_type"),
        publish_datetime=request.POST.get("publish_datetime"),
        existing_publish_time=None,
    )

    cleaned_data["publish_type"] = publish_type

    cleaned_data["published_at"] = published_at
    

    cleaned_data["publish_datetime"] = (
    published_at
    if publish_type == "scheduled"
    else None)

    # ------------------------------------------------------
    # Admission
    # ------------------------------------------------------

    admission_close_datetime = validate_admission(
        batch_status=batch_status,
        admission_close_datetime=request.POST.get(
            "admission_close_datetime"
        ),
        publish_time=published_at,
    )

    cleaned_data[
        "admission_close_datetime"
    ] = admission_close_datetime

    # ------------------------------------------------------
    # Offer
    # ------------------------------------------------------

    (
        offer_start_date,
        offer_end_date,
    ) = validate_offer_dates(

        discount_type=discount_type,

        offer_start_date=request.POST.get(
            "offer_start_date"
        ),

        offer_end_date=request.POST.get(
            "offer_end_date"
        ),

        publish_time=published_at,

        admission_close_datetime=admission_close_datetime,
    )

    cleaned_data[
        "offer_start_date"
    ] = offer_start_date

    cleaned_data[
        "offer_end_date"
    ] = offer_end_date

    # ------------------------------------------------------
    # Course End
    # ------------------------------------------------------

    cleaned_data[
        "course_end_date"
    ] = validate_course_end_date(

        batch_status=batch_status,

        course_end_date=request.POST.get(
            "course_end_date"
        ),

        admission_close_datetime=admission_close_datetime,
    )



    # ------------------------------------------------------
# Boolean Fields
# ------------------------------------------------------

    cleaned_data["marketplace_visible"] = parse_checkbox(
        request.POST.get("marketplace_visible"))

    cleaned_data["featured"] = parse_checkbox(
        request.POST.get("featured"))

    return cleaned_data


# ==========================================================
# EDIT BATCH VALIDATION
# ==========================================================

def validate_edit_batch(
    request,
    batch,
    student_count=0,
):

    cleaned_data = {}

    # ------------------------------------------------------
    # Basic Information
    # ------------------------------------------------------

    cleaned_data["batch_name"] = validate_batch_name(
        request.POST.get("batch_name"),
        batch=batch,
        student_count=student_count,
    )

    cleaned_data["batch_description"] = validate_description(
        request.POST.get("batch_description")
    )

    cleaned_data["batch_thumbnail"] = validate_thumbnail(
        request.FILES.get("batch_thumbnail"),
        required=False,
    )

    # ------------------------------------------------------
    # Pricing
    # ------------------------------------------------------

    original_price = validate_original_price(
        request.POST.get("original_price")
    )

    cleaned_data["original_price"] = original_price

    (
        discount_type,
        discount_value,
    ) = validate_discount(
        request.POST.get("discount_type"),
        request.POST.get("discount_value"),
        original_price,
    )

    cleaned_data["discount_type"] = discount_type
    cleaned_data["discount_value"] = discount_value

    # ------------------------------------------------------
    # Batch Status
    # ------------------------------------------------------

    batch_status = validate_batch_status(
        request.POST.get("batch_status"),
        student_count=student_count,
    )

    cleaned_data["batch_status"] = batch_status

    # ------------------------------------------------------
    # Publish Settings
    # ------------------------------------------------------

    (
        publish_type,
        published_at,
    ) = validate_publish_settings(
        batch_status=batch_status,
        publish_type=request.POST.get("publish_type"),
        publish_datetime=request.POST.get("publish_datetime"),
        existing_publish_time=batch.published_at,
    )

    cleaned_data["publish_type"] = publish_type

    cleaned_data["published_at"] = published_at

    cleaned_data["publish_datetime"] = (
        published_at
        if publish_type == "scheduled"
        else None
    )

    # ------------------------------------------------------
    # Admission
    # ------------------------------------------------------

    admission_close_datetime = validate_admission(
        batch_status=batch_status,
        admission_close_datetime=request.POST.get(
            "admission_close_datetime"
        ),
        publish_time=published_at,
    )

    cleaned_data[
        "admission_close_datetime"
    ] = admission_close_datetime

    # ------------------------------------------------------
    # Offer
    # ------------------------------------------------------

    (
        offer_start_date,
        offer_end_date,
    ) = validate_offer_dates(

        discount_type=discount_type,

        offer_start_date=request.POST.get(
            "offer_start_date"
        ),

        offer_end_date=request.POST.get(
            "offer_end_date"
        ),

        publish_time=published_at,

        admission_close_datetime=admission_close_datetime,
    )

    cleaned_data[
        "offer_start_date"
    ] = offer_start_date

    cleaned_data[
        "offer_end_date"
    ] = offer_end_date

    # ------------------------------------------------------
    # Course End
    # ------------------------------------------------------

    cleaned_data[
        "course_end_date"
    ] = validate_course_end_date(

        batch_status=batch_status,

        course_end_date=request.POST.get(
            "course_end_date"
        ),

        admission_close_datetime=admission_close_datetime,
    )

    # ------------------------------------------------------
    # Boolean Fields
    # ------------------------------------------------------

    cleaned_data[
        "marketplace_visible"
    ] = parse_checkbox(
        request.POST.get("marketplace_visible")
    )

    cleaned_data[
        "featured"
    ] = parse_checkbox(
        request.POST.get("featured")
    )

    # ------------------------------------------------------
    # Keep Existing Thumbnail
    # ------------------------------------------------------

    if cleaned_data["batch_thumbnail"] is None:
        cleaned_data["batch_thumbnail"] = batch.batch_thumbnail

    return cleaned_data