from decimal import Decimal, InvalidOperation
from datetime import timedelta

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
    Refund,
    RefundItem,
    RefundAttempt,
    Payment,
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
        # IMPORTANT:
        # This is the marketplace reference/crossed price.
        # It is NOT the refund base.
        # ----------------------------------------------------

        original_price = Decimal(
            str(
                batch.original_price
            )
        )

        # ----------------------------------------------------
        # ACTUAL CURRENT SELLING PRICE
        #
        # This is the real batch selling price before any
        # checkout coupon.
        # ----------------------------------------------------

        selling_price = Decimal(
            str(
                batch.final_price
            )
        )

        if selling_price < ZERO:
            selling_price = ZERO

        # ----------------------------------------------------
        # BATCH-LEVEL DISCOUNT
        #
        # original_price is only the marketplace reference
        # price, while selling_price is the actual price.
        # ----------------------------------------------------

        batch_discount = (
            original_price
            - selling_price
        )

        if batch_discount < ZERO:
            batch_discount = ZERO

        # ----------------------------------------------------
        # BATCH-SPECIFIC COUPON
        #
        # Only a batch_specific coupon belonging to this exact
        # batch is allocated to OrderItem.
        #
        # General and multi_checkout coupons remain at the
        # OrderCoupon / Order level.
        # ----------------------------------------------------

        item_coupon_discount = ZERO

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

            coupon_type = (
                getattr(
                    coupon,
                    "coupon_type",
                    "",
                )
                or ""
            )

            # Only batch-specific coupons belong to an item.
            if coupon_type != "batch_specific":
                continue

            applied_batch = applied_coupon.get(
                "batch"
            )

            # The coupon must belong to this exact batch.
            if (
                applied_batch is None
                or applied_batch.pk != batch.pk
            ):
                continue

            discount_value = (
                applied_coupon.get(
                    "discount_amount"
                )
                or applied_coupon.get(
                    "discount"
                )
                or ZERO
            )

            try:
                discount_value = Decimal(
                    str(
                        discount_value
                    )
                )

            except (
                InvalidOperation,
                TypeError,
                ValueError,
            ):
                discount_value = ZERO

            if discount_value < ZERO:
                discount_value = ZERO

            item_coupon_discount += discount_value

        # ----------------------------------------------------
        # NEVER ALLOW ITEM PRICE BELOW ZERO
        # ----------------------------------------------------

        if item_coupon_discount > selling_price:
            item_coupon_discount = selling_price

        # ----------------------------------------------------
        # HISTORICAL ACTUAL PAID AMOUNT
        #
        # This is the amount that will later be used for
        # batch-level refunds.
        # ----------------------------------------------------

        item_final_price = (
            selling_price
            - item_coupon_discount
        )

        if item_final_price < ZERO:
            item_final_price = ZERO

        OrderItem.objects.create(
            order=order,
            batch=batch,
            batch_name=batch.batch_name,
            original_price=original_price,
            batch_discount=batch_discount,
            coupon_discount=item_coupon_discount,
            final_price=item_final_price,
        )

    return order


# ============================================================
# REFUND ENGINE
# ============================================================

REFUND_WINDOW_DAYS = 7

REFUND_POLICY_SINGLE_BATCH_FULL = "single_batch_full"
REFUND_POLICY_MULTI_BATCH_PARTIAL_FULL = "multi_batch_partial_full"
REFUND_POLICY_MULTI_CHECKOUT_FULL = "multi_checkout_full"


# ============================================================
# REFUND DEADLINE
# ============================================================

def get_refund_deadline(order):
    """
    Return the exact refund deadline for an order.

    Refund eligibility is based on the original NeoLearn order
    creation time plus 7 days.
    """

    return (
        order.created_at
        + timedelta(
            days=REFUND_WINDOW_DAYS
        )
    )


# ============================================================
# REFUND WINDOW
# ============================================================

def is_refund_window_open(order):
    """
    Return True when the order is still inside the 7-day
    refund window.
    """

    if not order.created_at:
        return False

    return timezone.now() <= get_refund_deadline(
        order
    )


# ============================================================
# GET ORDER COUPON SNAPSHOTS
# ============================================================

def get_order_coupon_snapshots(order):
    """
    Return historical coupon snapshots for the order.

    Refund logic must use OrderCoupon rather than the current
    Coupon model.
    """

    return list(
        order.coupons.all()
    )


# ============================================================
# CHECK MULTI-CHECKOUT COUPON
# ============================================================

def has_multi_checkout_coupon(order):
    """
    Return True when this order contains a historical
    multi_checkout coupon.
    """

    return any(
        coupon.coupon_type == "multi_checkout"
        for coupon in get_order_coupon_snapshots(order)
    )


# ============================================================
# CHECK BATCH-SPECIFIC COUPON
# ============================================================

def has_batch_specific_coupon(order):
    """
    Return True when the order contains a historical
    batch-specific coupon.
    """

    return any(
        coupon.coupon_type == "batch_specific"
        for coupon in get_order_coupon_snapshots(order)
    )


# ============================================================
# GET ORDER ITEM COUNT
# ============================================================

def get_order_item_count(order):
    """
    Return the total number of batches/items in the order.
    """

    return order.items.count()


# ============================================================
# REFUND POLICY
# ============================================================

def get_refund_policy(order):
    """
    Determine which refund policy applies to an order.

    Rules:

    1. Single batch:
       Full refund only.

    2. Multiple batches + multi_checkout coupon:
       Full order refund only.

    3. Multiple batches without multi_checkout:
       Partial or full refund.

    General coupons are expected to be used only with
    single-batch checkout by the existing checkout rules.
    """

    item_count = get_order_item_count(
        order
    )

    if item_count <= 1:
        return REFUND_POLICY_SINGLE_BATCH_FULL

    if has_multi_checkout_coupon(
        order
    ):
        return REFUND_POLICY_MULTI_CHECKOUT_FULL

    return REFUND_POLICY_MULTI_BATCH_PARTIAL_FULL


# ============================================================
# REFUND POLICY FLAGS
# ============================================================

def refund_allows_partial(order):
    """
    Return True when individual batches can be refunded.
    """

    return (
        get_refund_policy(order)
        == REFUND_POLICY_MULTI_BATCH_PARTIAL_FULL
    )


def refund_allows_full(order):
    """
    Return True when the complete order can be refunded.
    """

    return True


# ============================================================
# GET REFUND-BLOCKING STATUSES
# ============================================================

def get_refund_blocking_statuses():
    """
    Refund statuses that reserve an OrderItem from being
    refunded again.

    REQUESTED and PROCESSING must block duplicate requests
    because the previous refund is still active.

    COMPLETED permanently consumes that refundable amount.
    """

    return (
        Refund.Status.REQUESTED,
        Refund.Status.PROCESSING,
        Refund.Status.COMPLETED,
    )


# ============================================================
# GET ALREADY REFUNDED / RESERVED ITEM IDS
# ============================================================

def get_reserved_refund_item_ids(
    order,
    exclude_refund_id=None,
):
    """
    Return OrderItem IDs that are already reserved by a
    REQUESTED, PROCESSING, or COMPLETED refund.

    When exclude_refund_id is provided, that particular refund
    is ignored.

    This is required when editing an existing REQUESTED refund,
    because its own RefundItems must become selectable again.
    """

    queryset = RefundItem.objects.filter(
        refund__order=order,
        refund__status__in=(
            get_refund_blocking_statuses()
        ),
    )

    if exclude_refund_id is not None:
        queryset = queryset.exclude(
            refund_id=exclude_refund_id,
        )

    return set(
        queryset.values_list(
            "order_item_id",
            flat=True,
        )
    )

# ============================================================
# GET REFUNDABLE ITEM IDS
# ============================================================

def get_refundable_order_item_ids(
    order,
    exclude_refund_id=None,
):
    """
    Return IDs of currently refundable OrderItems.

    When editing an existing REQUESTED refund,
    exclude_refund_id allows that refund's own items
    to become selectable again.
    """

    return set(
        get_refundable_order_items(
            order,
            exclude_refund_id=exclude_refund_id,
        ).values_list(
            "id",
            flat=True,
        )
    )

# ============================================================
# GET HISTORICAL ITEM REFUND AMOUNT
# ============================================================

def get_order_item_refund_amount(order_item):
    """
    Return the historical amount actually paid for this batch.

    Refunds NEVER use:

    - current Batch.final_price
    - current Coupon
    - Batch.original_price

    They use the historical OrderItem.final_price.
    """

    amount = (
        order_item.final_price
    )

    try:
        amount = Decimal(
            str(amount)
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        amount = ZERO

    if amount < ZERO:
        amount = ZERO

    return amount

# ============================================================
# CALCULATE PARTIAL REFUND
# ============================================================

def calculate_partial_refund_amount(
    order,
    order_item_ids,
    exclude_refund_id=None,
):
    """
    Calculate the refund amount for selected batches.

    Partial refund rules:

        - Order must support partial refunds.
        - There must be at least TWO refundable batches.
        - Selected batches must be FEWER than all refundable
          batches.
        - Selecting every refundable batch is NOT a partial
          refund. The student must use Full Refund.
        - Amount is always calculated from historical
          OrderItem.final_price.

    Examples:

        refundable = 2
        selected = 1
        -> allowed

        refundable = 3
        selected = 1
        -> allowed

        refundable = 3
        selected = 2
        -> allowed

        refundable = 3
        selected = 3
        -> rejected

        refundable = 1
        selected = 1
        -> rejected
    """

    # --------------------------------------------------------
    # PARTIAL REFUND POLICY
    # --------------------------------------------------------

    if not refund_allows_partial(
        order
    ):
        raise ValueError(
            "This order can only be refunded as a complete order."
        )

    # --------------------------------------------------------
    # SELECTION REQUIRED
    # --------------------------------------------------------

    if not order_item_ids:
        raise ValueError(
            "Select at least one batch to refund."
        )

    # --------------------------------------------------------
    # NORMALIZE SELECTED IDS
    # --------------------------------------------------------

    try:
        selected_ids = {
            int(item_id)
            for item_id in order_item_ids
        }

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid refund item selection."
        )

    # --------------------------------------------------------
    # GET CURRENTLY REFUNDABLE ITEMS
    #
    # When editing a REQUESTED refund, exclude that refund
    # from the reservation calculation.
    # --------------------------------------------------------

    refundable_ids = (
        get_refundable_order_item_ids(
            order,
            exclude_refund_id=exclude_refund_id,
        )
    )

    # --------------------------------------------------------
    # AT LEAST TWO REFUNDABLE BATCHES
    #
    # Partial refund is impossible when only one refundable
    # batch remains.
    # --------------------------------------------------------

    if len(refundable_ids) <= 1:
        raise ValueError(
            "A partial refund requires at least two refundable "
            "batches. Choose Full Refund to refund the remaining batch."
        )

    # --------------------------------------------------------
    # SELECTED BATCHES MUST BE FEWER THAN ALL REFUNDABLE
    #
    # IMPORTANT:
    #
    # selected < refundable
    #
    # Therefore:
    #
    # 2 refundable / 1 selected -> allowed
    # 3 refundable / 2 selected -> allowed
    # 3 refundable / 3 selected -> rejected
    # --------------------------------------------------------

    if len(selected_ids) >= len(refundable_ids):
        raise ValueError(
            "Partial refund must include fewer than all batches. "
            "Choose Full Refund to refund every batch."
        )

    # --------------------------------------------------------
    # EVERY SELECTED ITEM MUST BE REFUNDABLE
    # --------------------------------------------------------

    invalid_ids = (
        selected_ids
        - refundable_ids
    )

    if invalid_ids:
        raise ValueError(
            "One or more selected batches are no longer "
            "available for refund."
        )

    # --------------------------------------------------------
    # GET SELECTED ORDER ITEMS
    # --------------------------------------------------------

    items = (
        order.items
        .filter(
            id__in=selected_ids
        )
        .order_by("id")
    )

    # --------------------------------------------------------
    # CALCULATE HISTORICAL REFUND AMOUNT
    # --------------------------------------------------------

    total = ZERO

    for order_item in items:

        total += get_order_item_refund_amount(
            order_item
        )

    # --------------------------------------------------------
    # AMOUNT MUST BE POSITIVE
    # --------------------------------------------------------

    if total <= ZERO:
        raise ValueError(
            "The selected batches have no refundable amount."
        )

    return total

# ============================================================
# CALCULATE FULL REFUND
# ============================================================

def calculate_full_refund_amount(
    order,
    exclude_refund_id=None,
):
    """
    Calculate the amount for a full order refund.

    When editing an existing REQUESTED refund,
    exclude_refund_id prevents that refund from blocking
    its own refundable amount.
    """

    if not refund_allows_full(order):
        raise ValueError(
            "This order cannot be refunded as a complete order."
        )

    amount = get_full_order_refund_amount(
        order,
        exclude_refund_id=exclude_refund_id,
    )

    if amount <= ZERO:
        raise ValueError(
            "This order has no refundable amount."
        )

    return amount

# ============================================================
# VALIDATE REFUND REQUEST
# ============================================================

def validate_refund_request(
    order,
    *,
    order_item_ids=None,
    full_order=False,
    exclude_refund_id=None,
):
    """
    Validate a student refund request before creating or
    updating Refund / RefundItem records.

    Parameters:

        order:
            The Order being refunded.

        order_item_ids:
            Selected OrderItem IDs for a partial refund.

        full_order:
            True when requesting a complete refund.

        exclude_refund_id:
            Existing REQUESTED refund ID that should be ignored
            while calculating refundable items.

            This is used only when editing an existing refund
            request.

    Returns:

        {
            "policy": ...,
            "refund_type": ...,
            "items": [...],
            "amount": Decimal(...)
        }
    """

    # --------------------------------------------------------
    # ORDER MUST BE PAID OR ALREADY PARTIALLY REFUNDED
    # --------------------------------------------------------

    if order.status not in (
        Order.Status.PAID,
        Order.Status.PARTIALLY_REFUNDED,
    ):
        raise ValueError(
            "This order is not eligible for a refund."
        )

    # --------------------------------------------------------
    # 7-DAY REFUND WINDOW
    # --------------------------------------------------------

    if not is_refund_window_open(
        order
    ):
        raise ValueError(
            "The 7-day refund period has expired."
        )

    # --------------------------------------------------------
    # DETERMINE REFUND POLICY
    # --------------------------------------------------------

    policy = get_refund_policy(
        order
    )

    # ========================================================
    # FULL ORDER REFUND
    # ========================================================

    if full_order:

        # ----------------------------------------------------
        # CALCULATE FULL REFUND
        #
        # IMPORTANT:
        # When editing an existing REQUESTED refund,
        # exclude that refund from the calculation so that
        # its own items do not block themselves.
        # ----------------------------------------------------

        amount = calculate_full_refund_amount(
            order,
            exclude_refund_id=exclude_refund_id,
        )

        # ----------------------------------------------------
        # GET REFUNDABLE ITEMS
        # ----------------------------------------------------

        items = list(
            get_refundable_order_items(
                order,
                exclude_refund_id=exclude_refund_id,
            )
        )

        if not items:
            raise ValueError(
                "There are no refundable batches in this order."
            )

        return {
            "policy": policy,
            "refund_type": "full",
            "items": items,
            "amount": amount,
        }

    # ========================================================
    # PARTIAL REFUND
    # ========================================================

    if policy != REFUND_POLICY_MULTI_BATCH_PARTIAL_FULL:
        raise ValueError(
            "This order only supports a full refund."
        )

    # --------------------------------------------------------
    # SELECTION REQUIRED
    # --------------------------------------------------------

    if not order_item_ids:
        raise ValueError(
            "Select at least one batch to refund."
        )

    # --------------------------------------------------------
    # CALCULATE PARTIAL AMOUNT
    #
    # This also validates:
    #
    # - at least two refundable batches
    # - selected < refundable
    # - selected IDs are refundable
    # - amount is positive
    #
    # When editing an existing REQUESTED refund,
    # that refund is excluded from the reservation check.
    # --------------------------------------------------------

    amount = calculate_partial_refund_amount(
        order,
        order_item_ids,
        exclude_refund_id=exclude_refund_id,
    )

    # --------------------------------------------------------
    # NORMALIZE SELECTED IDS
    # --------------------------------------------------------

    selected_ids = {
        int(item_id)
        for item_id in order_item_ids
    }

    # --------------------------------------------------------
    # GET SELECTED ITEMS
    # --------------------------------------------------------

    items = list(
        order.items
        .filter(
            id__in=selected_ids
        )
        .order_by("id")
    )

    # --------------------------------------------------------
    # FINAL SAFETY CHECK
    # --------------------------------------------------------

    if not items:
        raise ValueError(
            "No valid batches were selected for refund."
        )

    return {
        "policy": policy,
        "refund_type": "partial",
        "items": items,
        "amount": amount,
    }
    
# ============================================================
# GET FULL ORDER REFUND AMOUNT
# ============================================================

def get_full_order_refund_amount(
    order,
    exclude_refund_id=None,
):
    """
    Calculate the currently refundable amount for a complete
    order refund.

    Parameters:

        order:
            The Order being refunded.

        exclude_refund_id:
            Existing REQUESTED refund ID that should be ignored
            while calculating refundable items.

            This is required when editing an existing REQUESTED
            full refund.

    Rules:

        1. Single-batch order:
           Refund the exact historical Order.final_amount.

        2. Multiple batches + multi_checkout coupon:
           Refund the complete historical Order.final_amount.

        3. Multiple batches without multi_checkout:
           Refund the sum of the currently refundable
           OrderItem.final_price values.

    Important:

        Refund calculations NEVER use current batch prices
        or current coupon values.

        They use historical order values.
    """

    # --------------------------------------------------------
    # DETERMINE REFUND POLICY
    # --------------------------------------------------------

    policy = get_refund_policy(order)

    # --------------------------------------------------------
    # SINGLE-BATCH ORDER
    # --------------------------------------------------------
    #
    # A single-batch order can have a general coupon.
    #
    # General coupons are order-level discounts, so the exact
    # amount actually paid is stored in Order.final_amount.
    #
    # When editing an existing REQUESTED refund, exclude that
    # refund from the refundable-item reservation check.
    # --------------------------------------------------------

    if policy == REFUND_POLICY_SINGLE_BATCH_FULL:

        refundable_items = get_refundable_order_items(
            order,
            exclude_refund_id=exclude_refund_id,
        )

        if not refundable_items.exists():
            return ZERO

        amount = order.final_amount

        try:
            amount = Decimal(
                str(amount)
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            amount = ZERO

        if amount < ZERO:
            amount = ZERO

        return amount

    # --------------------------------------------------------
    # MULTI-CHECKOUT ORDER
    # --------------------------------------------------------
    #
    # Multi-checkout discount cannot safely be allocated
    # between individual batches.
    #
    # Therefore this order is refundable only as one complete
    # order.
    #
    # When editing an existing REQUESTED refund, that refund
    # must not block itself.
    # --------------------------------------------------------

    if policy == REFUND_POLICY_MULTI_CHECKOUT_FULL:

        existing_completed_refund = (
            Refund.objects.filter(
                order=order,
                status=Refund.Status.COMPLETED,
            )
            .exclude(
                pk=exclude_refund_id,
            )
            .exists()
        )

        existing_processing_refund = (
            Refund.objects.filter(
                order=order,
                status=Refund.Status.PROCESSING,
            )
            .exclude(
                pk=exclude_refund_id,
            )
            .exists()
        )

        existing_requested_refund = (
            Refund.objects.filter(
                order=order,
                status=Refund.Status.REQUESTED,
            )
            .exclude(
                pk=exclude_refund_id,
            )
            .exists()
        )

        if (
            existing_completed_refund
            or existing_processing_refund
            or existing_requested_refund
        ):
            return ZERO

        amount = order.final_amount

        try:
            amount = Decimal(
                str(amount)
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            amount = ZERO

        if amount < ZERO:
            amount = ZERO

        return amount

    # --------------------------------------------------------
    # NORMAL MULTI-BATCH ORDER
    # --------------------------------------------------------
    #
    # Every batch has its own historical OrderItem.final_price.
    #
    # Previous completed refunds and other active refund
    # requests are excluded.
    #
    # When editing an existing REQUESTED refund, that refund's
    # own items are made refundable again.
    # --------------------------------------------------------

    refundable_items = get_refundable_order_items(
        order,
        exclude_refund_id=exclude_refund_id,
    )

    total = ZERO

    for order_item in refundable_items:
        total += get_order_item_refund_amount(
            order_item
        )

    if total < ZERO:
        total = ZERO

    return total

# ============================================================
# GET REFUNDABLE ORDER ITEMS
# ============================================================

def get_refundable_order_items(
    order,
    exclude_refund_id=None,
):
    """
    Return OrderItems that are still refundable.

    An OrderItem is refundable only when:

        - its StudentBatchPurchase is still ACTIVE
        - it does not belong to another REQUESTED refund
        - it does not belong to another PROCESSING refund
        - it does not belong to another COMPLETED refund

    When exclude_refund_id is provided, that particular refund
    is ignored.

    This is required when editing an existing REQUESTED refund,
    because the existing refund's own items must become
    selectable again.
    """

    # --------------------------------------------------------
    # GET ITEMS ALREADY RESERVED BY OTHER REFUNDS
    # --------------------------------------------------------

    reserved_item_ids = get_reserved_refund_item_ids(
        order,
        exclude_refund_id=exclude_refund_id,
    )

    # --------------------------------------------------------
    # GET CURRENTLY ACTIVE PURCHASE ITEMS
    #
    # Only ACTIVE StudentBatchPurchase records remain
    # refundable.
    # --------------------------------------------------------

    active_purchase_item_ids = set(
        StudentBatchPurchase.objects.filter(
            order=order,
            student=order.user,
            status=StudentBatchPurchase.Status.ACTIVE,
        ).values_list(
            "order_item_id",
            flat=True,
        )
    )

    # --------------------------------------------------------
    # NO ACTIVE PURCHASES
    # --------------------------------------------------------

    if not active_purchase_item_ids:
        return order.items.none()

    # --------------------------------------------------------
    # REMOVE ITEMS ALREADY RESERVED / REFUNDED
    # --------------------------------------------------------

    refundable_item_ids = (
        active_purchase_item_ids
        - reserved_item_ids
    )

    # --------------------------------------------------------
    # NOTHING LEFT TO REFUND
    # --------------------------------------------------------

    if not refundable_item_ids:
        return order.items.none()

    # --------------------------------------------------------
    # RETURN REFUNDABLE ORDER ITEMS
    # --------------------------------------------------------

    return (
        order.items
        .select_related(
            "batch",
        )
        .filter(
            id__in=refundable_item_ids,
        )
        .order_by("id")
    )

# ============================================================
# REFUND REQUEST LIFECYCLE
# ============================================================
#
# Refund       = one student refund request / one permanent
#                refund_number.
# RefundAttempt = one provider/Razorpay processing attempt for
#                 that same refund request.
#
# Therefore:
#   Edit REQUESTED refund       -> same Refund + same number
#   Provider retry             -> same Refund + new Attempt
#   Provider failure/cancel    -> Attempt changes only; parent
#                                 Refund remains PROCESSING
#   Successful provider refund -> Attempt COMPLETED + parent
#                                 Refund COMPLETED
#   Rejected request + new request later -> NEW Refund + NEW
#                                           refund_number
#
# ============================================================


def get_active_refund_requests(order):
    """
    Return refund requests that currently reserve refundable items.

    REJECTED refunds do not block a new request.
    New provider failures/cancellations are stored on RefundAttempt,
    so the parent Refund remains PROCESSING and continues to reserve
    its RefundItems.
    """
    return (
        Refund.objects.filter(
            order=order,
            status__in=get_refund_blocking_statuses(),
        )
        .prefetch_related("items", "attempts")
        .order_by("-requested_at", "-pk")
    )


def get_latest_refund_attempt(refund):
    """Return the latest provider attempt for a refund, or None."""
    return (
        refund.attempts
        .order_by("-attempt_number", "-started_at", "-pk")
        .first()
    )


def get_next_refund_attempt_number(refund):
    """Return the next attempt number for this parent Refund."""
    latest = get_latest_refund_attempt(refund)
    if latest is None:
        return 1
    return latest.attempt_number + 1


def get_refund_request_state(refund):
    """
    Return stable parent/attempt state for views and templates.

    The parent Refund status is the student-facing state.
    Attempt status is internal provider/audit state.
    """
    latest_attempt = get_latest_refund_attempt(refund)

    if refund.status == Refund.Status.REQUESTED:
        student_status = "requested"
    elif refund.status == Refund.Status.PROCESSING:
        student_status = "processing"
    elif refund.status == Refund.Status.COMPLETED:
        student_status = "completed"
    elif refund.status == Refund.Status.REJECTED:
        student_status = "rejected"
    else:
        # Legacy parent-level FAILED records are retained only for
        # compatibility. New provider failures must use attempts.
        student_status = "failed"

    retryable = (
        refund.status == Refund.Status.PROCESSING
        and (
            latest_attempt is None
            or latest_attempt.status
            in (
                RefundAttempt.Status.FAILED,
                RefundAttempt.Status.CANCELLED,
            )
        )
    )

    return {
        "refund": refund,
        "status": refund.status,
        "latest_attempt": latest_attempt,
        "has_retryable_attempt": retryable,
        "student_status": student_status,
    }


def get_student_refund_for_order(order, *, include_rejected=True):
    """
    Return the newest Refund request for an order.

    Rejected requests remain historical records. A later student
    request creates a new Refund with a new permanent refund_number.
    """
    queryset = Refund.objects.filter(order=order)

    if not include_rejected:
        queryset = queryset.exclude(status=Refund.Status.REJECTED)

    return (
        queryset
        .prefetch_related("items", "attempts")
        .order_by("-requested_at", "-pk")
        .first()
    )


def has_blocking_refund_request(order, *, exclude_refund_id=None):
    """
    Return True when a REQUESTED, PROCESSING, or COMPLETED refund
    currently reserves refundable items on the order.

    REJECTED refunds do not block a new request.
    """
    queryset = Refund.objects.filter(
        order=order,
        status__in=get_refund_blocking_statuses(),
    )

    if exclude_refund_id is not None:
        queryset = queryset.exclude(pk=exclude_refund_id)

    return queryset.exists()


@transaction.atomic
def create_refund_request(
    order,
    student,
    *,
    reason,
    order_item_ids=None,
    full_order=False,
):
    """
    Create one new student refund request.

    A new Refund is created only for a genuinely new request. The
    Refund model generates its permanent unique refund_number.

    Existing REQUESTED / PROCESSING / COMPLETED refunds block an
    overlapping request. REJECTED refunds do not.
    """
    locked_order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if locked_order.user_id != student.pk:
        raise ValueError(
            "You are not allowed to request a refund for this order."
        )

    if has_blocking_refund_request(locked_order):
        raise ValueError(
            "A refund request is already active for this order."
        )

    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Refund reason is required.")

    validation = validate_refund_request(
        locked_order,
        order_item_ids=order_item_ids,
        full_order=full_order,
    )

    refund = Refund.objects.create(
        order=locked_order,
        student=student,
        reason=reason,
        status=Refund.Status.REQUESTED,
        requested_amount=validation["amount"],
        refunded_amount=ZERO,
    )

    RefundItem.objects.bulk_create([
        RefundItem(
            refund=refund,
            order_item=order_item,
            refund_amount=get_order_item_refund_amount(order_item),
        )
        for order_item in validation["items"]
    ])

    return refund


@transaction.atomic
def update_requested_refund(
    refund,
    *,
    reason,
    order_item_ids=None,
    full_order=False,
):
    """
    Edit an existing REQUESTED refund.

    IMPORTANT: this does NOT create a second Refund and does NOT
    change refund_number. It updates the same Refund and replaces
    its RefundItems.
    """
    locked_refund = (
        Refund.objects
        .select_for_update()
        .select_related("order", "student")
        .get(pk=refund.pk)
    )

    if locked_refund.status != Refund.Status.REQUESTED:
        raise ValueError(
            "Only a pending refund request can be edited."
        )

    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Refund reason is required.")

    validation = validate_refund_request(
        locked_refund.order,
        order_item_ids=order_item_ids,
        full_order=full_order,
        exclude_refund_id=locked_refund.pk,
    )

    locked_refund.reason = reason
    locked_refund.requested_amount = validation["amount"]
    locked_refund.refunded_amount = ZERO
    locked_refund.save(
        update_fields=[
            "reason",
            "requested_amount",
            "refunded_amount",
        ]
    )

    locked_refund.items.all().delete()

    RefundItem.objects.bulk_create([
        RefundItem(
            refund=locked_refund,
            order_item=order_item,
            refund_amount=get_order_item_refund_amount(order_item),
        )
        for order_item in validation["items"]
    ])

    return locked_refund


def can_create_new_refund_request(order):
    """Return whether a new refund request is currently allowed."""
    return not has_blocking_refund_request(order)


@transaction.atomic
def begin_refund_attempt(refund, *, requested_amount=None):
    """
    Create the next provider attempt for an existing Refund.

    First processing:
        Refund REQUESTED -> PROCESSING + Attempt #1 PROCESSING

    Retry after failure/cancellation:
        Same Refund -> new Attempt #N PROCESSING

    A second simultaneous PROCESSING attempt is blocked.
    """
    locked_refund = (
        Refund.objects
        .select_for_update()
        .get(pk=refund.pk)
    )

    if locked_refund.status not in (
        Refund.Status.REQUESTED,
        Refund.Status.PROCESSING,
    ):
        raise ValueError("This refund cannot be processed again.")

    latest_attempt = get_latest_refund_attempt(locked_refund)

    if (
        latest_attempt is not None
        and latest_attempt.status == RefundAttempt.Status.PROCESSING
    ):
        raise ValueError("A refund attempt is already processing.")

    if requested_amount is None:
        requested_amount = locked_refund.requested_amount

    try:
        requested_amount = Decimal(str(requested_amount))
    except (InvalidOperation, TypeError, ValueError):
        requested_amount = ZERO

    if requested_amount <= ZERO:
        raise ValueError("Refund amount must be greater than zero.")

    attempt = RefundAttempt.objects.create(
        refund=locked_refund,
        attempt_number=get_next_refund_attempt_number(locked_refund),
        status=RefundAttempt.Status.PROCESSING,
        requested_amount=requested_amount,
        refunded_amount=ZERO,
    )

    if locked_refund.status != Refund.Status.PROCESSING:
        locked_refund.status = Refund.Status.PROCESSING
        locked_refund.save(update_fields=["status"])

    return attempt


@transaction.atomic
def record_refund_attempt_failed(
    attempt,
    *,
    error_message="",
    admin_note="",
):
    """
    Mark a provider attempt FAILED.

    The parent Refund intentionally remains PROCESSING so the admin
    can retry the same refund request using a new RefundAttempt.
    """
    locked_attempt = (
        RefundAttempt.objects
        .select_for_update()
        .select_related("refund")
        .get(pk=attempt.pk)
    )

    if locked_attempt.status != RefundAttempt.Status.PROCESSING:
        raise ValueError(
            "Only a processing refund attempt can be marked failed."
        )

    locked_attempt.status = RefundAttempt.Status.FAILED
    locked_attempt.error_message = (error_message or "").strip()
    locked_attempt.admin_note = (admin_note or "").strip()
    locked_attempt.processed_at = timezone.now()
    locked_attempt.save(update_fields=[
        "status",
        "error_message",
        "admin_note",
        "processed_at",
    ])

    return locked_attempt


@transaction.atomic
def record_refund_attempt_cancelled(
    attempt,
    *,
    error_message="",
    admin_note="",
):
    """
    Mark a provider attempt CANCELLED.

    The parent Refund remains PROCESSING and can be retried.
    """
    locked_attempt = (
        RefundAttempt.objects
        .select_for_update()
        .select_related("refund")
        .get(pk=attempt.pk)
    )

    if locked_attempt.status != RefundAttempt.Status.PROCESSING:
        raise ValueError(
            "Only a processing refund attempt can be cancelled."
        )

    locked_attempt.status = RefundAttempt.Status.CANCELLED
    locked_attempt.error_message = (error_message or "").strip()
    locked_attempt.admin_note = (admin_note or "").strip()
    locked_attempt.processed_at = timezone.now()
    locked_attempt.save(update_fields=[
        "status",
        "error_message",
        "admin_note",
        "processed_at",
    ])

    return locked_attempt


@transaction.atomic
def record_refund_attempt_completed(
    attempt,
    *,
    razorpay_refund_id,
    refunded_amount,
    admin_note="",
):
    """
    Complete a successful provider attempt and its parent Refund.

    Only a successful completion changes financial/order state.
    """
    locked_attempt = (
        RefundAttempt.objects
        .select_for_update()
        .select_related("refund")
        .get(pk=attempt.pk)
    )

    if locked_attempt.status != RefundAttempt.Status.PROCESSING:
        raise ValueError(
            "Only a processing refund attempt can be completed."
        )

    locked_refund = (
        Refund.objects
        .select_for_update()
        .get(pk=locked_attempt.refund_id)
    )

    if locked_refund.status != Refund.Status.PROCESSING:
        raise ValueError("This refund is no longer processing.")

    try:
        refunded_amount = Decimal(str(refunded_amount))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid refunded amount.")

    if refunded_amount <= ZERO:
        raise ValueError("Refunded amount must be greater than zero.")

    razorpay_refund_id = (razorpay_refund_id or "").strip()
    if not razorpay_refund_id:
        raise ValueError(
            "Razorpay refund ID is required for a completed refund."
        )

    now = timezone.now()

    locked_attempt.status = RefundAttempt.Status.COMPLETED
    locked_attempt.refunded_amount = refunded_amount
    locked_attempt.razorpay_refund_id = razorpay_refund_id
    locked_attempt.admin_note = (admin_note or "").strip()
    locked_attempt.processed_at = now
    locked_attempt.save(update_fields=[
        "status",
        "refunded_amount",
        "razorpay_refund_id",
        "admin_note",
        "processed_at",
    ])

    locked_refund.status = Refund.Status.COMPLETED
    locked_refund.refunded_amount = refunded_amount
    locked_refund.razorpay_refund_id = razorpay_refund_id
    locked_refund.processed_at = now
    locked_refund.save(update_fields=[
        "status",
        "refunded_amount",
        "razorpay_refund_id",
        "processed_at",
    ])

    order = (
        Order.objects
        .select_for_update()
        .get(pk=locked_refund.order_id)
    )

    payment = (
        Payment.objects
        .select_for_update()
        .filter(order_id=order.pk)
        .first()
    )

    # Sum all completed parent refunds for this order, including the
    # refund that has just completed.
    completed_total = ZERO
    completed_refunds = Refund.objects.filter(
        order_id=order.pk,
        status=Refund.Status.COMPLETED,
    ).only("refunded_amount")

    for completed_refund in completed_refunds:
        try:
            completed_total += Decimal(
                str(completed_refund.refunded_amount or ZERO)
            )
        except (InvalidOperation, TypeError, ValueError):
            continue

    order_total = Decimal(str(order.final_amount or ZERO))

    if completed_total >= order_total:
        order.status = Order.Status.REFUNDED
    else:
        order.status = Order.Status.PARTIALLY_REFUNDED

    order.save(update_fields=["status", "updated_at"])

    if payment is not None:
        payment_total = Decimal(str(payment.amount or ZERO))
        if completed_total >= payment_total:
            payment.status = Payment.Status.REFUNDED
        else:
            payment.status = Payment.Status.PARTIALLY_REFUNDED

        payment.save(update_fields=["status", "updated_at"])

    refund_item_ids = list(
        locked_refund.items.values_list("order_item_id", flat=True)
    )

    if refund_item_ids:
        StudentBatchPurchase.objects.filter(
            order_id=order.pk,
            student_id=locked_refund.student_id,
            order_item_id__in=refund_item_ids,
        ).update(
            status=StudentBatchPurchase.Status.REFUNDED,
            refunded_at=now,
        )

    return locked_refund


def get_refund_attempt_history(refund):
    """Return all provider attempts in chronological order for admin UI."""
    return refund.attempts.order_by("attempt_number", "started_at", "pk")


# ============================================================
# RAZORPAY REFUND PROVIDER LOOKUP
# ============================================================


def fetch_razorpay_refund(payment_id, refund_id):
    """
    Fetch the current Razorpay refund object for an existing provider refund.

    This is a read-only provider lookup. It does not change any NeoLearn
    database state. The caller decides how the returned provider status
    should update RefundAttempt / Refund.
    """
    from django.conf import settings
    import razorpay

    payment_id = (payment_id or "").strip()
    refund_id = (refund_id or "").strip()

    if not payment_id:
        raise ValueError("Razorpay payment ID is required.")

    if not refund_id:
        raise ValueError("Razorpay refund ID is required.")

    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise ValueError("Razorpay credentials are not configured.")

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )

    return client.payment.fetch_refund_id(
        payment_id,
        refund_id,
    )
