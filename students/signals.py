
import secrets

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StudentProfile


def generate_neo_student_id():
    """
    Generate a unique student ID in the format:
    NEOCE + 10 hexadecimal characters.
    Total length: 15 characters.
    """

    while True:
        student_id = f"NEOCE{secrets.token_hex(5).upper()}"

        if not StudentProfile.objects.filter(
            neo_student_id=student_id
        ).exists():
            return student_id


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """
    Automatically create a StudentProfile when a new User
    is created, including users created through Google signup.
    """

    if not created:
        return

    # Avoid creating a second profile for the same user.
    if StudentProfile.objects.filter(user=instance).exists():
        return

    with transaction.atomic():
        student_id = generate_neo_student_id()

        try:
            StudentProfile.objects.create(
                user=instance,
                neo_student_id=student_id,
            )
        except IntegrityError:
            # Re-raise unexpected database errors.
            # Do not silently hide profile creation failures.
            raise
