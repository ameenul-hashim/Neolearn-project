from django.urls import path

from .views import checkout_view


app_name = "orders"


urlpatterns = [
    path(
        "checkout/",
        checkout_view,
        name="checkout",
    ),
]