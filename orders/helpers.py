from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from admins.models import Batch
from admins.helpers import calculate_student_cart_totals

from students.models import Cart

from .models import (
    Order,
    OrderItem,
    OrderCoupon,
    StudentBatchPurchase,
)

# ============================================================
# CHECKOUT CONSTANTS
# ============================================================

ZERO = Decimal("0.00")


# ============================================================
# STUDENT CHECKOUT ACCESS
# ============================================================

def is_student_user(user):
    """
    Only normal student accounts can use checkout.
    """

    return (
        user.is_authenticated
        and not user.is_staff
        and not user.is_superuser
    )


# ============================================================
# GET STUDENT CART
# ============================================================

def get_student_cart(user):
    """
    Get or create the student's cart.
    """

    cart, created = Cart.objects.get_or_create(
        student=user
    )

    return cart


# ============================================================
# GET CURRENT CHECKOUT DATA
# ============================================================

def get_checkout_data(user):
    """
    Recalculate the cart exactly like the existing cart page.

    Checkout never trusts an old browser-side amount.
    """

    cart = get_student_cart(user)

    cart_items = list(
        cart.items
        .select_related("batch")
        .prefetch_related(
            "batch__subjects",
            "batch__assigned_teachers__teacher",
        )
    )

    # --------------------------------------------------------
    # EMPTY CART
    # --------------------------------------------------------

    if not cart_items:
        return {
            "cart": cart,
            "cart_items": [],
            "totals": None,
            "purchased_batches": [],
            "unavailable_batches": [],
        }

    # --------------------------------------------------------
    # REUSE EXISTING CART COUPON CALCULATION
    # --------------------------------------------------------

    totals = calculate_student_cart_totals(
        cart,
        cart_items,
        user,
    )

    # --------------------------------------------------------
    # CHECK ALREADY PURCHASED BATCHES
    # --------------------------------------------------------

    batch_ids = [
        item.batch_id
        for item in cart_items
    ]

    purchased_batch_ids = set(
        StudentBatchPurchase.objects.filter(
            student=user,
            batch_id__in=batch_ids,
            status=StudentBatchPurchase.Status.ACTIVE,
        ).values_list(
            "batch_id",
            flat=True,
        )
    )

    purchased_batches = [
        item.batch
        for item in cart_items
        if item.batch_id in purchased_batch_ids
    ]

    # --------------------------------------------------------
    # CHECK MARKETPLACE AVAILABILITY
    # --------------------------------------------------------

    unavailable_batches = [
        item.batch
        for item in cart_items
        if (
            item.batch.batch_status != "published"
            or not item.batch.marketplace_visible
            or item.batch.marketplace_status != "buy_now"
        )
    ]

    return {
        "cart": cart,
        "cart_items": cart_items,
        "totals": totals,
        "purchased_batches": purchased_batches,
        "unavailable_batches": unavailable_batches,
    }


# ============================================================
# PHONE VALIDATION HELPER
# ============================================================

def _validate_optional_phone(value, field_name, errors):
    """
    Validate an OPTIONAL Indian mobile number.

    Rules (only applied if a value was entered):
        - After removing +91 / spaces / dashes / brackets,
          it must be exactly 10 digits.
        - It must start with 6, 7, 8, or 9.

    If the value is empty, no error is added.
    """

    value = (value or "").strip()

    if not value:
        return ""

    normalized = (
        value
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if normalized.startswith("+91"):
        digits = normalized[3:]
    elif normalized.startswith("91") and len(normalized) == 12:
        digits = normalized[2:]
    else:
        digits = normalized

    if not digits.isdigit():
        errors[field_name] = "Enter a valid phone number."

    elif len(digits) != 10:
        errors[field_name] = (
            "Phone number must contain 10 digits."
        )

    elif digits[0] not in "6789":
        errors[field_name] = (
            "Enter a valid Indian mobile number."
        )

    return digits


# ============================================================
# CHECKOUT VALIDATION
# ============================================================

def validate_checkout_data(
    user,
    full_name,
    email,
    phone,
    alternative_phone,
    terms_accepted,
):
    """
    Server-side validation for every checkout field.

    Main phone is REQUIRED.
    Alternative phone is OPTIONAL.

    Returns:
        errors = {
            "full_name": "...",
            "email": "...",
            "phone": "...",
            "alternative_phone": "...",
            "terms_accepted": "...",
        }
    """

    errors = {}

    # --------------------------------------------------------
    # FULL NAME
    # --------------------------------------------------------

    full_name = (full_name or "").strip()

    if not full_name:

        errors["full_name"] = (
            "Full name is required."
        )

    elif len(full_name) < 2:

        errors["full_name"] = (
            "Full name must contain at least 2 characters."
        )

    elif len(full_name) > 200:

        errors["full_name"] = (
            "Full name cannot exceed 200 characters."
        )

    elif any(
        char.isdigit()
        for char in full_name
    ):

        errors["full_name"] = (
            "Full name cannot contain numbers."
        )

    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    email = (email or "").strip().lower()

    if not email:

        errors["email"] = (
            "Email address is required."
        )

    elif len(email) > 254:

        errors["email"] = (
            "Email address is too long."
        )

    else:

        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        try:

            validate_email(email)

        except ValidationError:

            errors["email"] = (
                "Enter a valid email address."
            )

    # --------------------------------------------------------
    # PHONE (REQUIRED)
    # --------------------------------------------------------

    phone = (phone or "").strip()

    if not phone:

        errors["phone"] = (
            "Phone number is required."
        )

        main_digits = ""

    else:

        main_digits = _validate_optional_phone(
            phone,
            "phone",
            errors,
        )

    # --------------------------------------------------------
    # ALTERNATIVE PHONE (OPTIONAL)
    # --------------------------------------------------------

    alt_digits = _validate_optional_phone(
        alternative_phone,
        "alternative_phone",
        errors,
    )

    # --------------------------------------------------------
    # SAME NUMBER CHECK
    # --------------------------------------------------------

    if (
        main_digits
        and alt_digits
        and not errors.get("phone")
        and not errors.get("alternative_phone")
        and main_digits == alt_digits
    ):

        errors["alternative_phone"] = (
            "Alternative phone number must be "
            "different from the main phone number."
        )

    # --------------------------------------------------------
    # TERMS
    # --------------------------------------------------------

    if not terms_accepted:

        errors["terms_accepted"] = (
            "You must accept the Terms & Conditions "
            "before continuing."
        )

    return errors

# ============================================================
# BUILD ORDER SNAPSHOT
# ============================================================


@transaction.atomic
def build_order_from_cart(
    user,
    full_name,
    email,
    phone,
    alternative_phone,
    terms_accepted,
):
    """
    Revalidate the cart and create the local pending Order
    and OrderItems.

    Razorpay is NOT called here.

    This function only creates the NeoLearn-side order.
    """

    # --------------------------------------------------------
    # RELOAD CURRENT CHECKOUT DATA
    # --------------------------------------------------------

    checkout = get_checkout_data(user)

    cart = checkout["cart"]
    cart_items = checkout["cart_items"]
    totals = checkout["totals"]

    # --------------------------------------------------------
    # EMPTY CART
    # --------------------------------------------------------

    if not cart_items:
        raise ValueError(
            "Your cart is empty."
        )

    # --------------------------------------------------------
    # ALREADY PURCHASED
    # --------------------------------------------------------

    if checkout["purchased_batches"]:

        names = ", ".join(
            batch.batch_name
            for batch in checkout["purchased_batches"]
        )

        raise ValueError(
            f"You have already purchased: {names}."
        )

    # --------------------------------------------------------
    # BATCH NO LONGER AVAILABLE
    # --------------------------------------------------------

    if checkout["unavailable_batches"]:

        names = ", ".join(
            batch.batch_name
            for batch in checkout["unavailable_batches"]
        )

        raise ValueError(
            "The following batch(es) are no longer "
            f"available for purchase: {names}."
        )

    # --------------------------------------------------------
    # FINAL TOTALS
    # --------------------------------------------------------

    subtotal = Decimal(
        str(
            totals.get(
                "subtotal",
                ZERO,
            )
        )
    )

    discount_total = Decimal(
        str(
            totals.get(
                "discount_total",
                ZERO,
            )
        )
    )

    final_total = Decimal(
        str(
            totals.get(
                "total",
                ZERO,
            )
        )
    )

    # --------------------------------------------------------
    # COUPON DISCOUNT
    # --------------------------------------------------------

    coupon_discount = ZERO

    for applied_coupon in totals.get(
        "applied_coupons",
        [],
    ):

        if not isinstance(
            applied_coupon,
            dict,
        ):
            continue

        value = (
            applied_coupon.get("discount")
            or applied_coupon.get("discount_amount")
            or ZERO
        )

        try:

            coupon_discount += Decimal(
                str(value)
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):

            continue

    # --------------------------------------------------------
    # NEVER ALLOW NEGATIVE TOTAL
    # --------------------------------------------------------

    if final_total < ZERO:
        final_total = ZERO

    # --------------------------------------------------------
    # NORMALIZE PHONE VALUES
    # --------------------------------------------------------

    phone_clean = (
        phone or ""
    ).strip()

    alternative_phone_clean = (
        alternative_phone or ""
    ).strip()

    # --------------------------------------------------------
    # CREATE LOCAL ORDER
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # Order model does NOT contain an email field.
    # Therefore email is intentionally NOT passed to
    # Order.objects.create().
    #
    # The checkout email is still validated by
    # validate_checkout_data() before this function runs.
    # --------------------------------------------------------

    order = Order.objects.create(

        user=user,

        status=Order.Status.PENDING,

        full_name=full_name.strip(),

        phone=phone_clean,

        alternative_phone=(
            alternative_phone_clean
        ),

        subtotal=subtotal,

        total_coupon_discount=(
            coupon_discount
        ),

        total_discount=(
            discount_total
        ),

        final_amount=(
            final_total
        ),

        currency="INR",

        terms_accepted=(
            terms_accepted
        ),
    )

    # --------------------------------------------------------
    # SAVE HISTORICAL COUPON SNAPSHOTS
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # This stores the coupon information that was actually
    # applied at the time this order was created.
    #
    # Refund logic should use this historical snapshot later,
    # instead of depending on the current Coupon model/cart.
    # --------------------------------------------------------

    for applied_coupon in totals.get(
        "applied_coupons",
        [],
    ):

        if not isinstance(
            applied_coupon,
            dict,
        ):
            continue

        coupon = applied_coupon.get(
            "coupon"
        )

        if coupon is None:
            continue

        discount_amount = (
            applied_coupon.get(
                "discount_amount"
            )
            or applied_coupon.get(
                "discount"
            )
            or ZERO
        )

        try:

            discount_amount = Decimal(
                str(
                    discount_amount
                )
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):

            discount_amount = ZERO

        applied_batch = applied_coupon.get(
            "batch"
        )

        applied_batch_name = ""

        if applied_batch is not None:

            applied_batch_name = (
                getattr(
                    applied_batch,
                    "batch_name",
                    "",
                )
                or ""
            )

        OrderCoupon.objects.create(

            order=order,

            coupon_code=(
                getattr(
                    coupon,
                    "code",
                    "",
                )
                or ""
            ),

            coupon_description=(
                getattr(
                    coupon,
                    "description",
                    "",
                )
                or ""
            ),

            coupon_type=(
                getattr(
                    coupon,
                    "coupon_type",
                    "",
                )
                or ""
            ),

            discount_type=(
                getattr(
                    coupon,
                    "discount_type",
                    "",
                )
                or ""
            ),

            discount_value=(
                getattr(
                    coupon,
                    "discount_value",
                    ZERO,
                )
                or ZERO
            ),

            discount_amount=(
                discount_amount
            ),

            minimum_order_amount=(
                getattr(
                    coupon,
                    "minimum_order_amount",
                    ZERO,
                )
                or ZERO
            ),

            maximum_order_amount=(
                getattr(
                    coupon,
                    "maximum_order_amount",
                    None,
                )
            ),

            maximum_discount_amount=(
                getattr(
                    coupon,
                    "maximum_discount_amount",
                    None,
                )
            ),

            usage_limit=(
                getattr(
                    coupon,
                    "usage_limit",
                    None,
                )
            ),

            per_user_limit=(
                getattr(
                    coupon,
                    "per_user_limit",
                    None,
                )
            ),

            valid_from=(
                getattr(
                    coupon,
                    "valid_from",
                    None,
                )
            ),

            valid_until=(
                getattr(
                    coupon,
                    "valid_until",
                    None,
                )
            ),

            applied_batch=(
                applied_batch
            ),

            applied_batch_name=(
                applied_batch_name
            ),
        )

    # --------------------------------------------------------
    # CREATE ORDER ITEMS
    # --------------------------------------------------------

    for cart_item in cart_items:

        batch = cart_item.batch

        # ----------------------------------------------------
        # BATCH ORIGINAL / REFERENCE PRICE
        #
        # Example:
        # original_price = 40000
        # ----------------------------------------------------

        original_price = Decimal(
            str(
                batch.original_price
            )
        )

        # ----------------------------------------------------
        # ACTUAL CURRENT SELLING PRICE
        #
        # Example:
        # final_price = 32000
        # ----------------------------------------------------

        final_price = Decimal(
            str(
                batch.final_price
            )
        )

        # ----------------------------------------------------
        # BATCH-LEVEL DISCOUNT
        #
        # Example:
        # 40000 - 32000 = 8000
        # ----------------------------------------------------

        batch_discount = (
            original_price
            - final_price
        )

        if batch_discount < ZERO:
            batch_discount = ZERO

        # ----------------------------------------------------
        # ORDER ITEM
        # ----------------------------------------------------

        OrderItem.objects.create(

            order=order,

            batch=batch,

            batch_name=batch.batch_name,

            original_price=(
                original_price
            ),

            batch_discount=(
                batch_discount
            ),

            coupon_discount=(
                ZERO
            ),

            final_price=(
                final_price
            ),
        )

    return order