from django.urls import path

from .views import (
    checkout_view,
    verify_payment_view,
    invoice_detail_view,
    payment_intro_view,
    payment_success_view,
    payment_failed_view,
    payment_cancelled_view,
)


app_name = "orders"


urlpatterns = [

    # --------------------------------------------------------
    # CHECKOUT
    # --------------------------------------------------------

    path(
        "checkout/",
        checkout_view,
        name="checkout",
    ),

    # --------------------------------------------------------
    # RAZORPAY PAYMENT VERIFICATION
    # --------------------------------------------------------

    path(
        "payment/verify/",
        verify_payment_view,
        name="verify_payment",
    ),

    # --------------------------------------------------------
    # PAYMENT SUCCESS INTRO VIDEO
    # --------------------------------------------------------

    path(
        "payment/intro/<str:order_number>/",
        payment_intro_view,
        name="payment_intro",
    ),

    # --------------------------------------------------------
    # FINAL PAYMENT SUCCESS
    # --------------------------------------------------------

    path(
        "payment/success/<str:order_number>/",
        payment_success_view,
        name="payment_success",
    ),

    # --------------------------------------------------------
    # PAYMENT FAILED
    # --------------------------------------------------------

    path(
        "payment/failed/<str:order_number>/",
        payment_failed_view,
        name="payment_failed",
    ),

    # --------------------------------------------------------
    # PAYMENT CANCELLED
    # --------------------------------------------------------

    path(
        "payment/cancelled/<str:order_number>/",
        payment_cancelled_view,
        name="payment_cancelled",
    ),

    # --------------------------------------------------------
    # INVOICE
    # --------------------------------------------------------

    path(
        "invoice/<str:invoice_number>/",
        invoice_detail_view,
        name="invoice_detail",
    ),
]