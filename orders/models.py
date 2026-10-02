from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAYMENT_PROCESSING = "payment_processing", "Payment Processing"
        PAID = "paid", "Paid"
        PAYMENT_FAILED = "payment_failed", "Payment Failed"
        CANCELLED = "cancelled", "Cancelled"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    order_number = models.CharField(
        max_length=40,
        unique=True,
        editable=False,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Checkout snapshot
    full_name = models.CharField(max_length=200)

    phone = models.CharField(
    max_length=10,
    )

    alternative_phone = models.CharField(
    max_length=10,
    blank=True,
    default="",
    )

    # Financial snapshot
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_coupon_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    final_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    currency = models.CharField(
        max_length=10,
        default="INR",
    )

    # Razorpay
    razorpay_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
    )

    terms_accepted = models.BooleanField(default=False)

    paid_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders_order"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()

        super().save(*args, **kwargs)

    @staticmethod
    def generate_order_number():
        year = timezone.now().year

        while True:
            number = f"NLORD-{year}-{uuid.uuid4().hex[:8].upper()}"

            if not Order.objects.filter(
                order_number=number
            ).exists():
                return number

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    @property
    def item_count(self):
        return self.items.count()


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    batch = models.ForeignKey(
        "admins.Batch",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    # Historical snapshot
    batch_name = models.CharField(max_length=200)

    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    batch_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    coupon_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders_order_item"
        ordering = ["id"]

    def __str__(self):
        return f"{self.order.order_number} - {self.batch_name}"

    @property
    def total_discount(self):
        return (
            self.batch_discount +
            self.coupon_discount
        )

class OrderCoupon(models.Model):
    """
    Historical snapshot of a coupon applied to an order.

    IMPORTANT:
    This model stores the coupon information exactly as it was
    when the order was created.

    It must not depend on the current Coupon configuration for
    historical order/refund decisions.
    """

    # ---------------------------------------------------------
    # Order
    # ---------------------------------------------------------

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="coupons",
    )

    # ---------------------------------------------------------
    # Historical Coupon Identity
    # ---------------------------------------------------------

    coupon_code = models.CharField(
        max_length=50,
    )

    coupon_description = models.TextField(
        blank=True,
        default="",
    )

    coupon_type = models.CharField(
        max_length=20,
    )

    # ---------------------------------------------------------
    # Historical Discount Configuration
    # ---------------------------------------------------------

    discount_type = models.CharField(
        max_length=20,
    )

    discount_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # ---------------------------------------------------------
    # ACTUAL DISCOUNT GIVEN TO THIS ORDER
    # ---------------------------------------------------------

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # ---------------------------------------------------------
    # Historical Checkout Restrictions
    # ---------------------------------------------------------

    minimum_order_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    maximum_order_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    maximum_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    # ---------------------------------------------------------
    # Historical Usage Rules
    # ---------------------------------------------------------

    usage_limit = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    per_user_limit = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    # ---------------------------------------------------------
    # Historical Validity
    # ---------------------------------------------------------

    valid_from = models.DateTimeField(
        blank=True,
        null=True,
    )

    valid_until = models.DateTimeField(
        blank=True,
        null=True,
    )

    # ---------------------------------------------------------
    # Batch Context
    #
    # Batch-specific coupons can be connected to a particular
    # batch. General and multi-checkout coupons may not need one.
    #
    # We save the batch name as a historical snapshot so the
    # order details remain understandable even if the current
    # coupon/batch configuration changes later.
    # ---------------------------------------------------------

    applied_batch = models.ForeignKey(
        "admins.Batch",
        on_delete=models.SET_NULL,
        related_name="order_coupon_snapshots",
        blank=True,
        null=True,
    )

    applied_batch_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    # ---------------------------------------------------------
    # Snapshot Timestamp
    # ---------------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    # ---------------------------------------------------------
    # Meta
    # ---------------------------------------------------------

    class Meta:
        db_table = "orders_order_coupon"
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["order"],
                name="order_coupon_order_idx",
            ),
            models.Index(
                fields=["coupon_code"],
                name="order_coupon_code_idx",
            ),
            models.Index(
                fields=["coupon_type"],
                name="order_coupon_type_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.order.order_number} - "
            f"{self.coupon_code}"
        )

class Payment(models.Model):
    class Source(models.TextChoices):
        RAZORPAY = "razorpay", "Razorpay"
        SCENARIO = "scenario", "Test Scenario"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PROCESSING = "processing", "Processing"
        CAPTURED = "captured", "Captured"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="payment",
    )

    payment_source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.RAZORPAY,
        db_index=True,
    )

    razorpay_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )

    razorpay_signature = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=10,
        default="INR",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.CREATED,
    )

    failure_reason = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    captured_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "orders_payment"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order.order_number} - {self.status}"

class Invoice(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="invoice",
    )

    invoice_number = models.CharField(
        max_length=40,
        unique=True,
        editable=False,
    )

    invoice_date = models.DateTimeField(
        auto_now_add=True,
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    coupon_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    final_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=10,
        default="INR",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "orders_invoice"
        ordering = ["-invoice_date"]

    def __str__(self):
        return self.invoice_number

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = timezone.now().year

            while True:
                number = (
                    f"NLINV-{year}-"
                    f"{uuid.uuid4().hex[:8].upper()}"
                )

                if not Invoice.objects.filter(
                    invoice_number=number
                ).exists():
                    self.invoice_number = number
                    break

        super().save(*args, **kwargs)


class StudentBatchPurchase(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"
        REFUNDED = "refunded", "Refunded"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchased_batches",
    )

    batch = models.ForeignKey(
        "admins.Batch",
        on_delete=models.PROTECT,
        related_name="student_purchases",
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="batch_purchases",
    )

    order_item = models.OneToOneField(
        OrderItem,
        on_delete=models.PROTECT,
        related_name="purchase",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    purchased_at = models.DateTimeField(
        auto_now_add=True,
    )

    refunded_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "orders_student_batch_purchase"
        ordering = ["-purchased_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "batch"],
                name="unique_student_batch_purchase",
            )
        ]
        indexes = [
            models.Index(
                fields=["student", "status"]
            ),
            models.Index(
                fields=["batch", "status"]
            ),
        ]

    def __str__(self):
        return (
            f"{self.student.username} - "
            f"{self.batch.batch_name}"
        )

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class Refund(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="refunds",
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refund_requests",
    )

    # =========================================================
    # PUBLIC REFUND REQUEST ID
    # =========================================================
    #
    # Examples:
    #
    #     NEORFD-2026-FA6B8A0C
    #     NEORFD-2026-X7K9M2Q4
    #     NEORFD-2026-P4N8Z6T1
    #
    # This is the public refund ID shown to students/admins.
    #
    # It is:
    #   - random
    #   - unique
    #   - automatically generated
    #   - not based on refund.id
    #   - not sequential
    #   - unchanged when the refund is edited
    # =========================================================

    refund_request_id = models.CharField(
        max_length=40,
        unique=True,
        editable=False,
        blank=True,
        null=True,
        db_index=True,
    )

    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    requested_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    refunded_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    razorpay_refund_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
    )

    admin_note = models.TextField(
        blank=True,
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
    )

    processed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "orders_refund"
        ordering = ["-requested_at"]

    def __str__(self):
        return (
            f"{self.refund_request_id} - "
            f"{self.order.order_number}"
        )

    def save(self, *args, **kwargs):
        # Generate the public refund ID only when
        # this refund does not already have one.
        #
        # Once generated, the same ID is kept permanently,
        # including when the student edits/reopens the refund.

        if not self.refund_request_id:
            year = timezone.now().year

            while True:
                refund_id = (
                    f"NEORFD-{year}-"
                    f"{uuid.uuid4().hex[:8].upper()}"
                )

                # Prevent a duplicate public refund ID.
                if not Refund.objects.filter(
                    refund_request_id=refund_id
                ).exists():
                    self.refund_request_id = refund_id
                    break

        super().save(
            *args,
            **kwargs,
        )
class RefundItem(models.Model):
    refund = models.ForeignKey(
        Refund,
        on_delete=models.CASCADE,
        related_name="items",
    )

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.PROTECT,
        related_name="refund_items",
    )

    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    class Meta:
        db_table = "orders_refund_item"
        constraints = [
            models.UniqueConstraint(
                fields=["refund", "order_item"],
                name="unique_refund_order_item",
            )
        ]

    def __str__(self):
        return (
            f"{self.refund_id} - "
            f"{self.order_item.batch_name}"
        )

# ============================================================
# REFUND ATTEMPT
# ============================================================

class RefundAttempt(models.Model):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    refund = models.ForeignKey(
        Refund,
        on_delete=models.CASCADE,
        related_name="attempts",
    )

    attempt_number = models.PositiveIntegerField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
        db_index=True,
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    razorpay_refund_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    gateway_response = models.JSONField(
        blank=True,
        null=True,
    )

    error_message = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "orders_refund_attempt"
        ordering = ["attempt_number", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "refund",
                    "attempt_number",
                ],
                name="unique_refund_attempt_number",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "refund",
                    "status",
                ],
                name="refund_att_refund_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Refund #{self.refund_id} - "
            f"Attempt #{self.attempt_number} - "
            f"{self.status}"
        )
        
class OrderTimelineEvent(models.Model):
    class EventType(models.TextChoices):
        ORDER_CREATED = (
            "order_created",
            "Order Created",
        )

        PAYMENT_CREATED = (
            "payment_created",
            "Payment Created",
        )

        PAYMENT_PROCESSING = (
            "payment_processing",
            "Payment Processing",
        )

        PAYMENT_SUCCEEDED = (
            "payment_succeeded",
            "Payment Successful",
        )

        PAYMENT_FAILED = (
            "payment_failed",
            "Payment Failed",
        )

        ORDER_CANCELLED = (
            "order_cancelled",
            "Order Cancelled",
        )

        ACCESS_GRANTED = (
            "access_granted",
            "Learning Access Granted",
        )

        ACCESS_REVOKED = (
            "access_revoked",
            "Learning Access Revoked",
        )

        REFUND_REQUESTED = (
            "refund_requested",
            "Refund Requested",
        )

        REFUND_PROCESSING = (
            "refund_processing",
            "Refund Processing",
        )

        REFUND_COMPLETED = (
            "refund_completed",
            "Refund Completed",
        )

        REFUND_REJECTED = (
            "refund_rejected",
            "Refund Rejected",
        )

        REFUND_REOPENED = (
            "refund_reopened",
            "Refund Reopened",
        )

        REFUND_FAILED = (
            "refund_failed",
            "Refund Failed",
        )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="timeline_events",
    )

    refund = models.ForeignKey(
        "Refund",
        on_delete=models.SET_NULL,
        related_name="timeline_events",
        blank=True,
        null=True,
    )

    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        related_name="timeline_events",
        blank=True,
        null=True,
    )

    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
        db_index=True,
    )

    title = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        db_table = "orders_order_timeline_event"
        ordering = [
            "created_at",
            "pk",
        ]
        indexes = [
            models.Index(
                fields=[
                    "order",
                    "created_at",
                ],
                name="ord_timeline_order_idx",
            ),
            models.Index(
                fields=[
                    "event_type",
                    "created_at",
                ],
                name="ord_timeline_type_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.order.order_number} - "
            f"{self.title}"
        )