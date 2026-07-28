from decimal import Decimal
from django.utils import timezone
from .models import Batch


# ==========================================================
# FINAL PRICE CALCULATOR
# ==========================================================

def calculate_final_price(batch):

    original_price = batch.original_price or Decimal("0")

    if (
        batch.discount_type == "none"
        or batch.discount_value <= 0
        or not is_offer_active(batch)
    ):
        return original_price

    if batch.discount_type == "percentage":

        discount_amount = (
            original_price
            * batch.discount_value
            / Decimal("100")
        )

        final_price = (
            original_price
            - discount_amount
        )

    elif batch.discount_type == "fixed":

        final_price = (
            original_price
            - batch.discount_value
        )

    else:

        final_price = original_price

    if final_price < Decimal("0"):

        final_price = Decimal("0")

    return final_price.quantize(
        Decimal("0.01")
    )


# ==========================================================
# OFFER STATUS
# ==========================================================

def is_offer_active(batch):

    if batch.discount_type == "none":
        return False

    now = timezone.now()

    if (
        batch.offer_start_date
        and now < batch.offer_start_date
    ):
        return False

    if (
        batch.offer_end_date
        and now > batch.offer_end_date
    ):
        return False

    return True


# ==========================================================
# PUBLISH STATUS
# ==========================================================

def is_publish_active(batch):

    if batch.batch_status != "published":
        return False

    if batch.publish_type == "immediate":
        return True

    if batch.publish_datetime is None:
        return False

    return timezone.now() >= batch.publish_datetime


# ==========================================================
# MARKETPLACE STATUS
# ==========================================================

def get_batch_marketplace_status(batch):

    now = timezone.now()

    if batch.batch_status == "draft":

        return {
            "label": "Draft",
            "color": "gray",
        }

    if batch.batch_status == "archived":

        return {
            "label": "Archived",
            "color": "red",
        }

    if (
        batch.publish_type == "scheduled"
        and batch.publish_datetime
        and now < batch.publish_datetime
    ):

        return {
            "label": "Scheduled",
            "color": "blue",
        }

    if (
        batch.admission_close_datetime
        and now > batch.admission_close_datetime
    ):

        return {
            "label": "Admission Closed",
            "color": "orange",
        }

    return {
        "label": "Admission Open",
        "color": "green",
    }
    
    
# ==========================================================
# CREATE BATCH
# ==========================================================

def create_batch(cleaned_data):

    batch = Batch(**cleaned_data)

    batch.full_clean()

    batch.save()

    return batch


# ==========================================================
# UPDATE BATCH
# ==========================================================

def update_batch(
    batch,
    cleaned_data,
):

    for field, value in cleaned_data.items():

        setattr(
            batch,
            field,
            value,
        )

    batch.full_clean()

    batch.save()

    return batch


# ==========================================================
# BUILD BATCH CONTEXT
# ==========================================================

def build_batch_context(
    *,
    batch=None,
    form_data=None,
    extra_context=None,
):

    context = {
        "batch": batch,
        "form_data": form_data or {},
    }

    if extra_context:

        context.update(extra_context)

    return context

# ==========================================================
# CAN DELETE BATCH
# ==========================================================

def can_delete_batch(
    batch,
    student_count=0,
):

    # Draft batches can always be deleted
    if batch.batch_status == "draft":
        return True

    # Published batch without students
    if (
        batch.batch_status == "published"
        and student_count == 0
    ):
        return True

    # Published batch with students
    if (
        batch.batch_status == "published"
        and student_count > 0
    ):
        return False

    # Archived batch
    if batch.batch_status == "archived":

        if batch.course_end_date is None:
            return False

        # Course still running
        if timezone.now().date() < batch.course_end_date:
            return False

        # Course completed
        return True

    return False


# ==========================================================
# CAN ARCHIVE BATCH
# ==========================================================

def can_archive_batch(
    batch,
    student_count=0,
):

    return (
        batch.batch_status == "published"
        and student_count > 0
    )

# ==========================================================
# CAN PUBLISH BATCH
# ==========================================================

def can_publish_batch(batch):

    return batch.batch_status == "draft"


# ==========================================================
# CAN EDIT BATCH
# ==========================================================

def can_edit_batch(
    batch,
    student_count=0,
):

    return {
        "batch_name": student_count == 0,
        "batch_description": True,
        "batch_thumbnail": True,
        "original_price": student_count == 0,
        "discount_type": True,
        "discount_value": True,
        "offer_start_date": True,
        "offer_end_date": True,
        "publish_type": student_count == 0,
        "publish_datetime": student_count == 0,
        "admission_close_datetime": True,
        "course_end_date": True,
        "batch_status": True,
    }