from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import razorpay

from django.conf import settings


# ============================================================
# RAZORPAY CLIENT
# ============================================================

def get_razorpay_client():
    """
    Return the configured Razorpay client.
    """

    if not settings.RAZORPAY_KEY_ID:
        raise ValueError(
            "RAZORPAY_KEY_ID is not configured."
        )

    if not settings.RAZORPAY_KEY_SECRET:
        raise ValueError(
            "RAZORPAY_KEY_SECRET is not configured."
        )

    return razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )


# ============================================================
# CREATE RAZORPAY ORDER
# ============================================================

def create_razorpay_order(
    *,
    order_number,
    amount,
    currency="INR",
):
    """
    Create a Razorpay order.

    Razorpay expects the amount in the smallest
    currency unit.

    Example:

        INR 100.00 -> 10000 paise
    """

    client = get_razorpay_client()

    try:
        decimal_amount = Decimal(
            str(amount)
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid payment amount."
        )

    amount_in_paise = int(
        (
            decimal_amount * Decimal("100")
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    if amount_in_paise < 0:
        raise ValueError(
            "Payment amount cannot be negative."
        )

    razorpay_order = client.order.create(
        {
            "amount": amount_in_paise,
            "currency": currency,
            "receipt": order_number,
            "payment_capture": 1,
        }
    )

    return razorpay_order


# ============================================================
# VERIFY PAYMENT SIGNATURE
# ============================================================

def verify_razorpay_payment(
    *,
    razorpay_order_id,
    razorpay_payment_id,
    razorpay_signature,
):
    """
    Verify the Razorpay payment signature.

    Returns True only when Razorpay confirms
    that the signature is valid.
    """

    if not razorpay_order_id:
        raise ValueError(
            "Razorpay order ID is required."
        )

    if not razorpay_payment_id:
        raise ValueError(
            "Razorpay payment ID is required."
        )

    if not razorpay_signature:
        raise ValueError(
            "Razorpay payment signature is required."
        )

    client = get_razorpay_client()

    client.utility.verify_payment_signature(
        {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        }
    )

    return True

# ============================================================
# CREATE RAZORPAY REFUND
# ============================================================

def create_razorpay_refund(
    *,
    razorpay_payment_id,
    amount,
):
    """
    Create a Razorpay refund for a captured payment.

    The amount is supplied in NeoLearn's major currency unit
    and converted to the smallest currency unit expected by
    Razorpay.

    Example:

        INR 100.00 -> 10000 paise
    """

    if not razorpay_payment_id:
        raise ValueError(
            "Razorpay payment ID is required."
        )

    client = get_razorpay_client()

    try:
        decimal_amount = Decimal(
            str(amount)
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid refund amount."
        )

    decimal_amount = decimal_amount.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    if decimal_amount <= Decimal("0.00"):
        raise ValueError(
            "Refund amount must be greater than zero."
        )

    amount_in_paise = int(
        (
            decimal_amount * Decimal("100")
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    if amount_in_paise <= 0:
        raise ValueError(
            "Refund amount must be greater than zero."
        )

    razorpay_refund = client.payment.refund(
        razorpay_payment_id,
        {
            "amount": amount_in_paise,
        },
    )

    return razorpay_refund