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
    # PHONE
    # --------------------------------------------------------

    phone = (phone or "").strip()

    if not phone:

        errors["phone"] = (
            "Phone number is required."
        )

    else:

        normalized_phone = (
            phone
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        if normalized_phone.startswith("+91"):

            digits = normalized_phone[3:]

        else:

            digits = normalized_phone

        if not digits.isdigit():

            errors["phone"] = (
                "Enter a valid phone number."
            )

        elif len(digits) != 10:

            errors["phone"] = (
                "Phone number must contain 10 digits."
            )

        elif digits[0] not in "6789":

            errors["phone"] = (
                "Enter a valid Indian mobile number."
            )

    # --------------------------------------------------------
    # ALTERNATIVE PHONE
    # --------------------------------------------------------

    alternative_phone = (
        alternative_phone or ""
    ).strip()

    if alternative_phone:

        normalized_alt_phone = (
            alternative_phone
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        if normalized_alt_phone.startswith("+91"):

            alt_digits = normalized_alt_phone[3:]

        else:

            alt_digits = normalized_alt_phone

        if not alt_digits.isdigit():

            errors["alternative_phone"] = (
                "Enter a valid alternative phone number."
            )

        elif len(alt_digits) != 10:

            errors["alternative_phone"] = (
                "Alternative phone number must contain 10 digits."
            )

        elif alt_digits[0] not in "6789":

            errors["alternative_phone"] = (
                "Enter a valid Indian mobile number."
            )

        # ----------------------------------------------------
        # SAME NUMBER CHECK
        # ----------------------------------------------------

        if (
            not errors.get("alternative_phone")
            and phone
        ):

            main_normalized = (
                phone
                .replace(" ", "")
                .replace("-", "")
                .replace("(", "")
                .replace(")", "")
            )

            if main_normalized.startswith("+91"):

                main_normalized = (
                    main_normalized[3:]
                )

            if main_normalized == alt_digits:

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
            for batch in checkout[
                "purchased_batches"
            ]
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
            for batch in checkout[
                "unavailable_batches"
            ]
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
    # CREATE LOCAL ORDER
    # --------------------------------------------------------

    order = Order.objects.create(
        user=user,

        status=Order.Status.PENDING,

        full_name=full_name.strip(),

        email=email.strip().lower(),

        phone=phone.strip(),

        alternative_phone=(
            alternative_phone.strip()
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
        #
        # Coupon discount remains ZERO here because the
        # current cart calculation is cart-level.
        #
        # The final coupon amount is stored on Order and the
        # exact per-item allocation can be handled later
        # when we finalize successful-payment processing.
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