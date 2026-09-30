from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from admins.models import Batch

from .razorpay_utils import create_razorpay_refund
from students.models import Cart
from .models import (
    Order,
    OrderItem,
    OrderCoupon,
    Payment,
    StudentBatchPurchase,
    Refund,
    RefundItem,
    RefundAttempt,
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
    from admins.helpers import calculate_student_cart_totals
    
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
# REFUND EXECUTION ENGINE
# ============================================================


def _decimal_amount(value):
    """
    Safely convert a value to Decimal.
    """
    try:
        amount = Decimal(str(value))
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return ZERO

    if amount < ZERO:
        return ZERO

    return amount


def _serialize_gateway_response(response):
    """
    Convert Razorpay's response into JSON-safe data for
    RefundAttempt.gateway_response.
    """

    if response is None:
        return None

    if isinstance(response, dict):
        return response

    try:
        return dict(response)
    except (TypeError, ValueError):
        return {
            "response": str(response),
        }


def _get_next_refund_attempt_number(refund):
    """
    Return the next sequential attempt number for this refund.
    """

    last_attempt = (
        RefundAttempt.objects
        .filter(refund=refund)
        .order_by("-attempt_number")
        .first()
    )

    if not last_attempt:
        return 1

    return last_attempt.attempt_number + 1


def _get_completed_refunded_amount(order, exclude_refund_id=None):
    """
    Return the total amount already successfully refunded
    for this order.

    Only COMPLETED refunds count.

    Failed Razorpay attempts do not reduce the refundable
    amount because they did not move any money.
    """

    queryset = Refund.objects.filter(
        order=order,
        status=Refund.Status.COMPLETED,
    )

    if exclude_refund_id is not None:
        queryset = queryset.exclude(
            pk=exclude_refund_id,
        )

    total = ZERO

    for refund in queryset:
        total += _decimal_amount(
            refund.refunded_amount
        )

    return total


def _get_payment_for_refund(order):
    """
    Return the payment associated with the order.
    """

    try:
        return order.payment
    except Payment.DoesNotExist:
        return None


def _mark_refund_attempt_failed(
    *,
    refund_id,
    attempt_id,
    error_message,
    gateway_response=None,
):
    """
    Record a failed Razorpay attempt.

    IMPORTANT:
    The Refund itself goes back to REQUESTED.

    This means Admin can retry the same Refund later.
    """

    with transaction.atomic():

        refund = (
            Refund.objects
            .select_for_update()
            .get(pk=refund_id)
        )

        attempt = (
            RefundAttempt.objects
            .select_for_update()
            .get(pk=attempt_id)
        )

        attempt.status = RefundAttempt.Status.FAILED
        attempt.error_message = (
            str(error_message or "")
        )
        attempt.gateway_response = (
            _serialize_gateway_response(
                gateway_response
            )
        )
        attempt.completed_at = timezone.now()

        attempt.save(
            update_fields=[
                "status",
                "error_message",
                "gateway_response",
                "completed_at",
            ]
        )

        # --------------------------------------------------------
        # IMPORTANT:
        # Razorpay failure does NOT mean the business refund
        # request itself has permanently failed.
        #
        # It becomes REQUESTED again so Admin can retry/reject.
        # --------------------------------------------------------

        if refund.status == Refund.Status.PROCESSING:

            refund.status = Refund.Status.REQUESTED

            refund.save(
                update_fields=[
                    "status",
                ]
            )

        return refund


def _complete_refund_successfully(
    *,
    refund_id,
    attempt_id,
    gateway_response,
):
    """
    Finalize a successful Razorpay refund.

    This function performs all NeoLearn-side success updates
    only AFTER Razorpay has successfully created the refund.
    """

    with transaction.atomic():

        refund = (
            Refund.objects
            .select_for_update()
            .select_related("order", "student")
            .get(pk=refund_id)
        )

        attempt = (
            RefundAttempt.objects
            .select_for_update()
            .get(pk=attempt_id)
        )

        order = (
            Order.objects
            .select_for_update()
            .get(pk=refund.order_id)
        )

        payment = _get_payment_for_refund(order)

        # --------------------------------------------------------
        # PREVENT DUPLICATE FINALIZATION
        # --------------------------------------------------------

        if refund.status == Refund.Status.COMPLETED:

            return refund

        # --------------------------------------------------------
        # GET RAZORPAY REFUND ID
        # --------------------------------------------------------

        razorpay_refund_id = None

        if isinstance(gateway_response, dict):

            razorpay_refund_id = (
                gateway_response.get("id")
                or gateway_response.get(
                    "refund_id"
                )
            )

        if not razorpay_refund_id:

            raise ValueError(
                "Razorpay refund succeeded but no "
                "refund ID was returned."
            )

        # --------------------------------------------------------
        # AMOUNT
        # --------------------------------------------------------

        successful_amount = _decimal_amount(
            attempt.amount
        )

        if successful_amount <= ZERO:

            raise ValueError(
                "Successful refund amount must be greater than zero."
            )

        # --------------------------------------------------------
        # COMPLETE REFUND
        # --------------------------------------------------------

        refund.status = Refund.Status.COMPLETED
        refund.refunded_amount = successful_amount
        refund.razorpay_refund_id = (
            razorpay_refund_id
        )
        refund.processed_at = timezone.now()

        refund.save(
            update_fields=[
                "status",
                "refunded_amount",
                "razorpay_refund_id",
                "processed_at",
            ]
        )

        # --------------------------------------------------------
        # COMPLETE ATTEMPT
        # --------------------------------------------------------

        attempt.status = RefundAttempt.Status.SUCCESS
        attempt.razorpay_refund_id = (
            razorpay_refund_id
        )
        attempt.gateway_response = (
            _serialize_gateway_response(
                gateway_response
            )
        )
        attempt.completed_at = timezone.now()

        attempt.save(
            update_fields=[
                "status",
                "razorpay_refund_id",
                "gateway_response",
                "completed_at",
            ]
        )

        # --------------------------------------------------------
        # REMOVE ACCESS ONLY FOR SUCCESSFULLY REFUNDED ITEMS
        # --------------------------------------------------------

        refund_items = (
            RefundItem.objects
            .select_related("order_item")
            .filter(
                refund=refund,
            )
        )

        refunded_order_item_ids = []

        for refund_item in refund_items:

            order_item = refund_item.order_item

            refunded_order_item_ids.append(
                order_item.id
            )

            StudentBatchPurchase.objects.filter(
                order_item=order_item,
                order=order,
                student=refund.student,
                status=StudentBatchPurchase.Status.ACTIVE,
            ).update(
                status=StudentBatchPurchase.Status.REFUNDED,
                refunded_at=timezone.now(),
            )

        # --------------------------------------------------------
        # DETERMINE TOTAL SUCCESSFULLY REFUNDED AMOUNT
        # --------------------------------------------------------

        total_refunded = _get_completed_refunded_amount(
            order,
        )

        order_amount = _decimal_amount(
            order.final_amount
        )

        # --------------------------------------------------------
        # UPDATE ORDER STATUS
        # --------------------------------------------------------

        if (
            order_amount > ZERO
            and total_refunded >= order_amount
        ):

            order.status = (
                Order.Status.REFUNDED
            )

        else:

            order.status = (
                Order.Status.PARTIALLY_REFUNDED
            )

        order.save(
            update_fields=[
                "status",
            ]
        )

        # --------------------------------------------------------
        # UPDATE PAYMENT STATUS
        # --------------------------------------------------------

        if payment is not None:

            payment_amount = _decimal_amount(
                payment.amount
            )

            if (
                payment_amount > ZERO
                and total_refunded >= payment_amount
            ):

                payment.status = (
                    Payment.Status.REFUNDED
                )

            else:

                payment.status = (
                    Payment.Status.PARTIALLY_REFUNDED
                )

            payment.save(
                update_fields=[
                    "status",
                ]
            )

        return refund


def execute_refund(refund_id):
    """
    Execute one Refund through Razorpay.

    This is the central refund execution function.

    It is intentionally reusable by:

        - Admin Approve
        - Admin Retry
        - Admin Manual Refund

    Student refund request creation does NOT call this
    function directly. Student requests remain REQUESTED
    until Admin approves them.
    """

    # =========================================================
    # STEP 1
    # Lock refund and prepare a new gateway attempt.
    #
    # IMPORTANT:
    # Do NOT keep this transaction open while calling Razorpay.
    # =========================================================

    with transaction.atomic():

        refund = (
            Refund.objects
            .select_for_update()
            .select_related(
                "order",
                "student",
            )
            .get(pk=refund_id)
        )

        # -----------------------------------------------------
        # ONLY REQUESTED REFUNDS CAN BE EXECUTED
        # -----------------------------------------------------

        if refund.status != Refund.Status.REQUESTED:

            raise ValueError(
                "This refund is not available for processing."
            )

        order = refund.order

        # -----------------------------------------------------
        # PAYMENT MUST EXIST
        # -----------------------------------------------------

        payment = _get_payment_for_refund(order)

        if payment is None:

            raise ValueError(
                "No payment record exists for this order."
            )

        # -----------------------------------------------------
        # RAZORPAY PAYMENT ID MUST EXIST
        # -----------------------------------------------------

        if not payment.razorpay_payment_id:

            raise ValueError(
                "No Razorpay payment ID exists for this order."
            )

        # -----------------------------------------------------
        # REFUND AMOUNT
        # -----------------------------------------------------

        amount = _decimal_amount(
            refund.requested_amount
        )

        if amount <= ZERO:

            raise ValueError(
                "Refund amount must be greater than zero."
            )

        # -----------------------------------------------------
        # PREVENT OVER-REFUND
        # -----------------------------------------------------

        completed_amount = (
            _get_completed_refunded_amount(
                order,
                exclude_refund_id=refund.id,
            )
        )

        order_amount = _decimal_amount(
            order.final_amount
        )

        remaining_amount = (
            order_amount - completed_amount
        )

        if remaining_amount <= ZERO:

            raise ValueError(
                "There is no remaining refundable amount."
            )

        if amount > remaining_amount:

            raise ValueError(
                "The requested refund amount exceeds "
                "the remaining refundable amount."
            )

        # -----------------------------------------------------
        # CREATE ATTEMPT
        # -----------------------------------------------------

        attempt_number = (
            _get_next_refund_attempt_number(
                refund
            )
        )

        attempt = RefundAttempt.objects.create(
            refund=refund,
            attempt_number=attempt_number,
            amount=amount,
            status=RefundAttempt.Status.INITIATED,
            razorpay_payment_id=(
                payment.razorpay_payment_id
            ),
        )

        # -----------------------------------------------------
        # MARK BUSINESS REFUND AS PROCESSING
        # -----------------------------------------------------

        refund.status = Refund.Status.PROCESSING

        refund.save(
            update_fields=[
                "status",
            ]
        )

        refund_id_value = refund.id
        attempt_id_value = attempt.id
        payment_id_value = (
            payment.razorpay_payment_id
        )
        currency = (
            payment.currency
            or order.currency
            or "INR"
        )

    # =========================================================
    # STEP 2
    # Call Razorpay OUTSIDE the database transaction.
    # =========================================================

    try:

        gateway_response = create_razorpay_refund(
            razorpay_payment_id=payment_id_value,
            amount=amount,
            currency=currency,
        )

    except Exception as exc:

        _mark_refund_attempt_failed(
            refund_id=refund_id_value,
            attempt_id=attempt_id_value,
            error_message=str(exc),
        )

        raise

    # =========================================================
    # STEP 3
    # Finalize successful refund.
    # =========================================================

    try:

        return _complete_refund_successfully(
            refund_id=refund_id_value,
            attempt_id=attempt_id_value,
            gateway_response=gateway_response,
        )

    except Exception as exc:

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # At this point Razorpay has already returned success.
        #
        # Therefore we MUST NOT call Razorpay again or mark
        # the money movement as failed.
        #
        # This exception indicates a local finalization problem
        # that must be investigated.
        # -----------------------------------------------------

        raise RuntimeError(
            "Razorpay refund succeeded, but NeoLearn "
            "could not finalize the refund locally."
        ) from exc