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