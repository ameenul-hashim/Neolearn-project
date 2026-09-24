from django.urls import path

from .views import (
    checkout_view,
    verify_payment_view,
    invoice_detail_view,
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
    # INVOICE
    # --------------------------------------------------------

    path(
        "invoice/<str:invoice_number>/",
        invoice_detail_view,
        name="invoice_detail",
    ),
]