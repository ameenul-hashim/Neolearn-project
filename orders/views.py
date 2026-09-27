from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_POST
import json
from decimal import Decimal
import logging

from django.contrib.auth.decorators import login_required
from .helpers import (
    is_student_user,
    get_checkout_data,
    validate_checkout_data,
    build_order_from_cart,

    # Refund helpers
    validate_refund_request,
    get_order_item_refund_amount,
)
from .models import (
    Order,
    OrderItem,
    Payment,
    Invoice,
    StudentBatchPurchase,
    Refund,
    RefundItem,
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
    
# ============================================================
# UPDATE RAZORPAY PAYMENT STATUS
# ============================================================

@login_required(login_url="signin")
@require_POST
def update_payment_status_view(request):
    """
    Update the local NeoLearn order/payment status after a Razorpay
    checkout failure or cancellation.

    Important:
    - The Order row is locked independently.
    - The Payment row is locked independently.
    - We intentionally do NOT use select_related("payment") together
      with select_for_update(), because PostgreSQL rejects locking
      the nullable reverse OneToOne side of that outer join.
    """

    # ============================================================
    # STUDENT CHECK
    # ============================================================

    if not is_student_user(request.user):
        return JsonResponse(
            {
                "success": False,
                "message": "Student access required.",
            },
            status=403,
        )


    # ============================================================
    # PARSE REQUEST
    # ============================================================

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid payment status request.",
            },
            status=400,
        )


    # ============================================================
    # REQUEST DATA
    # ============================================================

    order_number = (
        payload.get("order_number") or ""
    ).strip()

    razorpay_order_id = (
        payload.get("razorpay_order_id") or ""
    ).strip()

    payment_status = (
        payload.get("status") or ""
    ).strip().lower()

    failure_reason = (
        payload.get("failure_reason") or ""
    ).strip()


    # ============================================================
    # VALIDATION
    # ============================================================

    if not order_number:
        return JsonResponse(
            {
                "success": False,
                "message": "Order number is required.",
            },
            status=400,
        )


    if not razorpay_order_id:
        return JsonResponse(
            {
                "success": False,
                "message": "Razorpay order ID is required.",
            },
            status=400,
        )


    if payment_status not in {
        "failed",
        "cancelled",
    }:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid payment status.",
            },
            status=400,
        )


    # ============================================================
    # DATABASE TRANSACTION
    # ============================================================

    try:

        with transaction.atomic():

            # ----------------------------------------------------
            # LOCK ONLY THE ORDER
            #
            # IMPORTANT:
            # Do NOT use:
            #
            # .select_related("payment")
            # .select_for_update()
            #
            # together here.
            #
            # PostgreSQL rejects FOR UPDATE on the nullable side
            # of the reverse OneToOne join.
            # ----------------------------------------------------

            try:

                order = (
                    Order.objects
                    .select_for_update()
                    .get(
                        order_number=order_number,
                        razorpay_order_id=razorpay_order_id,
                        user=request.user,
                    )
                )

            except Order.DoesNotExist:

                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Payment order could not be found."
                        ),
                    },
                    status=404,
                )


            # ----------------------------------------------------
            # NEVER DOWNGRADE A SUCCESSFUL PAYMENT
            # ----------------------------------------------------

            if order.status == Order.Status.PAID:

                return JsonResponse(
                    {
                        "success": True,
                        "already_paid": True,
                        "order_number":
                            order.order_number,
                        "status":
                            order.status,
                        "message":
                            "Payment has already been completed.",
                    }
                )


            # ----------------------------------------------------
            # ONLY PAYMENT_PROCESSING CAN BE FINALIZED
            # ----------------------------------------------------

            if (
                order.status !=
                Order.Status.PAYMENT_PROCESSING
            ):

                return JsonResponse(
                    {
                        "success": True,
                        "already_final": True,
                        "order_number":
                            order.order_number,
                        "status":
                            order.status,
                        "message":
                            "Payment status has already been finalized.",
                    }
                )


            # ----------------------------------------------------
            # LOCK PAYMENT SEPARATELY
            # ----------------------------------------------------

            payment = (
                Payment.objects
                .select_for_update()
                .filter(
                    order=order
                )
                .first()
            )


            # ====================================================
            # PAYMENT FAILED
            # ====================================================

            if payment_status == "failed":

                order.status = (
                    Order.Status.PAYMENT_FAILED
                )

                order.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )


                if payment is not None:

                    payment.status = (
                        Payment.Status.FAILED
                    )

                    payment.failure_reason = (
                        failure_reason
                        or "Razorpay payment failed."
                    )

                    payment.save(
                        update_fields=[
                            "status",
                            "failure_reason",
                            "updated_at",
                        ]
                    )


                return JsonResponse(
                    {
                        "success": True,
                        "status":
                            order.status,
                        "order_number":
                            order.order_number,
                        "message":
                            "Payment failure recorded.",
                    }
                )


            # ====================================================
            # PAYMENT CANCELLED
            # ====================================================

            order.status = (
                Order.Status.CANCELLED
            )

            order.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )


            if payment is not None:

                # Payment model does not have a CANCELLED status.
                #
                # Therefore the payment record is marked FAILED
                # while the Order itself is marked CANCELLED.

                payment.status = (
                    Payment.Status.FAILED
                )

                payment.failure_reason = (
                    failure_reason
                    or
                    "Payment checkout was cancelled "
                    "before completion."
                )

                payment.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "updated_at",
                    ]
                )


            return JsonResponse(
                {
                    "success": True,
                    "status":
                        order.status,
                    "order_number":
                        order.order_number,
                    "message":
                        "Payment cancellation recorded.",
                }
            )


    # ============================================================
    # UNEXPECTED ERROR
    # ============================================================

    except Exception as exc:

        import logging

        logging.getLogger(__name__).exception(
            "NeoLearn payment status update failed "
            "for order %s: %s",
            order_number,
            exc,
        )

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Unable to update payment status.",
            },
            status=500,
        )
        
# ============================================================
# STUDENT REFUND REQUEST
# ============================================================

@login_required(login_url="signin")
@require_POST
def request_refund_view(request):
    """
    Create a student refund request.

    Important rules:
    - Student must own the order.
    - Order must be PAID or PARTIALLY_REFUNDED.
    - Refund must be within the server-side 7-day window.
    - Student never submits the refund amount.
    - Backend calculates the historical refundable amount.
    - Full refund requests refund every currently refundable item.
    - Partial refund requests only the selected OrderItems.
    - Refund is created as REQUESTED.
    - No Razorpay refund is performed here.
    - No access is removed here.
    - No order status is changed here.
    """

    # ========================================================
    # STUDENT ACCESS
    # ========================================================

    if not is_student_user(request.user):
        return JsonResponse(
            {
                "success": False,
                "message": "Student access is required.",
            },
            status=403,
        )

    # ========================================================
    # REQUEST DATA
    # ========================================================

    order_number = (
        request.POST.get("order_number") or ""
    ).strip()

    refund_type = (
        request.POST.get("refund_type") or ""
    ).strip().lower()

    reason = (
        request.POST.get("reason") or ""
    ).strip()

    order_item_ids = request.POST.getlist(
        "order_item_ids"
    )

    # ========================================================
    # BASIC VALIDATION
    # ========================================================

    if not order_number:
        return JsonResponse(
            {
                "success": False,
                "message": "Order number is required.",
            },
            status=400,
        )

    if refund_type not in {
        "full",
        "partial",
    }:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid refund type.",
            },
            status=400,
        )

    if not reason:
        return JsonResponse(
            {
                "success": False,
                "message": "Please provide a refund reason.",
            },
            status=400,
        )

    # ========================================================
    # FIND STUDENT'S ORDER
    # ========================================================

    try:
        with transaction.atomic():

            # ------------------------------------------------
            # LOCK THE ORDER
            # ------------------------------------------------
            #
            # This prevents two refund requests from being
            # created simultaneously for the same order.
            # ------------------------------------------------

            try:
                order = (
                    Order.objects
                    .select_for_update()
                    .get(
                        order_number=order_number,
                        user=request.user,
                    )
                )

            except Order.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Order could not be found.",
                    },
                    status=404,
                )

            # ------------------------------------------------
            # VALIDATE REFUND
            # ------------------------------------------------
            #
            # IMPORTANT:
            # The helper calculates the amount from historical
            # OrderItem.final_price / Order.final_amount.
            #
            # We do NOT trust an amount sent by the browser.
            # ------------------------------------------------

            try:

                if refund_type == "full":

                    refund_data = validate_refund_request(
                        order,
                        full_order=True,
                    )

                else:

                    refund_data = validate_refund_request(
                        order,
                        order_item_ids=order_item_ids,
                        full_order=False,
                    )

            except ValueError as exc:

                return JsonResponse(
                    {
                        "success": False,
                        "message": str(exc),
                    },
                    status=400,
                )

            # ------------------------------------------------
            # EXTRACT VALIDATED DATA
            # ------------------------------------------------

            refund_amount = refund_data["amount"]
            refundable_items = refund_data["items"]
            validated_refund_type = refund_data["refund_type"]

            # ------------------------------------------------
            # FINAL SAFETY CHECK
            # ------------------------------------------------

            if not refundable_items:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "There are no refundable batches "
                            "available in this order."
                        ),
                    },
                    status=400,
                )

            if refund_amount <= Decimal("0.00"):
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "The calculated refund amount "
                            "must be greater than zero."
                        ),
                    },
                    status=400,
                )

            # ------------------------------------------------
            # CREATE REFUND REQUEST
            # ------------------------------------------------

            refund = Refund.objects.create(
                order=order,
                student=request.user,
                reason=reason,
                status=Refund.Status.REQUESTED,
                requested_amount=refund_amount,
                refunded_amount=Decimal("0.00"),
            )

            # ------------------------------------------------
            # CREATE REFUND ITEMS
            # ------------------------------------------------
            #
            # Store the exact historical refund amount for
            # every selected batch.
            #
            # This gives us a permanent snapshot even if
            # current batch/coupon prices change later.
            # ------------------------------------------------

            for order_item in refundable_items:

                item_refund_amount = (
                    get_order_item_refund_amount(
                        order_item
                    )
                )

                if item_refund_amount <= Decimal("0.00"):
                    continue

                RefundItem.objects.create(
                    refund=refund,
                    order_item=order_item,
                    refund_amount=item_refund_amount,
                )

            # ------------------------------------------------
            # SAFETY CHECK AFTER REFUND ITEM CREATION
            # ------------------------------------------------

            refund_item_count = RefundItem.objects.filter(
                refund=refund
            ).count()

            if refund_item_count == 0:
                refund.delete()

                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "No refundable batches were "
                            "available for this request."
                        ),
                    },
                    status=400,
                )

            # ------------------------------------------------
            # RESPONSE
            # ------------------------------------------------

            return JsonResponse(
                {
                    "success": True,
                    "refund_id": refund.id,
                    "order_number": order.order_number,
                    "refund_type": validated_refund_type,
                    "requested_amount": str(
                        refund.requested_amount
                    ),
                    "status": refund.status,
                    "message": (
                        "Your refund request has been "
                        "submitted successfully."
                    ),
                }
            )

    # ========================================================
    # UNEXPECTED ERROR
    # ========================================================

    except Exception as exc:

        logging.getLogger(__name__).exception(
            "NeoLearn refund request failed "
            "for order %s: %s",
            order_number,
            exc,
        )

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "Unable to submit the refund request. "
                    "Please try again."
                ),
            },
            status=500,
        )
        
# ============================================================
# EDIT STUDENT REFUND REQUEST
# ============================================================

@login_required(login_url="signin")
@require_POST
def edit_refund_request_view(request, refund_id):
    """
    Edit an existing student refund request.

    Important rules:

    - Student must own the refund request.
    - Refund must still be in REQUESTED status.
    - PROCESSING refunds cannot be edited.
    - COMPLETED refunds cannot be edited.
    - REJECTED refunds cannot be edited.
    - FAILED refunds cannot be edited.
    - The order is locked during the update.
    - The existing refund is excluded from reservation checks.
    - The refund amount is recalculated server-side.
    - Browser-submitted amounts are never trusted.
    - Existing RefundItems are replaced only after validation succeeds.
    - No Razorpay refund is performed here.
    - No order status is changed here.
    """

    # ========================================================
    # STUDENT ACCESS
    # ========================================================

    if not is_student_user(request.user):
        return JsonResponse(
            {
                "success": False,
                "message": "Student access is required.",
            },
            status=403,
        )

    # ========================================================
    # REQUEST DATA
    # ========================================================

    order_number = (
        request.POST.get("order_number") or ""
    ).strip()

    refund_type = (
        request.POST.get("refund_type") or ""
    ).strip().lower()

    reason = (
        request.POST.get("reason") or ""
    ).strip()

    order_item_ids = request.POST.getlist(
        "order_item_ids"
    )

    # ========================================================
    # BASIC VALIDATION
    # ========================================================

    if not order_number:
        return JsonResponse(
            {
                "success": False,
                "message": "Order number is required.",
            },
            status=400,
        )

    if refund_type not in {
        "full",
        "partial",
    }:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid refund type.",
            },
            status=400,
        )

    if not reason:
        return JsonResponse(
            {
                "success": False,
                "message": "Please provide a refund reason.",
            },
            status=400,
        )

    # ========================================================
    # DATABASE TRANSACTION
    # ========================================================

    try:
        with transaction.atomic():

            # ------------------------------------------------
            # LOCK THE REFUND
            # ------------------------------------------------

            try:
                refund = (
                    Refund.objects
                    .select_for_update()
                    .select_related(
                        "order",
                    )
                    .get(
                        pk=refund_id,
                        student=request.user,
                    )
                )

            except Refund.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Refund request could not be found."
                        ),
                    },
                    status=404,
                )

            # ------------------------------------------------
            # REFUND MUST STILL BE REQUESTED
            # ------------------------------------------------

            if refund.status != Refund.Status.REQUESTED:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "This refund request can no longer "
                            "be edited."
                        ),
                    },
                    status=400,
                )

            # ------------------------------------------------
            # LOCK THE ORDER
            # ------------------------------------------------

            try:
                order = (
                    Order.objects
                    .select_for_update()
                    .get(
                        pk=refund.order_id,
                        user=request.user,
                    )
                )

            except Order.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "The order associated with this "
                            "refund could not be found."
                        ),
                    },
                    status=404,
                )

            # ------------------------------------------------
            # VALIDATE UPDATED REFUND
            #
            # IMPORTANT:
            #
            # exclude_refund_id allows this refund's existing
            # RefundItems to become refundable again while
            # recalculating the edited request.
            # ------------------------------------------------

            try:

                if refund_type == "full":

                    refund_data = validate_refund_request(
                        order,
                        full_order=True,
                        exclude_refund_id=refund.id,
                    )

                else:

                    refund_data = validate_refund_request(
                        order,
                        order_item_ids=order_item_ids,
                        full_order=False,
                        exclude_refund_id=refund.id,
                    )

            except ValueError as exc:
                return JsonResponse(
                    {
                        "success": False,
                        "message": str(exc),
                    },
                    status=400,
                )

            # ------------------------------------------------
            # EXTRACT VALIDATED DATA
            # ------------------------------------------------

            refund_amount = refund_data["amount"]

            refundable_items = refund_data["items"]

            validated_refund_type = (
                refund_data["refund_type"]
            )

            # ------------------------------------------------
            # FINAL SAFETY CHECK
            # ------------------------------------------------

            if not refundable_items:
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "There are no refundable batches "
                            "available for this request."
                        ),
                    },
                    status=400,
                )

            if refund_amount <= Decimal("0.00"):
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "The calculated refund amount "
                            "must be greater than zero."
                        ),
                    },
                    status=400,
                )

            # =================================================
            # UPDATE REFUND HEADER
            # =================================================

            refund.reason = reason

            refund.requested_amount = (
                refund_amount
            )

            # Keep the refund in REQUESTED status.
            refund.status = Refund.Status.REQUESTED

            refund.save(
            update_fields=[
            "reason",
            "requested_amount",
            "status",
            ])

            # =================================================
            # REPLACE REFUND ITEMS
            # =================================================
            #
            # At this point validation has already succeeded.
            #
            # Therefore it is safe to remove the old snapshot
            # and recreate it using the newly selected items.
            #
            # The amount for every item comes from the historical
            # OrderItem.final_price.
            # =================================================

            refund.items.all().delete()

            created_refund_item_count = 0

            for order_item in refundable_items:

                item_refund_amount = (
                    get_order_item_refund_amount(
                        order_item
                    )
                )

                if item_refund_amount <= Decimal("0.00"):
                    continue

                RefundItem.objects.create(
                    refund=refund,
                    order_item=order_item,
                    refund_amount=item_refund_amount,
                )

                created_refund_item_count += 1

            # ------------------------------------------------
            # SAFETY CHECK
            # ------------------------------------------------

            if created_refund_item_count == 0:
                raise ValueError(
                    "No refundable batches were available "
                    "for this request."
                )

            # =================================================
            # RESPONSE
            # =================================================

            return JsonResponse(
                {
                    "success": True,
                    "refund_id": refund.id,
                    "order_number": order.order_number,
                    "refund_type": validated_refund_type,
                    "requested_amount": str(
                        refund.requested_amount
                    ),
                    "status": refund.status,
                    "message": (
                        "Your refund request has been "
                        "updated successfully."
                    ),
                }
            )

    # ========================================================
    # UNEXPECTED ERROR
    # ========================================================

    except ValueError as exc:

        logging.getLogger(__name__).warning(
            "NeoLearn refund edit validation failed "
            "for refund %s: %s",
            refund_id,
            exc,
        )

        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )

    except Exception as exc:

        logging.getLogger(__name__).exception(
            "NeoLearn refund edit failed "
            "for refund %s: %s",
            refund_id,
            exc,
        )

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "Unable to update the refund request. "
                    "Please try again."
                ),
            },
            status=500,
        )