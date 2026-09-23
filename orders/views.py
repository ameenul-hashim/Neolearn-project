from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_control

from .helpers import (
    is_student_user,
    get_checkout_data,
    validate_checkout_data,
    build_order_from_cart,
)

from .razorpay_utils import (
    create_razorpay_order,
)


# ============================================================
# CHECKOUT
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def checkout_view(request):

    # --------------------------------------------------------
    # STUDENT ACCESS
    # --------------------------------------------------------

    if not is_student_user(request.user):

        messages.error(
            request,
            "Student access is required to continue to checkout.",
        )

        return redirect("signin")

    # --------------------------------------------------------
    # GET CURRENT CHECKOUT DATA
    # --------------------------------------------------------

    checkout = get_checkout_data(
        request.user
    )

    cart = checkout["cart"]
    cart_items = checkout["cart_items"]
    totals = checkout["totals"]

    # --------------------------------------------------------
    # EMPTY CART
    # --------------------------------------------------------

    if not cart_items:

        messages.warning(
            request,
            "Your cart is empty. Add a batch before continuing.",
        )

        return redirect("cart")

    # --------------------------------------------------------
    # ALREADY PURCHASED
    # --------------------------------------------------------

    if checkout["purchased_batches"]:

        for batch in checkout["purchased_batches"]:

            messages.warning(
                request,
                f'"{batch.batch_name}" has already been purchased.',
            )

        return redirect("cart")

    # --------------------------------------------------------
    # BATCH NO LONGER AVAILABLE
    # --------------------------------------------------------

    if checkout["unavailable_batches"]:

        for batch in checkout["unavailable_batches"]:

            messages.warning(
                request,
                f'"{batch.batch_name}" is no longer available for purchase.',
            )

        return redirect("cart")

    # --------------------------------------------------------
    # DEFAULT FORM VALUES
    # --------------------------------------------------------

    form_data = {
        "full_name": (
            f"{request.user.first_name} "
            f"{request.user.last_name}"
        ).strip(),

        "email": request.user.email or "",

        "phone": "",

        "alternative_phone": "",
    }

    errors = {}

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    if request.method == "POST":

        form_data = {
            "full_name": request.POST.get(
                "full_name",
                "",
            ).strip(),

            "email": request.POST.get(
                "email",
                "",
            ).strip(),

            "phone": request.POST.get(
                "phone",
                "",
            ).strip(),

            "alternative_phone": request.POST.get(
                "alternative_phone",
                "",
            ).strip(),
        }

        terms_accepted = (
            request.POST.get("terms_accepted")
            == "on"
        )

        # ----------------------------------------------------
        # VALIDATE ALL FIELDS
        # ----------------------------------------------------

        errors = validate_checkout_data(
            user=request.user,

            full_name=form_data["full_name"],
            email=form_data["email"],
            phone=form_data["phone"],
            alternative_phone=form_data[
                "alternative_phone"
            ],

            terms_accepted=terms_accepted,
        )

        # ----------------------------------------------------
        # IF VALID
        # ----------------------------------------------------

        if not errors:

            order = None

            try:

                # --------------------------------------------
                # CREATE LOCAL PENDING ORDER
                # --------------------------------------------

                order = build_order_from_cart(
                    user=request.user,

                    full_name=form_data[
                        "full_name"
                    ],

                    email=form_data[
                        "email"
                    ],

                    phone=form_data[
                        "phone"
                    ],

                    alternative_phone=form_data[
                        "alternative_phone"
                    ],

                    terms_accepted=True,
                )

                # --------------------------------------------
                # CREATE RAZORPAY ORDER
                # --------------------------------------------

                razorpay_order = create_razorpay_order(
                    order_number=order.order_number,
                    amount=order.final_amount,
                    currency=order.currency,
                )

                # --------------------------------------------
                # SAVE RAZORPAY ORDER ID
                # --------------------------------------------

                order.razorpay_order_id = (
                    razorpay_order["id"]
                )

                order.status = (
                    order.Status.PAYMENT_PROCESSING
                )

                order.save(
                    update_fields=[
                        "razorpay_order_id",
                        "status",
                        "updated_at",
                    ]
                )

            except ValueError as exc:

                messages.error(
                    request,
                    str(exc),
                )

                return redirect("cart")

            except Exception:

                # ------------------------------------------------
                # RAZORPAY / ORDER CREATION FAILED
                # ------------------------------------------------

                if order is not None:

                    try:

                        order.status = (
                            order.Status.PAYMENT_FAILED
                        )

                        order.save(
                            update_fields=[
                                "status",
                                "updated_at",
                            ]
                        )

                    except Exception:
                        pass

                messages.error(
                    request,
                    "Unable to start secure payment. "
                    "Please try again.",
                )

                return redirect("checkout")

            # ------------------------------------------------
            # RAZORPAY CHECKOUT DATA
            # ------------------------------------------------

            return render(
                request,
                "orders/checkout.html",
                {
                    "cart": cart,
                    "cart_items": cart_items,
                    "totals": totals,

                    "subtotal": totals[
                        "subtotal"
                    ],

                    "discount_total": totals[
                        "discount_total"
                    ],

                    "total": totals[
                        "total"
                    ],

                    "applied_coupons": totals.get(
                        "applied_coupons",
                        [],
                    ),

                    "form_data": form_data,

                    "errors": {},

                    # ----------------------------------------
                    # RAZORPAY
                    # ----------------------------------------

                    "razorpay_key_id": (
                        settings.RAZORPAY_KEY_ID
                    ),

                    "razorpay_order_id": (
                        order.razorpay_order_id
                    ),

                    "razorpay_amount": int(
                        order.final_amount * 100
                    ),

                    "razorpay_currency": (
                        order.currency
                    ),

                    # ----------------------------------------
                    # NE OLEARN ORDER
                    # ----------------------------------------

                    "order_number": (
                        order.order_number
                    ),

                    "order_id": order.id,
                },
            )

    # --------------------------------------------------------
    # NORMAL GET / VALIDATION ERROR RENDER
    # --------------------------------------------------------

    return render(
        request,
        "orders/checkout.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "totals": totals,

            "subtotal": totals[
                "subtotal"
            ],

            "discount_total": totals[
                "discount_total"
            ],

            "total": totals[
                "total"
            ],

            "applied_coupons": totals.get(
                "applied_coupons",
                [],
            ),

            "form_data": form_data,

            "errors": errors,
        },
    )