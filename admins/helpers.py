from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from .models import Batch, Coupon, CouponBatchRule
from datetime import datetime


# =========================================================
# BATCH HELPERS
# =========================================================


# FINAL PRICE CALCULATOR
def calculate_final_price(batch):
    original_price = batch.original_price or Decimal("0")

    if (
        batch.discount_type == "none"
        or batch.discount_value <= 0
        or not is_offer_active(batch)
    ):
        return original_price

    if batch.discount_type == "percentage":
        discount_amount = (
            original_price
            * batch.discount_value
            / Decimal("100")
        )

        final_price = (
            original_price
            - discount_amount
        )

    elif batch.discount_type == "fixed":
        final_price = (
            original_price
            - batch.discount_value
        )

    else:
        final_price = original_price

    if final_price < Decimal("0"):
        final_price = Decimal("0")

    return final_price.quantize(
        Decimal("0.01")
    )


def is_offer_active(batch):
    if batch.discount_type == "none":
        return False

    now = timezone.now()

    if batch.offer_start_date and now < batch.offer_start_date:
        return False

    if batch.offer_end_date and now > batch.offer_end_date:
        return False

    return True


def is_publish_active(batch):
    if batch.batch_status != "published":
        return False

    if batch.publish_type == "immediate":
        return True

    if batch.publish_datetime is None:
        return False

    return timezone.now() >= batch.publish_datetime


def get_batch_marketplace_status(batch):
    now = timezone.now()

    if batch.batch_status == "draft":
        return {
            "label": "Draft",
            "color": "gray",
        }

    if batch.batch_status == "archived":
        return {
            "label": "Archived",
            "color": "red",
        }

    if (
        batch.publish_type == "scheduled"
        and batch.publish_datetime
        and now < batch.publish_datetime
    ):
        return {
            "label": "Scheduled",
            "color": "blue",
        }

    if (
        batch.admission_close_datetime
        and now > batch.admission_close_datetime
    ):
        return {
            "label": "Admission Closed",
            "color": "orange",
        }

    return {
        "label": "Admission Open",
        "color": "green",
    }


def create_batch(cleaned_data):
    batch = Batch(**cleaned_data)
    batch.full_clean()
    batch.save()

    return batch


def update_batch(batch, cleaned_data):
    for field, value in cleaned_data.items():
        setattr(batch, field, value)

    batch.full_clean()
    batch.save()

    return batch


def build_batch_context(
    *,
    batch=None,
    form_data=None,
    extra_context=None,
):
    context = {
        "batch": batch,
        "form_data": form_data or {},
    }

    if extra_context:
        context.update(extra_context)

    return context


def can_delete_batch(batch, student_count=0):
    if batch.batch_status == "draft":
        return True

    if (
        batch.batch_status == "published"
        and student_count == 0
    ):
        return True

    if (
        batch.batch_status == "published"
        and student_count > 0
    ):
        return False

    if batch.batch_status == "archived":
        if batch.course_end_date is None:
            return False

        if timezone.now().date() < batch.course_end_date:
            return False

        return True

    return False


def can_archive_batch(batch, student_count=0):
    return (
        batch.batch_status == "published"
        and student_count > 0
    )


def can_publish_batch(batch):
    return batch.batch_status == "draft"


def can_edit_batch(batch, student_count=0):
    return {
        "batch_name": student_count == 0,
        "batch_description": True,
        "batch_thumbnail": True,
        "original_price": student_count == 0,
        "discount_type": True,
        "discount_value": True,
        "offer_start_date": True,
        "offer_end_date": True,
        "publish_type": student_count == 0,
        "publish_datetime": student_count == 0,
        "admission_close_datetime": True,
        "course_end_date": True,
        "batch_status": True,
    }


# =========================================================
# COUPON HELPERS
# =========================================================

from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

from .models import Batch, Coupon, CouponBatchRule


# =========================================================
# COUPON CONSTANTS
# =========================================================

COUPON_MAX_PERCENTAGE = Decimal("100.00")

COUPON_TYPES = {
    "general",
    "batch_specific",
}

COUPON_DISCOUNT_TYPES = {
    "percentage",
    "fixed",
}

COUPON_STATUS_VALUES = {
    "active",
    "inactive",
}


# =========================================================
# COMMON VALUE HELPERS
# =========================================================

def _money(value):
    """
    Convert a value safely into a two-decimal Decimal.
    """

    if value is None:
        return Decimal("0.00")

    try:
        value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")

    if not value.is_finite():
        return Decimal("0.00")

    if value < Decimal("0.00"):
        value = Decimal("0.00")

    return value.quantize(Decimal("0.01"))


def _integer(value):
    """
    Convert a value safely into an integer.
    """

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _get_post_value(request, *names, default=""):
    """
    Return the first available POST value.
    """

    for name in names:
        value = request.POST.get(name)

        if value is not None:
            return value

    return default


def _get_file_value(request, *names):
    """
    Return the first uploaded file found.
    """

    for name in names:
        value = request.FILES.get(name)

        if value:
            return value

    return None


# =========================================================
# DECIMAL PARSER
# =========================================================

def _parse_coupon_decimal(
    value,
    field_name,
    errors,
    *,
    allow_blank=True,
):
    """
    Safely parse a decimal field.
    """

    if value is None:
        if allow_blank:
            return None

        errors.append(f"{field_name} is required.")
        return None

    value = str(value).strip()

    if not value:
        if allow_blank:
            return None

        errors.append(f"{field_name} is required.")
        return None

    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        errors.append(f"{field_name} must be a valid number.")
        return None

    if not amount.is_finite():
        errors.append(f"{field_name} must be a valid number.")
        return None

    if amount < Decimal("0.00"):
        errors.append(f"{field_name} cannot be negative.")
        return None

    return amount.quantize(Decimal("0.01"))


# =========================================================
# INTEGER PARSER
# =========================================================

def _parse_coupon_integer(
    value,
    field_name,
    errors,
    *,
    allow_blank=True,
):
    """
    Safely parse an integer field.
    """

    if value is None:
        if allow_blank:
            return None

        errors.append(f"{field_name} is required.")
        return None

    value = str(value).strip()

    if not value:
        if allow_blank:
            return None

        errors.append(f"{field_name} is required.")
        return None

    if any(character in value for character in [".", ","]):
        errors.append(f"{field_name} must be a whole number.")
        return None

    try:
        number = int(value)
    except (ValueError, TypeError):
        errors.append(f"{field_name} must be a whole number.")
        return None

    if number < 0:
        errors.append(f"{field_name} cannot be negative.")
        return None

    return number


# =========================================================
# DATETIME PARSER
# =========================================================

def _parse_coupon_datetime(
    value,
    field_name,
    errors,
):
    """
    Parse HTML datetime-local values.
    """

    value = str(value or "").strip()

    if not value:
        errors.append(f"{field_name} is required.")
        return None

    accepted_formats = (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
    )

    parsed = None

    for input_format in accepted_formats:
        try:
            parsed = datetime.strptime(
                value,
                input_format,
            )
            break
        except ValueError:
            continue

    if parsed is None:
        errors.append(
            f"{field_name} must be a valid date and time."
        )
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(
            parsed,
            timezone.get_current_timezone(),
        )

    return parsed


# =========================================================
# COUPON CODE NORMALIZATION
# =========================================================

def normalize_coupon_code(code):
    """
    Normalize coupon code before validation/storage.
    """

    return str(code or "").strip().upper()


# =========================================================
# COUPON CODE VALIDATION
# =========================================================

def validate_coupon_code(
    code,
    errors,
    *,
    coupon=None,
):
    """
    Validate coupon code and uniqueness.
    """

    code = normalize_coupon_code(code)

    if not code:
        errors.append("Coupon code is required.")
        return code

    if len(code) < 3:
        errors.append(
            "Coupon code must contain at least 3 characters."
        )

    if len(code) > 50:
        errors.append(
            "Coupon code cannot exceed 50 characters."
        )

    allowed_characters = all(
        character.isalnum() or character in "-_"
        for character in code
    )

    if not allowed_characters:
        errors.append(
            "Coupon code can contain only letters, "
            "numbers, hyphens and underscores."
        )

    duplicate_query = Coupon.objects.filter(
        code__iexact=code
    )

    if coupon is not None:
        duplicate_query = duplicate_query.exclude(
            pk=coupon.pk
        )

    if duplicate_query.exists():
        errors.append(
            "Another coupon with this code already exists."
        )

    return code


# =========================================================
# AVAILABLE MARKETPLACE BATCHES
# =========================================================

def get_coupon_batches():
    """
    Return batches that can currently be configured
    for coupon use.
    """

    return (
        Batch.objects
        .filter(
            batch_status="published",
            marketplace_visible=True,
        )
        .order_by("batch_name")
    )


# =========================================================
# BATCH SELLING PRICE
# =========================================================

def get_batch_selling_price(batch):
    """
    Return the stored selling price for the batch.
    """

    if batch is None:
        return Decimal("0.00")

    price = getattr(batch, "final_price", None)

    if price is None or price <= Decimal("0.00"):
        price = getattr(
            batch,
            "original_price",
            Decimal("0.00"),
        )

    return _money(price)


def get_batch_current_price(batch):
    """
    Backwards-compatible alias for get_batch_selling_price.
    """

    return get_batch_selling_price(batch)


# =========================================================
# COUPON STATUS / VALIDITY
# =========================================================

def is_coupon_currently_valid(coupon):
    """
    Return True only when the coupon is active and
    inside its validity window.
    """

    if coupon.status != "active":
        return False

    if not coupon.is_active:
        return False

    now = timezone.now()

    if coupon.valid_from and now < coupon.valid_from:
        return False

    if coupon.valid_until and now > coupon.valid_until:
        return False

    if coupon_usage_limit_reached(coupon):
        return False

    return True


def is_coupon_upcoming(coupon):
    """
    Active coupon whose validity has not started yet.
    """

    if coupon.status != "active":
        return False

    if not coupon.is_active:
        return False

    if not coupon.valid_from:
        return False

    return timezone.now() < coupon.valid_from


def is_coupon_expired(coupon):
    """
    Coupon whose validity period has ended.
    """

    if not coupon.valid_until:
        return False

    return timezone.now() > coupon.valid_until


# =========================================================
# COUPON USAGE LIMITS
# =========================================================

def coupon_usage_limit_reached(coupon):
    """
    Check the total usage limit.
    """

    limit = coupon.usage_limit

    if limit is None:
        return False

    return (
        _integer(coupon.used_count)
        >= _integer(limit)
    )


def student_coupon_usage_limit_reached(
    coupon,
    student,
):
    """
    Per-student usage check.
    """

    limit = coupon.per_user_limit

    if limit is None:
        return False

    usage_model = getattr(
        coupon,
        "usage_records",
        None,
    )

    if usage_model is None:
        return False

    try:
        used_count = usage_model.filter(
            student=student
        ).count()
    except Exception:
        return False

    return used_count >= limit


# =========================================================
# DISCOUNT CALCULATION
# =========================================================

def calculate_discount_values(
    *,
    discount_type,
    discount_value,
    selling_price,
):
    """
    Calculate coupon discount against a selling price.

    Notes:

    - The maximum_discount_amount cap has been removed
      entirely. Percentage coupons are no longer capped.
    - Fixed coupons cannot exceed the selling price.
    - The final price never goes below zero.
    """

    selling_price = _money(selling_price)
    discount_value = _money(discount_value)

    if selling_price <= Decimal("0.00"):
        return {
            "valid": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": "Selling price must be greater than zero.",
        }

    if discount_value <= Decimal("0.00"):
        return {
            "valid": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": "Discount value must be greater than zero.",
        }

    if discount_type == "fixed":

        if discount_value > selling_price:
            return {
                "valid": False,
                "discount_amount": Decimal("0.00"),
                "final_price": selling_price,
                "reason": (
                    "Fixed discount cannot exceed "
                    "the current selling price."
                ),
            }

        discount_amount = discount_value

    elif discount_type == "percentage":

        if discount_value > COUPON_MAX_PERCENTAGE:
            return {
                "valid": False,
                "discount_amount": Decimal("0.00"),
                "final_price": selling_price,
                "reason": (
                    "Percentage discount cannot exceed 100%."
                ),
            }

        discount_amount = (
            selling_price
            * discount_value
            / Decimal("100.00")
        )

    else:
        return {
            "valid": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": "Invalid coupon discount type.",
        }

    discount_amount = min(
        discount_amount,
        selling_price,
    )

    discount_amount = _money(
        discount_amount
    )

    final_price = _money(
        selling_price - discount_amount
    )

    return {
        "valid": True,
        "discount_amount": discount_amount,
        "final_price": final_price,
        "reason": "",
    }


# =========================================================
# COUPON DISCOUNT / ORDER ELIGIBILITY
# =========================================================

def calculate_coupon_discount(
    coupon,
    selling_price,
):
    """
    Validate coupon-level restrictions and calculate
    the coupon result for a supplied selling price.
    """

    selling_price = _money(selling_price)

    if coupon.status != "active":
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": "Coupon is inactive.",
        }

    if not coupon.is_active:
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": "Coupon is inactive.",
        }

    now = timezone.now()

    if coupon.valid_from and now < coupon.valid_from:
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": "Coupon has not started yet.",
        }

    if coupon.valid_until and now > coupon.valid_until:
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": "Coupon has expired.",
        }

    if coupon_usage_limit_reached(coupon):
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": (
                "Coupon usage limit has been reached."
            ),
        }

    minimum_order = _money(
        coupon.minimum_order_amount
    )

    maximum_order = coupon.maximum_order_amount

    if (
        coupon.coupon_type == "general"
        and selling_price < minimum_order
    ):
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": (
                f"Minimum order amount is "
                f"₹{minimum_order:,.2f}."
            ),
        }

    if (
        coupon.coupon_type == "general"
        and maximum_order is not None
        and selling_price > _money(maximum_order)
    ):
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": (
                f"Maximum order amount is "
                f"₹{_money(maximum_order):,.2f}."
            ),
        }

    result = calculate_discount_values(
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        selling_price=selling_price,
    )

    if not result["valid"]:
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": selling_price,
            "reason": result["reason"],
        }

    return {
        "eligible": True,
        "discount_amount": result["discount_amount"],
        "final_price": result["final_price"],
        "reason": "",
    }


# =========================================================
# COUPON + BATCH ELIGIBILITY
# =========================================================

def is_coupon_batch_eligible(
    coupon,
    batch,
):
    """
    Check whether the coupon has been enabled for
    the supplied marketplace batch.
    """

    if batch is None:
        return False

    if (
        batch.batch_status != "published"
        or not batch.marketplace_visible
    ):
        return False

    return coupon.batch_rules.filter(
        batch=batch,
        is_enabled=True,
    ).exists()


def check_coupon_eligibility(
    coupon,
    batch,
    student=None,
):
    """
    Complete coupon eligibility check for a batch.
    """

    if batch is None:
        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": Decimal("0.00"),
            "reason": "Batch is required.",
        }

    if not is_coupon_batch_eligible(
        coupon,
        batch,
    ):
        current_price = get_batch_selling_price(
            batch
        )

        return {
            "eligible": False,
            "discount_amount": Decimal("0.00"),
            "final_price": current_price,
            "reason": (
                "Coupon is not available "
                "for this batch."
            ),
        }

    if student is not None:
        if student_coupon_usage_limit_reached(
            coupon,
            student,
        ):
            current_price = get_batch_selling_price(
                batch
            )

            return {
                "eligible": False,
                "discount_amount": Decimal("0.00"),
                "final_price": current_price,
                "reason": (
                    "You have already reached "
                    "this coupon's usage limit."
                ),
            }

    selling_price = get_batch_selling_price(
        batch
    )

    return calculate_coupon_discount(
        coupon,
        selling_price,
    )


# =========================================================
# ENABLED BATCH IDS
# =========================================================

def get_coupon_enabled_batch_ids(coupon):
    """
    Return enabled batch IDs for a coupon.
    """

    return set(
        coupon.batch_rules
        .filter(is_enabled=True)
        .values_list(
            "batch_id",
            flat=True,
        )
    )


# =========================================================
# SELECTED BATCH FOR BATCH-SPECIFIC COUPON
# =========================================================

def get_coupon_selected_batch(coupon):
    """
    Return the selected batch for a batch-specific coupon.
    """

    rule = (
        coupon.batch_rules
        .filter(is_enabled=True)
        .select_related("batch")
        .first()
    )

    if rule is None:
        return None

    return rule.batch


# =========================================================
# BATCH FORM ROWS
# =========================================================

def build_coupon_batch_rows(
    *,
    coupon=None,
    form_data=None,
):
    """
    Build batch information used by create/edit templates.
    """

    batches = list(
        get_coupon_batches()
    )

    enabled_ids = set()
    selected_batch_id = None

    if coupon is not None:

        enabled_ids = (
            get_coupon_enabled_batch_ids(coupon)
        )

        if coupon.coupon_type == "batch_specific":

            selected_batch = (
                get_coupon_selected_batch(coupon)
            )

            if selected_batch is not None:
                selected_batch_id = (
                    selected_batch.pk
                )

    if form_data is not None:

        if hasattr(
            form_data,
            "getlist",
        ):
            raw_enabled_ids = (
                form_data.getlist(
                    "enabled_batch_ids"
                )
            )
        else:
            raw_enabled_ids = (
                form_data.get(
                    "enabled_batch_ids",
                    [],
                )
            )

        if isinstance(
            raw_enabled_ids,
            str,
        ):
            raw_enabled_ids = [
                raw_enabled_ids
            ]

        enabled_ids = set()

        for raw_id in raw_enabled_ids:

            try:
                enabled_ids.add(
                    int(raw_id)
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

        selected_batch_value = (
            form_data.get(
                "batch_specific_batch"
            )
            or form_data.get(
                "selected_batch"
            )
        )

        if selected_batch_value:

            try:
                selected_batch_id = int(
                    selected_batch_value
                )
            except (
                TypeError,
                ValueError,
            ):
                selected_batch_id = None

    rows = []

    for batch in batches:

        selling_price = get_batch_selling_price(
            batch
        )

        existing_type = (
            batch.discount_type or "none"
        )

        existing_value = _money(
            batch.discount_value
        )

        subject_count = (
            batch.subjects.count()
        )

        teacher_count = (
            batch.assigned_teachers
            .filter(is_active=True)
            .count()
        )

        # TODO: connect a real enrollment model later.
        student_count = 0

        rows.append(
            {
                "batch": batch,
                "batch_id": batch.pk,
                "batch_name": batch.batch_name,

                "original_price": _money(
                    batch.original_price
                ),

                "current_price": selling_price,

                "existing_type": existing_type,
                "existing_value": existing_value,

                "subject_count": subject_count,
                "teacher_count": teacher_count,
                "student_count": student_count,

                "is_enabled": (
                    batch.pk in enabled_ids
                ),

                "is_selected": (
                    batch.pk
                    == selected_batch_id
                ),
            }
        )

    return rows


# =========================================================
# PARSE + VALIDATE COUPON FORM
# =========================================================

def parse_and_validate_coupon(
    request,
    *,
    coupon=None,
):
    """
    Parse and validate the complete coupon form.

    Returns:
        data, errors
    """

    errors = []

    now = timezone.now()

    # =====================================================
    # BASIC INFORMATION
    # =====================================================

    code = validate_coupon_code(
        _get_post_value(
            request,
            "code",
            "coupon_code",
        ),
        errors,
        coupon=coupon,
    )

    description = (
        _get_post_value(
            request,
            "description",
        )
        or ""
    ).strip()

    if not description:
        errors.append(
            "Coupon description is required."
        )

    coupon_type = (
        _get_post_value(
            request,
            "coupon_type",
        )
        or ""
    ).strip().lower()

    discount_type = (
        _get_post_value(
            request,
            "discount_type",
        )
        or ""
    ).strip().lower()

    if coupon_type not in COUPON_TYPES:
        errors.append(
            "Please select a valid coupon type."
        )

    if discount_type not in COUPON_DISCOUNT_TYPES:
        errors.append(
            "Please select a valid discount type."
        )

    # =====================================================
    # DISCOUNT
    # =====================================================

    discount_value = _parse_coupon_decimal(
        _get_post_value(
            request,
            "discount_value",
        ),
        "Discount value",
        errors,
        allow_blank=False,
    )

    if discount_value is not None:

        if discount_value <= Decimal("0.00"):
            errors.append(
                "Discount value must be greater than zero."
            )

        if (
            discount_type == "percentage"
            and discount_value
            > COUPON_MAX_PERCENTAGE
        ):
            errors.append(
                "Percentage discount cannot exceed 100%."
            )

    # =====================================================
    # ORDER RESTRICTIONS
    # =====================================================

    minimum_order_amount = _parse_coupon_decimal(
        _get_post_value(
            request,
            "minimum_order_amount",
        ),
        "Minimum order amount",
        errors,
        allow_blank=True,
    )

    maximum_order_amount = _parse_coupon_decimal(
        _get_post_value(
            request,
            "maximum_order_amount",
        ),
        "Maximum order amount",
        errors,
        allow_blank=True,
    )

    # The maximum_discount_amount field has been
    # removed from the validation flow entirely.
    # It is stored as None for every coupon.

    maximum_discount_amount = None

    if minimum_order_amount is None:
        minimum_order_amount = Decimal("0.00")

    if (
        maximum_order_amount is not None
        and maximum_order_amount
        < minimum_order_amount
    ):
        errors.append(
            "Maximum order amount cannot be less "
            "than minimum order amount."
        )

    # =====================================================
    # VALIDITY
    # =====================================================

    valid_from = _parse_coupon_datetime(
        _get_post_value(
            request,
            "valid_from",
        ),
        "Valid from",
        errors,
    )

    valid_until = _parse_coupon_datetime(
        _get_post_value(
            request,
            "valid_until",
        ),
        "Valid until",
        errors,
    )

    if (
        valid_from is not None
        and valid_from < now
    ):
        errors.append(
            "Valid from date and time cannot be in the past."
        )

    if (
        valid_until is not None
        and valid_until < now
    ):
        errors.append(
            "Valid until date and time cannot be in the past."
        )

    if (
        valid_from is not None
        and valid_until is not None
        and valid_from >= valid_until
    ):
        errors.append(
            "Valid until must be later than valid from."
        )

    # =====================================================
    # USAGE LIMITS
    # =====================================================

    usage_limit = _parse_coupon_integer(
        _get_post_value(
            request,
            "usage_limit",
        ),
        "Usage limit",
        errors,
        allow_blank=False,
    )

    per_user_limit = _parse_coupon_integer(
        _get_post_value(
            request,
            "per_user_limit",
        ),
        "Per-student usage limit",
        errors,
        allow_blank=False,
    )

    if (
        usage_limit is not None
        and usage_limit <= 0
    ):
        errors.append(
            "Usage limit must be greater than zero."
        )

    if (
        per_user_limit is not None
        and per_user_limit <= 0
    ):
        errors.append(
            "Per-student usage limit must be "
            "greater than zero."
        )

    if (
        usage_limit is not None
        and per_user_limit is not None
        and per_user_limit > usage_limit
    ):
        errors.append(
            "Per-student usage limit cannot exceed "
            "the total usage limit."
        )

    if (
        coupon is not None
        and usage_limit is not None
        and usage_limit
        < _integer(coupon.used_count)
    ):
        errors.append(
            "Usage limit cannot be less than "
            f"the current usage count "
            f"({_integer(coupon.used_count)})."
        )

    # =====================================================
    # STATUS
    # =====================================================

    raw_status = (
        _get_post_value(
            request,
            "status",
            "is_active",
            default="active",
        )
        or "active"
    ).strip().lower()

    if raw_status in {
        "1",
        "true",
        "on",
        "active",
    }:
        status = "active"

    elif raw_status in {
        "0",
        "false",
        "off",
        "inactive",
    }:
        status = "inactive"

    else:
        errors.append(
            "Please select a valid coupon status."
        )
        status = "active"

    # =====================================================
    # THUMBNAIL
    # =====================================================

    coupon_thumbnail = _get_file_value(
        request,
        "coupon_thumbnail",
        "thumbnail",
    )

    existing_thumbnail = (
        getattr(
            coupon,
            "coupon_thumbnail",
            None,
        )
        if coupon is not None
        else None
    )

    if coupon is None:

        if not coupon_thumbnail:
            errors.append(
                "Coupon thumbnail is required."
            )

    elif (
        not coupon_thumbnail
        and not existing_thumbnail
    ):
        errors.append(
            "Coupon thumbnail is required."
        )

    if coupon_thumbnail:

        content_type = getattr(
            coupon_thumbnail,
            "content_type",
            "",
        )

        allowed_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
        }

        if (
            content_type
            and content_type not in allowed_types
        ):
            errors.append(
                "Coupon thumbnail must be JPG, PNG, "
                "or WEBP."
            )

        max_size = 5 * 1024 * 1024

        if (
            getattr(
                coupon_thumbnail,
                "size",
                0,
            )
            > max_size
        ):
            errors.append(
                "Coupon thumbnail cannot exceed 5 MB."
            )

    # =====================================================
    # BATCH SELECTION
    # =====================================================

    selected_batch_id = (
        _get_post_value(
            request,
            "batch_specific_batch",
            "selected_batch",
        )
        or ""
    ).strip()

    selected_batch = None

    if selected_batch_id:

        try:
            selected_batch = Batch.objects.get(
                pk=int(selected_batch_id),
                batch_status="published",
                marketplace_visible=True,
            )

        except (
            Batch.DoesNotExist,
            ValueError,
            TypeError,
        ):
            errors.append(
                "Please select a valid marketplace batch."
            )

    if (
        coupon_type == "batch_specific"
        and selected_batch is None
    ):
        errors.append(
            "Please select a batch for this coupon."
        )

    # =====================================================
    # ENABLED BATCH IDS
    # =====================================================

    enabled_batch_ids = request.POST.getlist(
        "enabled_batch_ids"
    )

    clean_enabled_batch_ids = set()

    available_batch_ids = set(
        get_coupon_batches().values_list(
            "pk",
            flat=True,
        )
    )

    for raw_id in enabled_batch_ids:

        try:
            batch_id = int(raw_id)
        except (
            TypeError,
            ValueError,
        ):
            continue

        if batch_id in available_batch_ids:
            clean_enabled_batch_ids.add(
                batch_id
            )

    # =====================================================
    # GENERAL COUPON BATCH REQUIREMENT
    # =====================================================

    if coupon_type == "general":

        if not clean_enabled_batch_ids:
            errors.append(
                "Please select at least one eligible batch."
            )

        minimum_order_amount = (
            minimum_order_amount
            or Decimal("0.00")
        )

    # =====================================================
    # BATCH-SPECIFIC RESTRICTIONS
    # =====================================================

    if coupon_type == "batch_specific":

        if (
            minimum_order_amount is not None
            and minimum_order_amount
            != Decimal("0.00")
        ):
            errors.append(
                "Minimum order amount is not applicable "
                "to batch-specific coupons."
            )

        if maximum_order_amount is not None:
            errors.append(
                "Maximum order amount is not applicable "
                "to batch-specific coupons."
            )

        minimum_order_amount = Decimal("0.00")
        maximum_order_amount = None

    # =====================================================
    # FIXED DISCOUNT VS SELLING PRICE
    # =====================================================

    if (
        discount_type == "fixed"
        and discount_value is not None
    ):

        if (
            coupon_type == "batch_specific"
            and selected_batch is not None
        ):

            selling_price = (
                get_batch_selling_price(
                    selected_batch
                )
            )

            if discount_value > selling_price:
                errors.append(
                    "Fixed discount cannot exceed "
                    f"the current selling price "
                    f"of ₹{selling_price:,.2f} "
                    "for the selected batch."
                )

        elif coupon_type == "general":

            selected_batches = Batch.objects.filter(
                pk__in=clean_enabled_batch_ids,
                batch_status="published",
                marketplace_visible=True,
            )

            for batch in selected_batches:

                selling_price = (
                    get_batch_selling_price(
                        batch
                    )
                )

                if discount_value > selling_price:
                    errors.append(
                        "Fixed discount cannot exceed "
                        f"₹{selling_price:,.2f} "
                        f"for batch '{batch.batch_name}'."
                    )

    # =====================================================
    # FINAL DATA
    # =====================================================

    data = {
        "code": code,
        "description": description,
        "coupon_type": coupon_type,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "minimum_order_amount": (
            minimum_order_amount
        ),
        "maximum_order_amount": (
            maximum_order_amount
        ),
        "maximum_discount_amount": (
            maximum_discount_amount
        ),
        "valid_from": valid_from,
        "valid_until": valid_until,
        "usage_limit": usage_limit,
        "per_user_limit": per_user_limit,
        "status": status,
        "coupon_thumbnail": coupon_thumbnail,
        "selected_batch": selected_batch,
        "enabled_batch_ids": list(
            clean_enabled_batch_ids
        ),
    }

    return data, errors


# =========================================================
# SAVE COUPON BATCH RULES
# =========================================================

def save_coupon_batch_rules(
    *,
    coupon,
    coupon_type,
    selected_batch=None,
    enabled_batch_ids=None,
):
    """
    Save the batch eligibility configuration.
    """

    enabled_batch_ids = (
        enabled_batch_ids or []
    )

    available_batch_ids = set(
        get_coupon_batches().values_list(
            "pk",
            flat=True,
        )
    )

    clean_enabled_ids = set()

    for raw_id in enabled_batch_ids:

        try:
            batch_id = int(raw_id)
        except (
            TypeError,
            ValueError,
        ):
            continue

        if batch_id in available_batch_ids:
            clean_enabled_ids.add(
                batch_id
            )

    # =====================================================
    # BATCH-SPECIFIC
    # =====================================================

    if coupon_type == "batch_specific":

        coupon.batch_rules.all().delete()

        if (
            selected_batch is not None
            and selected_batch.pk
            in available_batch_ids
        ):
            CouponBatchRule.objects.create(
                coupon=coupon,
                batch=selected_batch,
                is_enabled=True,
            )

        return

    # =====================================================
    # GENERAL
    # =====================================================

    coupon.batch_rules.all().delete()

    for batch_id in clean_enabled_ids:

        CouponBatchRule.objects.create(
            coupon=coupon,
            batch_id=batch_id,
            is_enabled=True,
        )


# =========================================================
# CREATE COUPON INSTANCE
# =========================================================

def create_coupon_instance(data):
    """
    Create the Coupon database record.
    """

    coupon = Coupon(
        code=data["code"],
        description=data["description"],
        coupon_type=data["coupon_type"],
        discount_type=data["discount_type"],
        discount_value=data["discount_value"],
        minimum_order_amount=(
            data["minimum_order_amount"]
        ),
        maximum_order_amount=(
            data["maximum_order_amount"]
        ),
        maximum_discount_amount=None,
        valid_from=data["valid_from"],
        valid_until=data["valid_until"],
        usage_limit=data["usage_limit"],
        per_user_limit=data["per_user_limit"],
        status=data["status"],
        is_active=(
            data["status"] == "active"
        ),
    )

    if data.get("coupon_thumbnail"):
        coupon.coupon_thumbnail = (
            data["coupon_thumbnail"]
        )

    coupon.full_clean()
    coupon.save()

    return coupon


# =========================================================
# UPDATE COUPON INSTANCE
# =========================================================

def update_coupon_instance(
    coupon,
    data,
):
    """
    Update the Coupon database record.
    """

    coupon.code = data["code"]

    coupon.description = (
        data["description"]
    )

    coupon.coupon_type = (
        data["coupon_type"]
    )

    coupon.discount_type = (
        data["discount_type"]
    )

    coupon.discount_value = (
        data["discount_value"]
    )

    coupon.minimum_order_amount = (
        data["minimum_order_amount"]
    )

    coupon.maximum_order_amount = (
        data["maximum_order_amount"]
    )

    # maximum_discount_amount is no longer set.

    coupon.valid_from = data["valid_from"]

    coupon.valid_until = data["valid_until"]

    coupon.usage_limit = (
        data["usage_limit"]
    )

    coupon.per_user_limit = (
        data["per_user_limit"]
    )

    coupon.status = data["status"]

    coupon.is_active = (
        data["status"] == "active"
    )

    if data.get("coupon_thumbnail"):
        coupon.coupon_thumbnail = (
            data["coupon_thumbnail"]
        )

    coupon.full_clean()
    coupon.save()

    return coupon


# =========================================================
# COUPON MESSAGES
# =========================================================

def add_coupon_errors_to_messages(
    request,
    errors,
):
    """
    Convert helper validation errors into
    Django messages.
    """

    from django.contrib import messages

    for error in errors:

        messages.error(
            request,
            error,
        )


# =========================================================
# COUPON LIST QUERYSET
# =========================================================

def get_coupon_queryset():
    """
    Base queryset for the main Coupons page.
    """

    return (
        Coupon.objects
        .prefetch_related(
            "batch_rules__batch",
        )
        .order_by(
            "-created_at"
        )
    )


# =========================================================
# COUPON LISTING CONTEXT
# =========================================================

def get_coupon_listing_context(request):
    """
    Complete backend context for the main Coupons page.
    """

    coupons = get_coupon_queryset()

    search = (
        request.GET.get(
            "search",
            "",
        )
        .strip()
    )

    coupon_type = (
        request.GET.get(
            "type",
            "",
        )
        .strip()
        .lower()
    )

    status = (
        request.GET.get(
            "status",
            "",
        )
        .strip()
        .lower()
    )

    sort = (
        request.GET.get(
            "sort",
            "newest",
        )
        .strip()
        .lower()
    )

    page_number = (
        request.GET.get(
            "page",
            1,
        )
    )

    if search:

        coupons = (
            coupons
            .filter(
                Q(code__icontains=search)
                |
                Q(description__icontains=search)
                |
                Q(
                    batch_rules__batch__batch_name__icontains=search
                )
            )
            .distinct()
        )

    if coupon_type in COUPON_TYPES:

        coupons = coupons.filter(
            coupon_type=coupon_type
        )

    current_time = timezone.now()

    if status == "active":

        coupons = coupons.filter(
            is_active=True
        )

    elif status == "inactive":

        coupons = coupons.filter(
            is_active=False
        )

    elif status == "upcoming":

        coupons = coupons.filter(
            is_active=True,
            valid_from__gt=current_time,
        )

    elif status == "expired":

        coupons = coupons.filter(
            valid_until__lt=current_time,
        )

    elif status == "running":

        coupons = coupons.filter(
            is_active=True,
            valid_from__lte=current_time,
            valid_until__gte=current_time,
        )

    if sort == "oldest":

        coupons = coupons.order_by(
            "created_at"
        )

    elif sort == "a_z":

        coupons = coupons.order_by(
            "code"
        )

    elif sort == "z_a":

        coupons = coupons.order_by(
            "-code"
        )

    elif sort == "expiry_soon":

        coupons = coupons.order_by(
            "valid_until"
        )

    elif sort == "most_used":

        coupons = coupons.order_by(
            "-used_count",
            "-created_at",
        )

    else:

        coupons = coupons.order_by(
            "-created_at"
        )

    paginator = Paginator(
        coupons,
        9,
    )

    page_obj = paginator.get_page(
        page_number
    )

    all_coupons = Coupon.objects.all()

    total_coupons = (
        all_coupons.count()
    )

    active_coupons = (
        all_coupons
        .filter(
            is_active=True
        )
        .count()
    )

    inactive_coupons = (
        all_coupons
        .filter(
            is_active=False
        )
        .count()
    )

    total_usage = sum(
        _integer(
            coupon.used_count
        )
        for coupon in all_coupons
    )

    # =====================================================
    # TOTAL DISCOUNT GIVEN
    # =====================================================
    #
    # The Coupon model does not store the actual
    # order-level discount for percentage coupons,
    # so we cannot compute a precise total for them.
    # Fixed coupons use the configured fixed amount
    # multiplied by used_count.

    total_discount_given = (
        Decimal("0.00")
    )

    for coupon in all_coupons:

        used_count = _integer(
            coupon.used_count
        )

        if (
            coupon.discount_type
            == "fixed"
        ):

            total_discount_given += (
                _money(
                    coupon.discount_value
                )
                * used_count
            )

    return {
        "coupons": page_obj,
        "page_obj": page_obj,

        "search": search,
        "coupon_type": coupon_type,
        "status": status,
        "sort": sort,

        "total_coupons": total_coupons,
        "active_coupons": active_coupons,
        "inactive_coupons": inactive_coupons,
        "total_usage": total_usage,
        "total_discount_given": (
            total_discount_given
        ),
    }


# =========================================================
# TOGGLE COUPON STATUS
# =========================================================

def toggle_coupon_status(coupon):
    """
    Toggle Active / Inactive status.
    """

    if coupon.status == "active":

        coupon.status = "inactive"
        coupon.is_active = False

    else:

        coupon.status = "active"
        coupon.is_active = True

    coupon.save(
        update_fields=[
            "status",
            "is_active",
            "updated_at",
        ]
    )

    return coupon


# =========================================================
# DELETE CHECK
# =========================================================

def can_delete_coupon(coupon):
    """
    Used coupons cannot be permanently deleted.
    """

    return (
        _integer(
            coupon.used_count
        )
        == 0
    )


# =========================================================
# DELETE COUPON
# =========================================================

def delete_coupon(coupon):
    """
    Delete coupon after business validation.
    """

    if not can_delete_coupon(coupon):

        raise ValidationError(
            "A coupon that has already been used "
            "cannot be permanently deleted."
        )

    coupon.delete()


# =========================================================
# COUPON PREVIEW
# =========================================================

def build_coupon_preview(
    coupon,
    batch,
):
    """
    Build pricing preview data for admin.
    """

    selling_price = (
        get_batch_selling_price(
            batch
        )
    )

    result = check_coupon_eligibility(
        coupon,
        batch,
    )

    return {
        "batch": batch,

        "original_price": _money(
            batch.original_price
        ),

        "existing_discount_type": (
            batch.discount_type
        ),

        "existing_discount_value": (
            batch.discount_value
        ),

        "current_price": selling_price,

        "eligible": result["eligible"],

        "discount_amount": (
            result["discount_amount"]
        ),

        "final_price": (
            result["final_price"]
        ),

        "reason": result["reason"],
    }


# =========================================================
# COUPON FORM CONTEXT
# =========================================================

def build_coupon_form_context(
    *,
    request=None,
    coupon=None,
    form_data=None,
    extra_context=None,
):
    """
    Common context for create/edit coupon templates.
    """

    context = {
        "coupon": coupon,

        "form_data": (
            form_data or {}
        ),

        "coupon_types": (
            COUPON_TYPES
        ),

        "coupon_discount_types": (
            COUPON_DISCOUNT_TYPES
        ),

        "coupon_status_values": (
            COUPON_STATUS_VALUES
        ),

        "coupon_batch_rows": (
            build_coupon_batch_rows(
                coupon=coupon,
                form_data=form_data,
            )
        ),
    }

    if extra_context:
        context.update(
            extra_context
        )

    return context