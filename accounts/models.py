# from django.db import models
# from django.contrib.auth.models import User


# class EmailOTP(models.Model):

#     user=models.ForeignKey(
#         User,
#         on_delete=models.CASCADE,
#         db_constraint=False
#     )

#     otp=models.CharField(
#         max_length=6
#     )

#     is_used=models.BooleanField(
#         default=False
#     )

#     created_at=models.DateTimeField(
#         auto_now_add=True
#     )

#     def __str__(self):

#         return self.user.email

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch import receiver
import re


class EmailOTP(models.Model):

    user=models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_constraint=False
    )

    otp=models.CharField(
        max_length=6
    )

    is_used=models.BooleanField(
        default=False
    )

    created_at=models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return self.user.email


# Optional: Signal to ensure username is always clean
@receiver(pre_save, sender=User)
def clean_username(sender, instance, **kwargs):
    """
    Ensure username is always clean and valid before saving.
    """
    if instance.username:
        # Remove special characters, keep alphanumeric and underscore
        instance.username = re.sub(r'[^a-zA-Z0-9_]', '_', instance.username)
        # Remove multiple underscores
        instance.username = re.sub(r'_+', '_', instance.username)
        # Remove leading/trailing underscores
        instance.username = instance.username.strip('_')