from django.db import models
from django.contrib.auth.models import User
from admins.models import Batch


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    profile_image = models.URLField(
        blank=True,
        null=True
    )

    cloudinary_public_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    bio = models.TextField(
        blank=True
    )

    phone = models.CharField(
        max_length=10,
        blank=True
    )

    joined_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.user.username


class StudentWishlist(models.Model):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="wishlists"
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="wishlisted_by"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = "student_wishlist"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["student", "batch"],
                name="unique_student_batch_wishlist"
            )
        ]

    def __str__(self):
        return f"{self.student.username} ❤️ {self.batch.batch_name}"


class Cart(models.Model):
    student = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="cart"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "student_cart"

    def __str__(self):
        return f"Cart - {self.student.username}"

    @property
    def item_count(self):
        return self.items.count()

    @property
    def subtotal(self):
        return sum(
            item.batch.final_price
            for item in self.items.select_related("batch")
        )


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items"
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )

    added_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = "student_cart_item"
        ordering = ["-added_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["cart", "batch"],
                name="unique_cart_batch"
            )
        ]

    def __str__(self):
        return f"{self.cart.student.username} - {self.batch.batch_name}"