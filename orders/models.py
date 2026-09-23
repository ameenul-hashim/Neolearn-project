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
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    alternative_phone = models.CharField(
        max_length=20,
        blank=True,
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


class Payment(models.Model):
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

    razorpay_order_id = models.CharField(
        max_length=100,
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
        return f"Refund #{self.pk} - {self.order.order_number}"


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
        