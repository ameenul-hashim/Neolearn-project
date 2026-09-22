from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Q
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
# COUPON HELPERS — COMPLETE REPLACEMENT
# =========================================================


# =========================================================
# COUPON CONSTANTS
# =========================================================

COUPON_MAX_PERCENTAGE = Decimal("100.00")

COUPON_TYPES = {
    "general",
    "batch_specific",
    "multi_checkout",
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
    All money values are converted to a whole rupee.

    Examples:
        3000.00 -> 3000
        3000.33 -> 3000
        3000.99 -> 3000

    This keeps cart totals, discounts and checkout amounts
    consistent without decimal paise.
    """
    if value is None:
        return Decimal("0")

    try:
        value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")

    if not value.is_finite():
        return Decimal("0")

    if value < Decimal("0"):
        value = Decimal("0")

    # Remove everything after the decimal point.
    return value.quantize(
        Decimal("1"),
        rounding="ROUND_DOWN",
    )


def _integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _get_post_value(request, *names, default=""):
    for name in names:
        value = request.POST.get(name)

        if value is not None:
            return value

    return default


def _get_file_value(request, *names):
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

    if amount < Decimal("0"):
        errors.append(f"{field_name} cannot be negative.")
        return None

    return _money(amount)


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
        errors.append(
            f"{field_name} must be a whole number."
        )
        return None

    try:
        number = int(value)
    except (ValueError, TypeError):
        errors.append(
            f"{field_name} must be a whole number."
        )
        return None

    if number < 0:
        errors.append(
            f"{field_name} cannot be negative."
        )
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
    value = str(value or "").strip()

    if not value:
        errors.append(
            f"{field_name} is required."
        )
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
# COUPON CODE
# =========================================================

def normalize_coupon_code(code):
    return str(code or "").strip().upper()


def validate_coupon_code(
    code,
    errors,
    *,
    coupon=None,
):
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

    if not all(
        character.isalnum() or character in "-_"
        for character in code
    ):
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
# MARKETPLACE BATCHES
# =========================================================

def get_coupon_batches():
    return (
        Batch.objects
        .filter(
            batch_status="published",
            marketplace_visible=True,
        )
        .order_by("batch_name")
    )


# =========================================================
# BATCH PRICE
# =========================================================

def get_batch_selling_price(batch):
    if batch is None:
        return Decimal("0")

    price = getattr(batch, "final_price", None)

    if price is None or price <= Decimal("0"):
        price = getattr(
            batch,
            "original_price",
            Decimal("0"),
        )

    return _money(price)


def get_batch_current_price(batch):
    return get_batch_selling_price(batch)


# =========================================================
# COUPON VALIDITY
# =========================================================

def coupon_usage_limit_reached(coupon):
    limit = coupon.usage_limit

    if limit is None:
        return False

    return (
        _integer(coupon.used_count)
        >= _integer(limit)
    )


def is_coupon_currently_valid(coupon):
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
    if coupon.status != "active":
        return False

    if not coupon.is_active:
        return False

    if not coupon.valid_from:
        return False

    return timezone.now() < coupon.valid_from


def is_coupon_expired(coupon):
    if not coupon.valid_until:
        return False

    return timezone.now() > coupon.valid_until


# =========================================================
# PER STUDENT USAGE
# =========================================================

def student_coupon_usage_limit_reached(
    coupon,
    student,
):
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
    selling_price = _money(selling_price)
    discount_value = _money(discount_value)

    if selling_price <= Decimal("0"):
        return {
            "valid": False,
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": (
                "Selling price must be greater than zero."
            ),
        }

    if discount_value <= Decimal("0"):
        return {
            "valid": False,
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": (
                "Discount value must be greater than zero."
            ),
        }

    if discount_type == "fixed":

        if discount_value > selling_price:
            return {
                "valid": False,
                "discount_amount": Decimal("0"),
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
                "discount_amount": Decimal("0"),
                "final_price": selling_price,
                "reason": (
                    "Percentage discount cannot exceed 100%."
                ),
            }

        discount_amount = (
            selling_price
            * discount_value
            / Decimal("100")
        )

    else:
        return {
            "valid": False,
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": "Invalid coupon discount type.",
        }

    discount_amount = min(
        discount_amount,
        selling_price,
    )

    discount_amount = _money(discount_amount)

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
# GENERAL / MULTI CHECKOUT DISCOUNT
# =========================================================

def calculate_coupon_discount(
    coupon,
    selling_price,
):
    selling_price = _money(selling_price)

    if coupon.status != "active":
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": "Coupon is inactive.",
        }

    if not coupon.is_active:
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": "Coupon is inactive.",
        }

    now = timezone.now()

    if coupon.valid_from and now < coupon.valid_from:
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": "Coupon has not started yet.",
        }

    if coupon.valid_until and now > coupon.valid_until:
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": "Coupon has expired.",
        }

    if coupon_usage_limit_reached(coupon):
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
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
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": (
                f"Minimum order amount is "
                f"₹{minimum_order:,.0f}."
            ),
        }

    if (
        coupon.coupon_type == "general"
        and maximum_order is not None
        and selling_price > _money(maximum_order)
    ):
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": (
                f"Maximum order amount is "
                f"₹{_money(maximum_order):,.0f}."
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
            "discount_amount": Decimal("0"),
            "final_price": selling_price,
            "reason": result["reason"],
        }

    return {
        "eligible": True,
        "discount_amount": _money(
            result["discount_amount"]
        ),
        "final_price": _money(
            result["final_price"]
        ),
        "reason": "",
    }


# =========================================================
# BATCH-SPECIFIC ELIGIBILITY
# =========================================================

def is_coupon_batch_eligible(
    coupon,
    batch,
):
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
    if batch is None:
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": Decimal("0"),
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
            "discount_amount": Decimal("0"),
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
                "discount_amount": Decimal("0"),
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
# COUPON BATCH RULES
# =========================================================

def get_coupon_enabled_batch_ids(coupon):
    return set(
        coupon.batch_rules
        .filter(is_enabled=True)
        .values_list(
            "batch_id",
            flat=True,
        )
    )


def get_coupon_selected_batch(coupon):
    rule = (
        coupon.batch_rules
        .filter(is_enabled=True)
        .select_related("batch")
        .first()
    )

    if rule is None:
        return None

    return rule.batch


def save_coupon_batch_rules(
    *,
    coupon,
    coupon_type,
    selected_batch=None,
    enabled_batch_ids=None,
):
    coupon.batch_rules.all().delete()

    if coupon_type == "multi_checkout":
        return

    if coupon_type == "batch_specific":

        if selected_batch is None:
            return

        CouponBatchRule.objects.create(
            coupon=coupon,
            batch=selected_batch,
            is_enabled=True,
        )

        return

    enabled_batch_ids = enabled_batch_ids or []

    for batch_id in enabled_batch_ids:

        try:
            batch_id = int(batch_id)
        except (TypeError, ValueError):
            continue

        try:
            batch = get_coupon_batches().get(
                pk=batch_id
            )
        except Batch.DoesNotExist:
            continue

        CouponBatchRule.objects.create(
            coupon=coupon,
            batch=batch,
            is_enabled=True,
        )


# =========================================================
# BATCH FORM ROWS
# =========================================================

def build_coupon_batch_rows(
    *,
    coupon=None,
    form_data=None,
):
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
                selected_batch_id = selected_batch.pk

    if form_data is not None:

        if hasattr(form_data, "getlist"):
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
                    batch.pk == selected_batch_id
                ),
            }
        )

    return rows


# =========================================================
# PARSE + VALIDATE COUPON
# =========================================================

def parse_and_validate_coupon(
    request,
    *,
    coupon=None,
):
    errors = []
    now = timezone.now()

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

    if (
        coupon is not None
        and coupon_type != coupon.coupon_type
    ):
        errors.append(
            "Coupon type cannot be changed after creation."
        )

        coupon_type = coupon.coupon_type

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

        if discount_value <= Decimal("0"):
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

    maximum_discount_amount = None

    if minimum_order_amount is None:
        minimum_order_amount = Decimal("0")

    # -----------------------------------------------------
    # GENERAL
    # -----------------------------------------------------

    if coupon_type == "general":

        if (
            maximum_order_amount is not None
            and maximum_order_amount
            < minimum_order_amount
        ):
            errors.append(
                "Maximum order amount cannot be less "
                "than minimum order amount."
            )

    # -----------------------------------------------------
    # BATCH SPECIFIC
    # -----------------------------------------------------

    selected_batch = None

    if coupon_type == "batch_specific":

        selected_batch_value = (
            _get_post_value(
                request,
                "batch_specific_batch",
                "selected_batch",
            )
        )

        if not selected_batch_value:
            errors.append(
                "Please select a batch for the batch-specific coupon."
            )

        else:

            try:
                selected_batch = (
                    get_coupon_batches().get(
                        pk=int(selected_batch_value)
                    )
                )

            except (
                ValueError,
                TypeError,
                Batch.DoesNotExist,
            ):
                errors.append(
                    "Selected batch is invalid."
                )

        if minimum_order_amount > Decimal("0"):
            errors.append(
                "Minimum checkout amount is not used "
                "for batch-specific coupons."
            )

        if maximum_order_amount is not None:
            errors.append(
                "Maximum checkout amount is not used "
                "for batch-specific coupons."
            )

        minimum_order_amount = Decimal("0")
        maximum_order_amount = None

    # -----------------------------------------------------
    # MULTI CHECKOUT
    # -----------------------------------------------------

    if coupon_type == "multi_checkout":

        if minimum_order_amount <= Decimal("0"):
            errors.append(
                "Minimum checkout amount is required "
                "for Multi Checkout coupons."
            )

        if maximum_order_amount is None:
            errors.append(
                "Maximum checkout amount is required "
                "for Multi Checkout coupons."
            )

        if (
            maximum_order_amount is not None
            and maximum_order_amount
            < minimum_order_amount
        ):
            errors.append(
                "Maximum checkout amount cannot be less "
                "than minimum checkout amount."
            )

        selected_batch = None

    # -----------------------------------------------------
    # VALIDITY
    # -----------------------------------------------------

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
        and coupon is None
    ):
        errors.append(
            "Valid from date and time cannot be in the past."
        )

    if (
        valid_until is not None
        and valid_until < now
        and coupon is None
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

    # -----------------------------------------------------
    # USAGE LIMITS
    # -----------------------------------------------------

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
            "Per-student usage limit must be greater than zero."
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
        and usage_limit < _integer(coupon.used_count)
    ):
        errors.append(
            "Usage limit cannot be less than "
            f"the current usage count "
            f"({_integer(coupon.used_count)})."
        )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # THUMBNAIL
    # -----------------------------------------------------

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

    if coupon is None and not coupon_thumbnail:
        errors.append(
            "Coupon thumbnail is required."
        )

    # -----------------------------------------------------
    # BATCH RULE INPUT
    # -----------------------------------------------------

    enabled_batch_ids = []

    if hasattr(request.POST, "getlist"):
        enabled_batch_ids = request.POST.getlist(
            "enabled_batch_ids"
        )

    # -----------------------------------------------------
    # BATCH-SPECIFIC MARKETPLACE VISIBILITY
    # -----------------------------------------------------

    marketplace_visible_raw = (
        _get_post_value(
            request,
            "marketplace_visible",
            default="0",
        )
        or "0"
    ).strip().lower()

    marketplace_visible = (
        marketplace_visible_raw
        in {
            "1",
            "true",
            "on",
            "yes",
        }
    )

    if coupon_type != "batch_specific":
        marketplace_visible = False

    # -----------------------------------------------------
    # RETURN
    # -----------------------------------------------------

    data = {
        "code": code,
        "description": description,
        "coupon_type": coupon_type,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "minimum_order_amount": minimum_order_amount,
        "maximum_order_amount": maximum_order_amount,
        "maximum_discount_amount": maximum_discount_amount,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "usage_limit": usage_limit,
        "per_user_limit": per_user_limit,
        "status": status,
        "coupon_thumbnail": coupon_thumbnail,
        "selected_batch": selected_batch,
        "enabled_batch_ids": enabled_batch_ids,
        "marketplace_visible": marketplace_visible,
    }

    return data, errors


# =========================================================
# CREATE COUPON INSTANCE
# =========================================================

def create_coupon_instance(data):
    coupon = Coupon(
        code=data["code"],
        description=data["description"],
        coupon_type=data["coupon_type"],
        discount_type=data["discount_type"],
        discount_value=data["discount_value"],
        minimum_order_amount=data[
            "minimum_order_amount"
        ],
        maximum_order_amount=data[
            "maximum_order_amount"
        ],
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

    if hasattr(
        coupon,
        "marketplace_visible",
    ):
        coupon.marketplace_visible = (
            data.get(
                "marketplace_visible",
                False,
            )
            if data["coupon_type"]
            == "batch_specific"
            else False
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
    coupon.code = data["code"]
    coupon.description = data["description"]

    coupon.coupon_type = data["coupon_type"]

    coupon.discount_type = data["discount_type"]
    coupon.discount_value = data["discount_value"]

    coupon.minimum_order_amount = (
        data["minimum_order_amount"]
    )

    coupon.maximum_order_amount = (
        data["maximum_order_amount"]
    )

    coupon.maximum_discount_amount = None

    coupon.valid_from = data["valid_from"]
    coupon.valid_until = data["valid_until"]

    coupon.usage_limit = data["usage_limit"]
    coupon.per_user_limit = data["per_user_limit"]

    coupon.status = data["status"]

    coupon.is_active = (
        data["status"] == "active"
    )

    if data.get("coupon_thumbnail"):
        coupon.coupon_thumbnail = (
            data["coupon_thumbnail"]
        )

    if hasattr(
        coupon,
        "marketplace_visible",
    ):
        coupon.marketplace_visible = (
            data.get(
                "marketplace_visible",
                False,
            )
            if coupon.coupon_type
            == "batch_specific"
            else False
        )

    coupon.full_clean()
    coupon.save()

    return coupon


# =========================================================
# RECORD SUCCESSFUL COUPON CHECKOUT
# =========================================================

def record_successful_coupon_use(
    coupon,
    discount_amount,
):
    """
    Atomically record one successful coupon checkout.

    This is the function the future successful checkout/payment
    flow should call after the purchase is confirmed.

    It updates:
        used_count
        total_discount_given

    The dashboard therefore shows the actual discount granted,
    including percentage coupons, instead of an estimate.
    """
    discount_amount = _money(
        discount_amount
    )

    if discount_amount < Decimal("0"):
        discount_amount = Decimal("0.00")

    Coupon.objects.filter(
        pk=coupon.pk,
    ).update(
        used_count=F("used_count") + 1,
        total_discount_given=(
            F("total_discount_given")
            + discount_amount
        ),
    )

    coupon.refresh_from_db(
        fields=[
            "used_count",
            "total_discount_given",
        ]
    )

    return coupon


# =========================================================
# COUPON MESSAGES
# =========================================================

def add_coupon_errors_to_messages(
    request,
    errors,
):
    from django.contrib import messages

    for error in errors:
        messages.error(
            request,
            error,
        )


# =========================================================
# COUPON QUERYSET
# =========================================================

def get_coupon_queryset():
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
# COUPON LISTING
# =========================================================

def get_coupon_listing_context(request):
    """
    Build the admin coupon listing queryset.

    Supported GET filters:
        search
        coupon_type:
            general
            batch_specific
            multi_checkout

        status:
            active
            inactive
            upcoming
            expired

        sort:
            newest
            oldest
            a_z
            z_a
            most_used
            expiry_soon

        page
    """
    coupons = get_coupon_queryset()

    search = (
        request.GET.get("search", "")
        .strip()
    )

    coupon_type = (
        request.GET.get("coupon_type", "")
        .strip()
        .lower()
    )

    status = (
        request.GET.get("status", "")
        .strip()
        .lower()
    )

    sort = (
        request.GET.get("sort", "newest")
        .strip()
        .lower()
    )

    # ---------------------------------------------------------
    # SEARCH
    # ---------------------------------------------------------
    if search:
        coupons = coupons.filter(
            Q(code__icontains=search)
            | Q(description__icontains=search)
        )

    # ---------------------------------------------------------
    # COUPON TYPE
    # ---------------------------------------------------------
    if coupon_type in COUPON_TYPES:
        coupons = coupons.filter(
            coupon_type=coupon_type
        )
    else:
        coupon_type = ""

    # ---------------------------------------------------------
    # STATUS
    #
    # Active:
    #   Manually active and currently inside the validity window.
    #
    # Inactive:
    #   Manually deactivated.
    #
    # Upcoming:
    #   Active coupon whose valid_from is still in the future.
    #
    # Expired:
    #   Active coupon whose valid_until has already passed.
    # ---------------------------------------------------------
    now = timezone.now()

    listing_statuses = {
        "active",
        "inactive",
        "upcoming",
        "expired",
    }

    if status not in listing_statuses:
        status = ""

    if status == "inactive":
        coupons = coupons.filter(
            Q(status="inactive")
            | Q(is_active=False)
        )

    elif status == "upcoming":
        coupons = coupons.filter(
            status="active",
            is_active=True,
            valid_from__isnull=False,
            valid_from__gt=now,
        )

    elif status == "expired":
        coupons = coupons.filter(
            status="active",
            is_active=True,
            valid_until__isnull=False,
            valid_until__lt=now,
        )

    elif status == "active":
        coupons = coupons.filter(
            status="active",
            is_active=True,
        ).filter(
            Q(valid_from__isnull=True)
            | Q(valid_from__lte=now)
        ).filter(
            Q(valid_until__isnull=True)
            | Q(valid_until__gte=now)
        )

    # ---------------------------------------------------------
    # DASHBOARD STATISTICS
    #
    # These top-of-page numbers always represent the complete
    # coupon database, not the currently filtered result set.
    # ---------------------------------------------------------
    all_coupons = Coupon.objects.all()

    total_coupons = all_coupons.count()

    active_coupons = all_coupons.filter(
        status="active",
        is_active=True,
    ).filter(
        Q(valid_from__isnull=True)
        | Q(valid_from__lte=now)
    ).filter(
        Q(valid_until__isnull=True)
        | Q(valid_until__gte=now)
    ).count()

    inactive_coupons = all_coupons.filter(
        Q(status="inactive")
        | Q(is_active=False)
    ).count()

    total_usage = sum(
        _integer(coupon.used_count)
        for coupon in all_coupons
    )

    general_coupon_count = all_coupons.filter(
        coupon_type="general"
    ).count()

    batch_specific_coupon_count = all_coupons.filter(
        coupon_type="batch_specific"
    ).count()

    multi_checkout_coupon_count = all_coupons.filter(
        coupon_type="multi_checkout"
    ).count()

    # The actual discount is recorded on the Coupon when a
    # successful checkout is completed. This is deliberately
    # NOT estimated from percentage settings or used_count.
    total_discount_given = sum(
        _money(
            getattr(
                coupon,
                "total_discount_given",
                Decimal("0.00"),
            )
        )
        for coupon in all_coupons
    )

    # Keep filtered counts available for any existing code that
    # still consumes these names.
    total_count = coupons.count()

    active_count = coupons.filter(
        status="active",
        is_active=True,
    ).filter(
        Q(valid_from__isnull=True)
        | Q(valid_from__lte=now)
    ).filter(
        Q(valid_until__isnull=True)
        | Q(valid_until__gte=now)
    ).count()

    inactive_count = coupons.filter(
        Q(status="inactive")
        | Q(is_active=False)
    ).count()

    used_count = sum(
        _integer(coupon.used_count)
        for coupon in coupons
    )

    # ---------------------------------------------------------
    # SORT
    # ---------------------------------------------------------
    allowed_sorts = {
        "newest",
        "oldest",
        "a_z",
        "z_a",
        "most_used",
        "expiry_soon",
    }

    if sort not in allowed_sorts:
        sort = "newest"

    if sort == "oldest":
        coupons = coupons.order_by(
            "created_at",
            "pk",
        )

    elif sort == "a_z":
        coupons = coupons.order_by(
            "code",
            "pk",
        )

    elif sort == "z_a":
        coupons = coupons.order_by(
            "-code",
            "-pk",
        )

    elif sort == "most_used":
        coupons = coupons.order_by(
            "-used_count",
            "-created_at",
            "-pk",
        )

    elif sort == "expiry_soon":
        coupons = coupons.order_by(
            F("valid_until").asc(nulls_last=True),
            "-created_at",
            "-pk",
        )

    else:
        # Newest is the default.
        coupons = coupons.order_by(
            "-created_at",
            "-pk",
        )

    # ---------------------------------------------------------
    # PAGINATION
    # ---------------------------------------------------------
    page_number = request.GET.get(
        "page",
        1,
    )

    paginator = Paginator(
        coupons,
        10,
    )

    try:
        page_obj = paginator.get_page(
            page_number
        )
    except Exception:
        page_obj = paginator.get_page(1)

    # ---------------------------------------------------------
    # PRESERVED QUERY
    # ---------------------------------------------------------
    preserved_params = []

    if search:
        preserved_params.append(
            f"search={search}"
        )

    if coupon_type:
        preserved_params.append(
            f"coupon_type={coupon_type}"
        )

    if status:
        preserved_params.append(
            f"status={status}"
        )

    preserved_params.append(
        f"sort={sort}"
    )

    return {
        "coupons": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,

        "search": search,
        "selected_coupon_type": coupon_type,
        "selected_status": status,
        "sort": sort,

        "coupon_types": [
            "general",
            "batch_specific",
            "multi_checkout",
        ],

        # These are the LISTING filter statuses.
        # Keep COUPON_STATUS_VALUES unchanged because it is also
        # used by create/edit coupon form context.
        "listing_statuses": [
            "active",
            "inactive",
            "upcoming",
            "expired",
        ],

        # Top dashboard cards.
        "total_coupons": total_coupons,
        "active_coupons": active_coupons,
        "inactive_coupons": inactive_coupons,
        "total_usage": total_usage,
        "total_discount_given": total_discount_given,

        # Dynamic type-tab counts.
        "general_coupon_count": general_coupon_count,
        "batch_specific_coupon_count": batch_specific_coupon_count,
        "multi_checkout_coupon_count": multi_checkout_coupon_count,

        # Existing filtered-result statistics retained.
        "total_count": total_count,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "used_count": used_count,

        "preserved_query": "&".join(
            preserved_params
        ),
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
    coupon_batch_rows = build_coupon_batch_rows(
        coupon=coupon,
        form_data=form_data,
    )

    context = {
        "coupon": coupon,
        
        "form_data": form_data or {},

        "coupon_types": sorted(
            COUPON_TYPES
        ),

        "discount_types": sorted(
            COUPON_DISCOUNT_TYPES
        ),

        "coupon_statuses": sorted(
            COUPON_STATUS_VALUES
        ),

        # Current create/edit coupon frontend key.
        "coupon_batch_rows": coupon_batch_rows,

        # Backward-compatible alias for older coupon templates.
        "batch_rows": coupon_batch_rows,
    }

    if coupon is not None:
        context[
            "marketplace_visible"
        ] = bool(
            getattr(
                coupon,
                "marketplace_visible",
                False,
            )
        )

    if extra_context:
        context.update(
            extra_context
        )

    return context


# =========================================================
# CART SUBTOTAL
# =========================================================

def calculate_cart_subtotal(
    cart_items,
):
    """
    Return the complete cart selling-price total.

    This is the authoritative subtotal for the student's full
    cart and is the calculation base for Multi Checkout coupons.
    General and Batch Specific coupon helpers intentionally use
    their own eligibility rules instead of this function directly.
    """
    subtotal = Decimal("0")

    for item in cart_items:
        subtotal += get_batch_selling_price(
            item.batch
        )

    return _money(subtotal)


def get_cart_batch_ids(
    cart_items,
):
    return {
        item.batch_id
        for item in cart_items
    }


# =========================================================
# CART COUPON MODE
# =========================================================

def get_cart_coupon_mode(
    applied_coupons,
):
    modes = set()

    for entry in applied_coupons:

        coupon = getattr(
            entry,
            "coupon",
            entry,
        )

        coupon_type = getattr(
            coupon,
            "coupon_type",
            None,
        )

        if coupon_type in COUPON_TYPES:
            modes.add(coupon_type)

    if not modes:
        return None

    if "general" in modes:
        return "general"

    if "multi_checkout" in modes:
        return "multi_checkout"

    return "batch_specific"


# =========================================================
# GENERAL COUPON FOR CART
# =========================================================

def calculate_general_cart_coupon(
    coupon,
    cart_items,
    student=None,
):
    if coupon.coupon_type != "general":
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": Decimal("0"),
            "eligible_total": Decimal("0"),
            "reason": (
                "This is not a general coupon."
            ),
        }

    if student is not None:
        if student_coupon_usage_limit_reached(
            coupon,
            student,
        ):
            return {
                "eligible": False,
                "discount_amount": Decimal("0"),
                "final_price": Decimal("0"),
                "eligible_total": Decimal("0"),
                "reason": (
                    "You have already reached "
                    "this coupon's usage limit."
                ),
            }

    enabled_batch_ids = (
        get_coupon_enabled_batch_ids(
            coupon
        )
    )

    eligible_total = Decimal("0")

    for item in cart_items:

        if item.batch_id not in enabled_batch_ids:
            continue

        if (
            item.batch.batch_status != "published"
            or not item.batch.marketplace_visible
        ):
            continue

        eligible_total += (
            get_batch_selling_price(
                item.batch
            )
        )

    eligible_total = _money(
        eligible_total
    )

    if eligible_total <= Decimal("0"):
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": eligible_total,
            "eligible_total": eligible_total,
            "reason": (
                "This coupon is not available "
                "for the batches in your cart."
            ),
        }

    result = calculate_coupon_discount(
        coupon,
        eligible_total,
    )

    return {
        "eligible": result["eligible"],
        "discount_amount": _money(
            result["discount_amount"]
        ),
        "final_price": _money(
            result["final_price"]
        ),
        "eligible_total": eligible_total,
        "reason": result["reason"],
    }


# =========================================================
# BATCH-SPECIFIC COUPON FOR CART
# =========================================================

def calculate_batch_coupon_for_cart(
    coupon,
    cart_items,
    student=None,
):
    if coupon.coupon_type != "batch_specific":
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": Decimal("0"),
            "batch": None,
            "reason": (
                "This is not a batch-specific coupon."
            ),
        }

    selected_batch = get_coupon_selected_batch(
        coupon
    )

    if selected_batch is None:
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": Decimal("0"),
            "batch": None,
            "reason": (
                "This coupon is not connected "
                "to a batch."
            ),
        }

    cart_item = next(
        (
            item
            for item in cart_items
            if item.batch_id
            == selected_batch.pk
        ),
        None,
    )

    if cart_item is None:
        return {
            "eligible": False,
            "discount_amount": Decimal("0"),
            "final_price": Decimal("0"),
            "batch": selected_batch,
            "reason": (
                "This coupon is not applicable "
                "to any batch in your cart."
            ),
        }

    result = check_coupon_eligibility(
        coupon,
        selected_batch,
        student=student,
    )

    return {
        "eligible": result["eligible"],
        "discount_amount": _money(
            result["discount_amount"]
        ),
        "final_price": _money(
            result["final_price"]
        ),
        "batch": selected_batch,
        "reason": result["reason"],
    }


# =========================================================
# MULTI CHECKOUT COUPON
# =========================================================

def calculate_multi_checkout_coupon(
    coupon,
    cart_items,
    student=None,
):
    """Validate and calculate one Multi Checkout coupon."""
    zero = Decimal("0")

    if coupon.coupon_type != "multi_checkout":
        return {
            "eligible": False,
            "discount_amount": zero,
            "final_price": zero,
            "eligible_total": zero,
            "reason": "This is not a Multi Checkout coupon.",
        }

    if student is not None and student_coupon_usage_limit_reached(coupon, student):
        return {
            "eligible": False,
            "discount_amount": zero,
            "final_price": zero,
            "eligible_total": zero,
            "reason": "You have already reached this coupon's usage limit.",
        }

    if len(get_cart_batch_ids(cart_items)) < 2:
        return {
            "eligible": False,
            "discount_amount": zero,
            "final_price": zero,
            "eligible_total": zero,
            "reason": "Multi Checkout coupon requires at least two different batches.",
        }

    total_cart_amount = calculate_cart_subtotal(cart_items)

    if total_cart_amount <= zero:
        return {
            "eligible": False,
            "discount_amount": zero,
            "final_price": total_cart_amount,
            "eligible_total": total_cart_amount,
            "reason": "Your checkout total must be greater than zero.",
        }

    minimum_checkout = _money(coupon.minimum_order_amount)
    maximum_checkout = coupon.maximum_order_amount

    if total_cart_amount < minimum_checkout:
        return {
            "eligible": False,
            "discount_amount": zero,
            "final_price": total_cart_amount,
            "eligible_total": total_cart_amount,
            "reason": f"Minimum checkout amount is ₹{minimum_checkout:,.0f}.",
        }

    if maximum_checkout is not None and total_cart_amount > _money(maximum_checkout):
        return {
            "eligible": False,
            "discount_amount": zero,
            "final_price": total_cart_amount,
            "eligible_total": total_cart_amount,
            "reason": f"Maximum checkout amount is ₹{_money(maximum_checkout):,.0f}.",
        }

    result = calculate_coupon_discount(coupon, total_cart_amount)

    if not result["eligible"]:
        return {
            "eligible": False,
            "discount_amount": zero,
            "final_price": total_cart_amount,
            "eligible_total": total_cart_amount,
            "reason": result["reason"],
        }

    return {
        "eligible": True,
        "discount_amount": _money(result["discount_amount"]),
        "final_price": _money(result["final_price"]),
        "eligible_total": total_cart_amount,
        "reason": "",
    }


# =========================================================
# STUDENT CART TOTALS
# =========================================================

def calculate_student_cart_totals(cart, cart_items, student):
    """
    Authoritative temporary cart calculation.

    Rules:
      Single batch:
        - one Batch Specific OR one General
        - Multi Checkout is not allowed

      Multiple batches:
        - one Batch Specific coupon per batch
        - multiple different Batch Specific coupons may coexist
        - one Multi Checkout coupon overall
        - General is not allowed
        - Multi Checkout cannot coexist with Batch Specific
    """
    subtotal = calculate_cart_subtotal(cart_items)
    discount_total = Decimal("0")
    applied_coupons = []
    invalid_coupons = []

    entries = list(
        cart.cart_coupons
        .select_related("coupon", "batch")
        .prefetch_related("coupon__batch_rules__batch")
    )

    general_entries = [e for e in entries if e.coupon.coupon_type == "general"]
    multi_entries = [e for e in entries if e.coupon.coupon_type == "multi_checkout"]
    batch_entries = [e for e in entries if e.coupon.coupon_type == "batch_specific"]
    batch_count = len(get_cart_batch_ids(cart_items))

    # ---------------------------------------------------------
    # Single-batch rules
    # ---------------------------------------------------------
    if batch_count <= 1:
        # General and Batch Specific are alternatives.
        if general_entries:
            selected = general_entries[0]

            for extra in general_entries[1:]:
                invalid_coupons.append({
                    "entry": extra,
                    "reason": "Only one General coupon can be used in one checkout.",
                })
                extra.delete()

            for entry in multi_entries + batch_entries:
                invalid_coupons.append({
                    "entry": entry,
                    "reason": "General coupons cannot be combined with other coupon modes.",
                })
                entry.delete()

            result = calculate_general_cart_coupon(
                selected.coupon,
                cart_items,
                student=student,
            )

            if result["eligible"]:
                discount_total = _money(result["discount_amount"])
                applied_coupons.append({
                    "entry": selected,
                    "coupon": selected.coupon,
                    "discount_amount": _money(result["discount_amount"]),
                    "eligible_total": _money(result["eligible_total"]),
                    "batch": None,
                })
            else:
                invalid_coupons.append({"entry": selected, "reason": result["reason"]})
                selected.delete()

        elif batch_entries:
            # A single batch can have only one Batch Specific coupon.
            selected_batch_id = cart_items[0].batch_id if cart_items else None
            selected = None

            for entry in batch_entries:
                result = calculate_batch_coupon_for_cart(
                    entry.coupon,
                    cart_items,
                    student=student,
                )

                if selected is None and result["eligible"]:
                    selected = entry
                    discount_total += _money(result["discount_amount"])
                    applied_coupons.append({
                        "entry": entry,
                        "coupon": entry.coupon,
                        "discount_amount": _money(result["discount_amount"]),
                        "eligible_total": _money(
                            result["final_price"] + result["discount_amount"]
                        ),
                        "batch": result["batch"],
                    })
                else:
                    invalid_coupons.append({
                        "entry": entry,
                        "reason": (
                            "Only one Batch Specific coupon can be applied "
                            "to the same batch."
                            if result["eligible"]
                            else result["reason"]
                        ),
                    })
                    entry.delete()

            # Multi Checkout can never be present in single-batch cart.
            for entry in multi_entries:
                invalid_coupons.append({
                    "entry": entry,
                    "reason": "Multi Checkout coupons require multiple batches.",
                })
                entry.delete()

        else:
            for entry in multi_entries:
                invalid_coupons.append({
                    "entry": entry,
                    "reason": "Multi Checkout coupons require multiple batches.",
                })
                entry.delete()

    # ---------------------------------------------------------
    # Multiple-batch rules
    # ---------------------------------------------------------
    else:
        if multi_entries:
            # Exactly one checkout-level Multi Checkout coupon.
            selected = multi_entries[0]

            for extra in multi_entries[1:]:
                invalid_coupons.append({
                    "entry": extra,
                    "reason": "Only one Multi Checkout coupon can be used in one checkout.",
                })
                extra.delete()

            # Multi Checkout and Batch Specific are mutually exclusive.
            for entry in batch_entries:
                invalid_coupons.append({
                    "entry": entry,
                    "reason": "Multi Checkout coupons cannot be combined with Batch Specific coupons.",
                })
                entry.delete()

            for entry in general_entries:
                invalid_coupons.append({
                    "entry": entry,
                    "reason": "General coupons are not available for multiple-batch checkout.",
                })
                entry.delete()

            result = calculate_multi_checkout_coupon(
                selected.coupon,
                cart_items,
                student=student,
            )

            if result["eligible"]:
                discount_total = _money(result["discount_amount"])
                applied_coupons.append({
                    "entry": selected,
                    "coupon": selected.coupon,
                    "discount_amount": _money(result["discount_amount"]),
                    "eligible_total": _money(result["eligible_total"]),
                    "batch": None,
                })
            else:
                invalid_coupons.append({"entry": selected, "reason": result["reason"]})
                selected.delete()

        else:
            # Batch Specific mode: one coupon per batch.
            for entry in batch_entries:
                result = calculate_batch_coupon_for_cart(
                    entry.coupon,
                    cart_items,
                    student=student,
                )

                if not result["eligible"]:
                    invalid_coupons.append({"entry": entry, "reason": result["reason"]})
                    entry.delete()
                    continue

                target_batch_id = result["batch"].pk if result["batch"] else None
                duplicate_batch = any(
                    item.get("batch") is not None
                    and item["batch"].pk == target_batch_id
                    for item in applied_coupons
                )

                if duplicate_batch:
                    invalid_coupons.append({
                        "entry": entry,
                        "reason": "Only one Batch Specific coupon can be applied to the same batch.",
                    })
                    entry.delete()
                    continue

                discount_total += _money(result["discount_amount"])
                applied_coupons.append({
                    "entry": entry,
                    "coupon": entry.coupon,
                    "discount_amount": _money(result["discount_amount"]),
                    "eligible_total": _money(
                        result["final_price"] + result["discount_amount"]
                    ),
                    "batch": result["batch"],
                })

            # General is never allowed in a multiple-batch cart.
            for entry in general_entries:
                invalid_coupons.append({
                    "entry": entry,
                    "reason": "General coupons are not available for multiple-batch checkout.",
                })
                entry.delete()

    discount_total = min(_money(discount_total), subtotal)
    total = _money(subtotal - discount_total)

    return {
        "cart": cart,
        "cart_items": cart_items,
        "subtotal": subtotal,
        "discount_total": discount_total,
        "total": total,
        "applied_coupons": applied_coupons,
        "invalid_coupons": invalid_coupons,
    }


# =========================================================
# AVAILABLE STUDENT COUPONS
# =========================================================

def get_available_student_coupons(cart_items, student, applied_entries=None):
    """
    Build the coupon cards for the student's current cart.

    Important application rules:

    - Only Batch Specific coupons connected to a batch that is actually
      present in the cart are listed.
    - A General coupon is usable only for a single-batch cart and only
      when no other coupon mode is already applied.
    - Batch Specific coupons can coexist, but only one coupon may be used
      for each cart batch.
    - Multi Checkout is a checkout-level coupon. It is only relevant when
      the cart contains multiple different batches and cannot coexist with
      General or Batch Specific coupons.
    - Coupons that are relevant to the cart but cannot currently be used
      remain in the list with ``is_available=False`` and a reason. This
      allows the template to show an unavailable/disabled Apply button.
    """
    if not cart_items:
        return []

    coupons = (
        Coupon.objects
        .filter(status="active", is_active=True)
        .prefetch_related("batch_rules__batch")
        .order_by("-created_at", "-pk")
    )

    applied_entries = list(applied_entries or [])
    applied_coupon_ids = {
        entry.coupon_id
        for entry in applied_entries
    }

    cart_batch_ids = get_cart_batch_ids(cart_items)
    multiple_batches = len(cart_batch_ids) > 1

    applied_batch_ids = {
        entry.batch_id
        for entry in applied_entries
        if (
            entry.coupon.coupon_type == "batch_specific"
            and entry.batch_id is not None
        )
    }

    has_batch_specific = any(
        entry.coupon.coupon_type == "batch_specific"
        for entry in applied_entries
    )
    has_multi_checkout = any(
        entry.coupon.coupon_type == "multi_checkout"
        for entry in applied_entries
    )
    has_general = any(
        entry.coupon.coupon_type == "general"
        for entry in applied_entries
    )

    catalog = []

    for coupon in coupons:
        # Applied coupons are already rendered in the Applied section.
        if coupon.pk in applied_coupon_ids:
            continue

        # Do not list expired/upcoming/inactive/usage-exhausted coupons.
        if not is_coupon_currently_valid(coupon):
            continue

        if student_coupon_usage_limit_reached(coupon, student):
            continue

        item = {
            "coupon": coupon,
            "discount_amount": _money(0),
            "batch": None,
            "is_available": False,
            "reason": "",
        }

        # ---------------------------------------------------------
        # GENERAL
        # ---------------------------------------------------------
        if coupon.coupon_type == "general":
            # General coupons belong only to the single-batch checkout mode.
            # For a multiple-batch cart, do not display them at all.
            if multiple_batches:
                continue

            if has_batch_specific or has_multi_checkout:
                item["reason"] = (
                    "Remove the currently applied coupon before using a General coupon."
                )
                catalog.append(item)
                continue

            if has_general:
                item["reason"] = (
                    "Only one General coupon can be applied at a time."
                )
                catalog.append(item)
                continue

            result = calculate_general_cart_coupon(
                coupon,
                cart_items,
                student=student,
            )

            item["discount_amount"] = _money(
                result.get("discount_amount", 0)
            )

            if result["eligible"]:
                item["is_available"] = True
            else:
                item["reason"] = result.get(
                    "reason",
                    "This coupon is not available for your cart.",
                )

            catalog.append(item)
            continue

        # ---------------------------------------------------------
        # BATCH SPECIFIC
        # ---------------------------------------------------------
        if coupon.coupon_type == "batch_specific":
            if not getattr(coupon, "marketplace_visible", False):
                continue

            selected_batch = get_coupon_selected_batch(coupon)

            # IMPORTANT: only show Batch Specific coupons whose selected
            # batch is actually present in this student's cart.
            if selected_batch is None:
                continue

            if selected_batch.pk not in cart_batch_ids:
                continue

            item["batch"] = selected_batch

            if has_general or has_multi_checkout:
                item["reason"] = (
                    "Remove the currently applied coupon before using a Batch Specific coupon."
                )
                catalog.append(item)
                continue

            if selected_batch.pk in applied_batch_ids:
                item["reason"] = (
                    "A Batch Specific coupon is already applied to this batch."
                )
                catalog.append(item)
                continue

            result = calculate_batch_coupon_for_cart(
                coupon,
                cart_items,
                student=student,
            )

            item["discount_amount"] = _money(
                result.get("discount_amount", 0)
            )

            if result["eligible"]:
                item["is_available"] = True
            else:
                item["reason"] = result.get(
                    "reason",
                    "This coupon is not available for this batch.",
                )

            catalog.append(item)
            continue

        # ---------------------------------------------------------
        # MULTI CHECKOUT
        # ---------------------------------------------------------
        if coupon.coupon_type == "multi_checkout":
            # Multi Checkout belongs only to the multiple-batch checkout mode.
            # For a single-batch cart, do not display it at all.
            if not multiple_batches:
                continue

            if has_general or has_batch_specific:
                item["reason"] = (
                    "Remove the currently applied coupon before using a Multi Checkout coupon."
                )
                catalog.append(item)
                continue

            if has_multi_checkout:
                item["reason"] = (
                    "Only one Multi Checkout coupon can be applied at a time."
                )
                catalog.append(item)
                continue

            result = calculate_multi_checkout_coupon(
                coupon,
                cart_items,
                student=student,
            )

            item["discount_amount"] = _money(
                result.get("discount_amount", 0)
            )

            if result["eligible"]:
                item["is_available"] = True
            else:
                item["reason"] = result.get(
                    "reason",
                    "This coupon is not available for your checkout.",
                )

            catalog.append(item)
            continue

    # Keep Batch Specific coupons grouped first, then General, then
    # Multi Checkout. Within each group, higher discount value comes first.
    priority = {
        "batch_specific": 1,
        "general": 2,
        "multi_checkout": 3,
    }

    catalog.sort(
        key=lambda item: (
            priority.get(item["coupon"].coupon_type, 99),
            0 if item["is_available"] else 1,
            -item["discount_amount"],
            item["coupon"].code.lower(),
        )
    )

    return catalog

def toggle_coupon_status(coupon):
    """
    Toggle the active/inactive state of a coupon.
    """

    coupon.is_active = not coupon.is_active

    if coupon.is_active:
        coupon.status = "active"
    else:
        coupon.status = "inactive"

    coupon.save(
        update_fields=[
            "is_active",
            "status",
        ]
    )

    return coupon


# =========================================================
# COUPON ADMIN ACTIONS
# =========================================================

def can_delete_coupon(coupon):
    """
    A coupon can only be permanently deleted
    when it has never been used.
    """

    return _integer(coupon.used_count) == 0


def delete_coupon(coupon):
    """
    Permanently delete a coupon.

    Used coupons are protected so historical
    coupon usage is not destroyed.
    """

    if not can_delete_coupon(coupon):
        raise ValidationError(
            "Used coupons cannot be deleted."
        )

    coupon.delete()

    return True
