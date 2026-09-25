from django.conf import settings

from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.db import transaction

from django.http import JsonResponse

from django.shortcuts import redirect, render

from django.utils import timezone

from django.views.decorators.cache import cache_control

from django.views.decorators.http import require_POST


from .helpers import (

    is_student_user,

    get_checkout_data,

    validate_checkout_data,

    build_order_from_cart,

)


from .models import (

    Order,

    OrderItem,

    Payment,

    Invoice,

    StudentBatchPurchase,

)


from students.models import Cart


from .razorpay_utils import (

    create_razorpay_order,

    verify_razorpay_payment,

)


# ============================================================

# NEOLEARN PAYMENT DIAGNOSTIC LOGGING

# ============================================================


def _clean(value):

    """Safely strip a value that may be None."""

    return (value or "").strip()


def checkout_view(request):





    # --------------------------------------------------------



    # STUDENT ACCESS



    # --------------------------------------------------------





    student_access = is_student_user(request.user)





    if not student_access:





        messages.error(



            request,



            "Student access is required to continue to checkout.",



        )





        return redirect("signin")





    # --------------------------------------------------------



    # GET CURRENT CHECKOUT DATA



    # --------------------------------------------------------





    try:



        checkout = get_checkout_data(request.user)



    except Exception as exc:





        raise





    cart = checkout["cart"]



    cart_items = checkout["cart_items"]



    totals = checkout["totals"]





    for index, item in enumerate(cart_items, start=1):



        batch = getattr(item, "batch", None)





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





        # PHONE IS REQUIRED



        "phone": "",





        "alternative_phone": "",





        "terms_accepted": False,



    }





    errors = {}





    # --------------------------------------------------------



    # POST



    # --------------------------------------------------------





    if request.method == "POST":





        # ----------------------------------------------------



        # GET FORM VALUES



        # ----------------------------------------------------





        form_data = {



            "full_name": _clean(



                request.POST.get("full_name")



            ),





            "email": _clean(



                request.POST.get("email")



            ),





            "phone": _clean(



                request.POST.get("phone")



            ),





            "alternative_phone": _clean(



                request.POST.get("alternative_phone")



            ),





            "terms_accepted": (



                request.POST.get("terms_accepted") == "1"



            ),



        }





        # ----------------------------------------------------



        # TERMS



        # ----------------------------------------------------





        terms_accepted = form_data["terms_accepted"]





        # ----------------------------------------------------



        # VALIDATE ALL FIELDS



        # ----------------------------------------------------





        try:



            errors = validate_checkout_data(



                user=request.user,





                full_name=form_data["full_name"],





                email=form_data["email"],





                phone=form_data["phone"],





                alternative_phone=form_data["alternative_phone"],





                terms_accepted=terms_accepted,



            )



        except Exception as exc:





            raise





        # ----------------------------------------------------



        # IF VALID



        # ----------------------------------------------------





        if not errors:





            order = None





            try:





                # --------------------------------------------



                # CREATE LOCAL ORDER



                # --------------------------------------------





                order = build_order_from_cart(



                    user=request.user,





                    full_name=form_data["full_name"],





                    email=form_data["email"],





                    phone=form_data["phone"],





                    alternative_phone=form_data["alternative_phone"],





                    terms_accepted=terms_accepted,



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





                order.razorpay_order_id = razorpay_order["id"]





                order.status = Order.Status.PAYMENT_PROCESSING





                order.save(



                    update_fields=[



                        "razorpay_order_id",



                        "status",



                        "updated_at",



                    ]



                )





                # --------------------------------------------



                # CREATE PAYMENT RECORD



                # --------------------------------------------





                payment, payment_created = Payment.objects.update_or_create(



                    order=order,





                    defaults={



                        "razorpay_order_id": razorpay_order["id"],





                        "amount": order.final_amount,





                        "currency": order.currency,





                        "status": Payment.Status.CREATED,





                        "failure_reason": "",



                    },



                )





            except ValueError as exc:





                messages.error(



                    request,



                    str(exc),



                )





                return redirect("cart")





            except Exception as exc:





                import traceback

                print("\n" + "=" * 80)
                print("NEOLEARN CHECKOUT PAYMENT ERROR")
                print("=" * 80)
                print("ERROR TYPE:", type(exc).__name__)
                print("ERROR:", exc)
                print("-" * 80)
                traceback.print_exc()
                print("=" * 80 + "\n")

                # --------------------------------------------

                # RAZORPAY / ORDER CREATION FAILED



                # --------------------------------------------





                if order is not None:





                    try:





                        order.status = Order.Status.PAYMENT_FAILED





                        order.save(



                            update_fields=[



                                "status",



                                "updated_at",



                            ]



                        )





                        Payment.objects.filter(



                            order=order



                        ).update(



                            status=Payment.Status.FAILED,



                            failure_reason=(



                                "Unable to create "



                                "Razorpay payment order."



                            ),



                        )





                    except Exception:



                        pass





                messages.error(



                    request,



                    "Unable to start secure payment. "



                    "Please try again.",



                )





                return redirect("orders:checkout")





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





                    "subtotal": totals["subtotal"],





                    "discount_total": totals["discount_total"],





                    "total": totals["total"],





                    "applied_coupons": totals.get(



                        "applied_coupons",



                        [],



                    ),





                    "form_data": form_data,





                    "errors": {},





                    # ----------------------------------------



                    # RAZORPAY



                    # ----------------------------------------





                    "razorpay_key_id": settings.RAZORPAY_KEY_ID,





                    "razorpay_order_id": order.razorpay_order_id,





                    "razorpay_amount": int(order.final_amount * 100),





                    "razorpay_currency": order.currency,





                    # ----------------------------------------



                    # NEOLEARN ORDER



                    # ----------------------------------------





                    "order_number": order.order_number,





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





            "subtotal": totals["subtotal"] if totals else 0,





            "discount_total": totals["discount_total"] if totals else 0,





            "total": totals["total"] if totals else 0,





            "applied_coupons": (



                totals.get("applied_coupons", [])



                if totals



                else []



            ),





            "form_data": form_data,





            "errors": errors,



        },



    )


# ============================================================

# INVOICE DETAIL

# ============================================================


@login_required(login_url="signin")

@cache_control(

    no_cache=True,

    must_revalidate=True,

    no_store=True,

)

def invoice_detail_view(request, invoice_number):


    # --------------------------------------------------------

    # STUDENT ACCESS

    # --------------------------------------------------------


    if not is_student_user(request.user):

        messages.error(

            request,

            "Student access is required to view this invoice.",

        )

        return redirect("signin")


    # --------------------------------------------------------

    # FIND ONLY THIS STUDENT'S INVOICE

    # --------------------------------------------------------


    try:

        invoice = (

            Invoice.objects

            .select_related(

                "order",

                "order__user",

                "order__payment",

            )

            .prefetch_related(

                "order__items",

            )

            .get(

                invoice_number=invoice_number,

                order__user=request.user,

                order__status=Order.Status.PAID,

            )

        )


    except Invoice.DoesNotExist:

        messages.error(

            request,

            "Invoice not found or it is not available.",

        )

        return redirect("orders:checkout")


    # --------------------------------------------------------

    # RENDER INVOICE

    # --------------------------------------------------------


    return render(

        request,

        "orders/invoice_detail.html",

        {

            "invoice": invoice,

        },

    )


# ============================================================



# ============================================================
# PAYMENT RESULT PAGES
# ============================================================


@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def payment_success_view(request, order_number):
    """
    Display the final successful payment page.

    This page is only available when the supplied order belongs to
    the logged-in student and has already been marked PAID by the
    server-side Razorpay verification flow.
    """

    if not is_student_user(request.user):
        messages.error(
            request,
            "Student access is required to view the payment result.",
        )
        return redirect("signin")

    try:
        order = (
            Order.objects
            .select_related(
                "user",
                "payment",
                "invoice",
            )
            .prefetch_related(
                "items__batch",
            )
            .get(
                order_number=order_number,
                user=request.user,
                status=Order.Status.PAID,
            )
        )
    except Order.DoesNotExist:
        messages.error(
            request,
            "Successful payment order could not be found.",
        )
        return redirect("orders:checkout")

    invoice = getattr(order, "invoice", None)

    return render(
        request,
        "orders/payment_success.html",
        {
            "order": order,
            "order_items": order.items.all(),
            "invoice": invoice,
            "order_number": order.order_number,
        },
    )


@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def payment_failed_view(request, order_number):
    """
    Display the payment-failed page.

    The cart is intentionally not changed here. The student can
    return to checkout and try the payment again.
    """

    if not is_student_user(request.user):
        messages.error(
            request,
            "Student access is required to view the payment result.",
        )
        return redirect("signin")

    try:
        order = (
            Order.objects
            .select_related(
                "user",
                "payment",
            )
            .prefetch_related(
                "items__batch",
            )
            .get(
                order_number=order_number,
                user=request.user,
            )
        )
    except Order.DoesNotExist:
        messages.error(
            request,
            "Payment order could not be found.",
        )
        return redirect("orders:checkout")

    return render(
        request,
        "orders/payment_failed.html",
        {
            "order": order,
            "order_items": order.items.all(),
            "order_number": order.order_number,
        },
    )


@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def payment_cancelled_view(request, order_number):
    """
    Display the payment-cancelled page.

    Closing/cancelling Razorpay does not remove cart items or
    coupons. The student can return to checkout and retry.
    """

    if not is_student_user(request.user):
        messages.error(
            request,
            "Student access is required to view the payment result.",
        )
        return redirect("signin")

    try:
        order = (
            Order.objects
            .select_related(
                "user",
                "payment",
            )
            .prefetch_related(
                "items__batch",
            )
            .get(
                order_number=order_number,
                user=request.user,
            )
        )
    except Order.DoesNotExist:
        messages.error(
            request,
            "Payment order could not be found.",
        )
        return redirect("orders:checkout")

    return render(
        request,
        "orders/payment_cancelled.html",
        {
            "order": order,
            "order_items": order.items.all(),
            "order_number": order.order_number,
        },
    )


# RAZORPAY PAYMENT VERIFICATION

# ============================================================


@login_required(login_url="signin")

@require_POST

def verify_payment_view(request):


    # --------------------------------------------------------

    # STUDENT ACCESS

    # --------------------------------------------------------


    if not is_student_user(request.user):

        return JsonResponse(

            {

                "success": False,

                "message": "Student access is required.",

            },

            status=403,

        )


    # --------------------------------------------------------

    # READ JSON REQUEST

    # --------------------------------------------------------


    try:

        import json


        payload = json.loads(

            request.body.decode("utf-8")

        )


    except (json.JSONDecodeError, UnicodeDecodeError) as exc:


        return JsonResponse(

            {

                "success": False,

                "message": "Invalid payment verification request.",

            },

            status=400,

        )


    # --------------------------------------------------------

    # GET RAZORPAY RESPONSE

    # --------------------------------------------------------


    order_number = str(

        payload.get("order_number", "")

    ).strip()


    razorpay_order_id = str(

        payload.get("razorpay_order_id", "")

    ).strip()


    razorpay_payment_id = str(

        payload.get("razorpay_payment_id", "")

    ).strip()


    razorpay_signature = str(

        payload.get("razorpay_signature", "")

    ).strip()


    # --------------------------------------------------------

    # REQUIRED VALUES

    # --------------------------------------------------------


    if not order_number:

        return JsonResponse(

            {

                "success": False,

                "message": "Order number is missing.",

            },

            status=400,

        )


    if not razorpay_order_id:

        return JsonResponse(

            {

                "success": False,

                "message": "Razorpay order ID is missing.",

            },

            status=400,

        )


    if not razorpay_payment_id:

        return JsonResponse(

            {

                "success": False,

                "message": "Razorpay payment ID is missing.",

            },

            status=400,

        )


    if not razorpay_signature:

        return JsonResponse(

            {

                "success": False,

                "message": "Razorpay payment signature is missing.",

            },

            status=400,

        )


    # --------------------------------------------------------

    # FIND ORDER

    # --------------------------------------------------------


    try:

        order = Order.objects.get(

            order_number=order_number,

            razorpay_order_id=razorpay_order_id,

            user=request.user,

        )


    except Order.DoesNotExist as exc:


        return JsonResponse(

            {

                "success": False,

                "message": "Order could not be found.",

            },

            status=404,

        )


    # --------------------------------------------------------

    # ALREADY PAID

    # --------------------------------------------------------


    if order.status == Order.Status.PAID:


        invoice = getattr(

            order,

            "invoice",

            None,

        )


        # A repeated verification request is safe. The payment is already

        # complete, so remove only the batches that belong to this order

        # from the student's cart. This also keeps unrelated cart items.

        try:

            purchased_batch_ids = list(

                order.items.values_list(

                    "batch_id",

                    flat=True,

                )

            )


            cart = Cart.objects.filter(

                student=request.user,

            ).first()


            if cart and purchased_batch_ids:

                cart.items.filter(

                    batch_id__in=purchased_batch_ids,

                ).delete()


                # Coupons belong to the checkout/cart state. Once the

                # purchased items are gone, clear the remaining checkout

                # coupons only when the cart itself is empty.

                if not cart.items.exists():

                    cart.cart_coupons.all().delete()

        except Exception:

            # Do not turn an already-completed payment into a failure just

            # because cart cleanup encountered a non-payment problem.

            pass


        return JsonResponse(

            {

                "success": True,

                "already_paid": True,

                "order_number": order.order_number,

                "invoice_number": (

                    invoice.invoice_number

                    if invoice

                    else ""

                ),

                "message": (

                    "Payment has already been verified."

                ),

            }

        )


    # --------------------------------------------------------

    # VERIFY RAZORPAY SIGNATURE

    # --------------------------------------------------------


    try:


        verify_razorpay_payment(

            razorpay_order_id=razorpay_order_id,

            razorpay_payment_id=razorpay_payment_id,

            razorpay_signature=razorpay_signature,

        )


    except Exception as exc:


        order.status = Order.Status.PAYMENT_FAILED


        order.save(

            update_fields=[

                "status",

                "updated_at",

            ]

        )


        Payment.objects.filter(

            order=order

        ).update(

            status=Payment.Status.FAILED,

            razorpay_payment_id=razorpay_payment_id,

            razorpay_signature=razorpay_signature,

            failure_reason=(

                "Razorpay payment signature "

                "verification failed."

            ),

        )


        return JsonResponse(

            {

                "success": False,

                "message": (

                    "Payment verification failed."

                ),

            },

            status=400,

        )


    # --------------------------------------------------------

    # FINALIZE SUCCESSFUL PAYMENT

    # --------------------------------------------------------


    try:


        with transaction.atomic():


            # --------------------------------------------

            # LOCK ORDER

            # --------------------------------------------


            order = (

                Order.objects

                .select_for_update()

                .get(

                    pk=order.pk,

                    user=request.user,

                )

            )


            # --------------------------------------------

            # CREATE / UPDATE PAYMENT

            # --------------------------------------------


            payment, created = (

                Payment.objects

                .select_for_update()

                .get_or_create(

                    order=order,

                    defaults={

                        "razorpay_order_id": razorpay_order_id,

                        "razorpay_payment_id": razorpay_payment_id,

                        "razorpay_signature": razorpay_signature,

                        "amount": order.final_amount,

                        "currency": order.currency,

                        "status": Payment.Status.CAPTURED,

                        "captured_at": timezone.now(),

                    },

                )

            )


            if not created:


                payment.razorpay_order_id = razorpay_order_id


                payment.razorpay_payment_id = razorpay_payment_id


                payment.razorpay_signature = razorpay_signature


                payment.amount = order.final_amount


                payment.currency = order.currency


                payment.status = Payment.Status.CAPTURED


                payment.failure_reason = ""


                payment.captured_at = timezone.now()


                payment.save()


            # --------------------------------------------

            # MARK ORDER PAID

            # --------------------------------------------


            order.status = Order.Status.PAID


            order.paid_at = timezone.now()


            order.save(

                update_fields=[

                    "status",

                    "paid_at",

                    "updated_at",

                ]

            )


            # --------------------------------------------

            # CREATE INVOICE

            # --------------------------------------------


            invoice, invoice_created = Invoice.objects.get_or_create(

                order=order,

                defaults={

                    "subtotal": order.subtotal,

                    "coupon_discount": order.total_coupon_discount,

                    "total_discount": order.total_discount,

                    "final_amount": order.final_amount,

                    "currency": order.currency,

                },

            )


            # --------------------------------------------

            # CREATE STUDENT BATCH ACCESS

            # --------------------------------------------


            for order_item in (

                order.items

                .select_related("batch")

                .all()

            ):


                purchase, created = (

                    StudentBatchPurchase.objects.get_or_create(

                        student=request.user,

                        batch=order_item.batch,

                        defaults={

                            "order": order,

                            "order_item": order_item,

                            "status": (

                                StudentBatchPurchase

                                .Status.ACTIVE

                            ),

                        },

                    )

                )


                if not created:

                    purchase.order = order

                    purchase.order_item = order_item

                    purchase.status = (

                        StudentBatchPurchase.Status.ACTIVE

                    )

                    purchase.save(

                        update_fields=[

                            "order",

                            "order_item",

                            "status",

                        ]

                    )


            # --------------------------------------------

            # REMOVE PURCHASED ITEMS FROM CART

            # --------------------------------------------

            # Only remove batches that were actually included in this paid

            # order. This prevents an unrelated cart item from being lost

            # if the cart changes between checkout creation and payment

            # verification.

            purchased_batch_ids = list(

                order.items.values_list(

                    "batch_id",

                    flat=True,

                )

            )


            if purchased_batch_ids:

                cart = Cart.objects.filter(

                    student=request.user,

                ).first()


                if cart:

                    cart.items.filter(

                        batch_id__in=purchased_batch_ids,

                    ).delete()


                    # If the successful purchase emptied the cart, its

                    # checkout coupon state is no longer needed.

                    if not cart.items.exists():

                        cart.cart_coupons.all().delete()


    except Exception as exc:


        import logging


        logging.getLogger(__name__).exception(

            "NeoLearn payment finalization failed for order %s: %s",

            order.order_number,

            exc,

        )


        return JsonResponse(

            {

                "success": False,

                "message": (

                    "Payment was verified, but "

                    "order finalization failed."

                ),

            },

            status=500,

        )


    # --------------------------------------------------------

    # SUCCESS

    # --------------------------------------------------------


    invoice = getattr(

        order,

        "invoice",

        None,

    )


    return JsonResponse(

        {

            "success": True,

            "order_number": order.order_number,

            "invoice_number": (

                invoice.invoice_number

                if invoice

                else ""

            ),

            "message": (

                "Payment completed successfully."

            ),

        }

    )
@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def payment_intro_view(request, order_number):
    """
    Display the payment-success intro video before the final
    payment success page.

    This view does not process or verify payment.
    It only allows the intro page to be shown for a paid order
    belonging to the logged-in student.
    """

    # --------------------------------------------------------
    # STUDENT ACCESS
    # --------------------------------------------------------

    if not is_student_user(request.user):
        messages.error(
            request,
            "Student access is required to view the payment result.",
        )
        return redirect("signin")

    # --------------------------------------------------------
    # FIND PAID ORDER
    # --------------------------------------------------------

    try:
        order = (
            Order.objects
            .select_related(
                "user",
                "payment",
                "invoice",
            )
            .prefetch_related(
                "items__batch",
            )
            .get(
                order_number=order_number,
                user=request.user,
                status=Order.Status.PAID,
            )
        )

    except Order.DoesNotExist:
        messages.error(
            request,
            "Successful payment order could not be found.",
        )
        return redirect("orders:checkout")

    # --------------------------------------------------------
    # RENDER PAYMENT INTRO VIDEO PAGE
    # --------------------------------------------------------

    return render(
        request,
        "orders/payment_intro.html",
        {
            "order": order,
            "order_number": order.order_number,
        },
    )