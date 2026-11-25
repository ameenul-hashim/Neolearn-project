import re
from PIL import Image, UnidentifiedImageError
from django.utils.dateparse import parse_date
from django.contrib.auth import (
    get_user_model,
    update_session_auth_hash,)
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from django.urls import reverse
from django.core.paginator import Paginator
from admins.models import FAQVideo
from admins.models import (
    Batch,
    Subject,
    Coupon,
)
from orders.models import (
    StudentBatchPurchase,
    Order,
    OrderCoupon,
    Refund,
)

from admins.models import (
    Batch,
    Subject,
    Teacher,
    TeacherBatch,
    TeacherSubject,
)

from orders.helpers import (
    get_refundable_order_items,
)
from admins.helpers import (
    normalize_coupon_code,
    calculate_student_cart_totals,
    calculate_general_cart_coupon,
    calculate_batch_coupon_for_cart,
    calculate_multi_checkout_coupon,
    get_available_student_coupons,
)
from .models import (
    StudentProfile,
    StudentWishlist,
    Cart,
    CartItem,
    CartCoupon,
    QuizAttempt,
    QuizAttemptAnswer,
)

from live_classes.models import LiveClass

from courses.models import (
    CourseChapter,
    ChapterVideo,
    ChapterPDF,
    ChapterQuiz,
    QuizQuestion,
    QuizOption,
)

import cloudinary.uploader

from .models import (
    StudentProfile,
    StudentWishlist,
    Cart,
    CartItem,
)


# ============================================================
# STUDENT ACCESS HELPER
# ============================================================

def is_student_user(user):
    """
    Allow only normal student users inside the student area.

    Staff and superusers must use their respective areas.
    """
    return not user.is_staff and not user.is_superuser


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def dashboard_view(request):

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    return render(
        request,
        'students/dashboard/dashboard.html'
    )


# ============================================================
# STUDENT SETTINGS
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def student_settings_view(request):
    """
    Single student Settings page.

    Handles:
    - Full name
    - Primary phone number
    - Username
    - Email address
    - Password
    - Profile image

    Shared family phone numbers are allowed.
    """

    if not is_student_user(request.user):
        messages.error(
            request,
            "Student access required. Please use the student login area.",
        )
        return redirect("signin")

    User = get_user_model()

    profile, _ = StudentProfile.objects.get_or_create(
        user=request.user
    )

    def save_profile_image(image):
        """
        Validate and save a profile image to Cloudinary.
        Returns (success, message). The profile's existing image is kept
        unless the new image has been uploaded and saved successfully.
        """
        if not image:
            return False, "Please select a profile image."

        if image.size > 2 * 1024 * 1024:
            return False, "Image size must be 2 MB or smaller."

        extension = (
            "." + image.name.rsplit(".", 1)[-1].lower()
            if "." in image.name
            else ""
        )
        if extension not in {".jpg", ".jpeg", ".png"}:
            return False, "Choose a JPG or PNG image."

        try:
            image.seek(0)
            with Image.open(image) as opened_image:
                image_format = opened_image.format
                opened_image.verify()

            if image_format not in {"JPEG", "PNG"}:
                return False, "Choose a valid JPG or PNG image."

            image.seek(0)
        except (UnidentifiedImageError, OSError, ValueError):
            return False, (
                "The image could not be loaded. "
                "Please choose a valid JPG or PNG image."
            )

        old_public_id = profile.cloudinary_public_id

        try:
            uploaded_image = cloudinary.uploader.upload(
                image,
                folder="neolearn_profiles",
                resource_type="image",
                allowed_formats=["jpg", "jpeg", "png"],
            )

            profile.profile_image = uploaded_image["secure_url"]
            profile.cloudinary_public_id = uploaded_image["public_id"]
            profile.save(
                update_fields=["profile_image", "cloudinary_public_id"]
            )

            # Delete the previous Cloudinary image only after the new one
            # has successfully uploaded and the profile record has saved.
            if (
                old_public_id
                and old_public_id != profile.cloudinary_public_id
            ):
                try:
                    cloudinary.uploader.destroy(old_public_id)
                except Exception:
                    pass

            return True, "Profile image updated successfully."

        except Exception:
            return False, (
                "The profile image could not be uploaded. "
                "Please try again."
            )

    # ========================================================
    # SAVE SETTINGS
    # ========================================================

    if request.method == "POST":

        form_type = request.POST.get(
            "form_type",
            "",
        ).strip()

        # ====================================================
        # PERSONAL DETAILS
        # ====================================================

        if form_type == "personal":

            full_name = " ".join(
                request.POST.get("full_name", "").split()
            )

            phone = request.POST.get(
                "phone",
                "",
            ).strip()

            errors = []

            if not full_name:
                errors.append("Full name is required.")

            elif len(full_name) > 150:
                errors.append(
                    "Full name cannot exceed 150 characters."
                )

            # Phone number is optional.
            # Shared family numbers are intentionally allowed.
            if phone and not re.fullmatch(r"[6-9]\d{9}", phone):
                errors.append(
                    "Enter a valid 10-digit Indian mobile number "
                    "starting with 6, 7, 8, or 9."
                )

            # The updated profile form submits the photo and personal details
            # together using form_type="personal". Process the photo here too.
            image = request.FILES.get("profile_image")

            if errors:
                for error in errors:
                    messages.error(request, error)
                return redirect("student_settings")

            if image:
                image_saved, image_message = save_profile_image(image)
                if not image_saved:
                    messages.error(request, image_message)
                    return redirect("student_settings")

            name_parts = full_name.split(" ", 1)
            request.user.first_name = name_parts[0]
            request.user.last_name = (
                name_parts[1] if len(name_parts) > 1 else ""
            )
            request.user.save(update_fields=["first_name", "last_name"])

            # Shared family phone numbers are allowed; no uniqueness check.
            profile.phone = phone
            profile.save(update_fields=["phone"])

            if image:
                messages.success(
                    request,
                    "Profile photo and personal details updated successfully.",
                )
            else:
                messages.success(
                    request,
                    "Personal details updated successfully.",
                )

            return redirect("student_settings")

        # ====================================================
        # USERNAME AND EMAIL
        # ====================================================

        if form_type == "account":

            username = request.POST.get(
                "username",
                "",
            ).strip()

            email = request.POST.get(
                "email",
                "",
            ).strip()

            errors = []

            # -----------------------------
            # USERNAME VALIDATION
            # -----------------------------

            if not username:

                errors.append("Username is required.")

            elif len(username) > 150:

                errors.append(
                    "Username cannot exceed 150 characters."
                )

            else:

                try:
                    User._meta.get_field("username").clean(
                        username,
                        request.user,
                    )

                except ValidationError:

                    errors.append(
                        "Enter a valid username."
                    )

            # Check all user accounts, excluding the current account.
            if username and User.objects.filter(
                username__iexact=username
            ).exclude(
                pk=request.user.pk
            ).exists():

                errors.append(
                    "This username is already in use. "
                    "Choose another username."
                )

            # -----------------------------
            # EMAIL VALIDATION
            # -----------------------------

            if not email:

                errors.append(
                    "Email address is required."
                )

            elif len(email) > 254:

                errors.append(
                    "Email address cannot exceed 254 characters."
                )

            else:

                try:
                    validate_email(email)

                except ValidationError:

                    errors.append(
                        "Enter a valid email address."
                    )

            email_valid = (
                bool(email)
                and len(email) <= 254
                and not any(
                    error in errors
                    for error in [
                        "Enter a valid email address.",
                        "Email address is required.",
                        "Email address cannot exceed 254 characters.",
                    ]
                )
            )

            # Check the entire User table, including inactive accounts.
            if email_valid and User.objects.filter(
                email__iexact=email
            ).exclude(
                pk=request.user.pk
            ).exists():

                errors.append(
                    "This email address is already in use. "
                    "Use a different email address."
                )

            if errors:

                for error in errors:
                    messages.error(request, error)

            else:

                request.user.username = username
                request.user.email = email

                try:

                    request.user.save(
                        update_fields=[
                            "username",
                            "email",
                        ]
                    )

                    messages.success(
                        request,
                        "Username and email updated successfully.",
                    )

                except Exception:

                    messages.error(
                        request,
                        "Account details could not be saved. "
                        "Please check the username and try again.",
                    )

            return redirect("student_settings")

        # ====================================================
        # PASSWORD CHANGE
        # ====================================================

        if form_type == "password":

            current_password = request.POST.get(
                "current_password",
                "",
            )

            new_password = request.POST.get(
                "new_password",
                "",
            )

            confirm_password = request.POST.get(
                "confirm_password",
                "",
            )

            errors = []

            if not current_password:

                errors.append(
                    "Enter your current password."
                )

            elif not request.user.check_password(
                current_password
            ):

                errors.append(
                    "Your current password is incorrect."
                )

            if not new_password:

                errors.append(
                    "Enter a new password."
                )

            else:

                if len(new_password) < 8:
                    errors.append(
                        "Password must contain at least 8 characters."
                    )

                if not re.search(r"[A-Z]", new_password):
                    errors.append(
                        "Password must contain an uppercase letter."
                    )

                if not re.search(r"[a-z]", new_password):
                    errors.append(
                        "Password must contain a lowercase letter."
                    )

                if not re.search(r"\d", new_password):
                    errors.append(
                        "Password must contain a number."
                    )

                if not re.search(
                    r"[^A-Za-z0-9]",
                    new_password,
                ):
                    errors.append(
                        "Password must contain a special character."
                    )

                if request.user.check_password(new_password):
                    errors.append(
                        "Your new password must differ from "
                        "your current password."
                    )

            if new_password != confirm_password:

                errors.append(
                    "The new passwords do not match."
                )

            if errors:

                for error in errors:
                    messages.error(request, error)

            else:

                request.user.set_password(new_password)

                request.user.save(
                    update_fields=["password"]
                )

                # Keep the student logged in after changing password.
                update_session_auth_hash(
                    request,
                    request.user,
                )

                messages.success(
                    request,
                    "Password changed successfully.",
                )

            return redirect("student_settings")

        # ====================================================
        # PROFILE IMAGE
        # ====================================================

        if form_type == "image":
            image = request.FILES.get("profile_image")
            image_saved, image_message = save_profile_image(image)

            if image_saved:
                messages.success(request, image_message)
            else:
                messages.error(request, image_message)

            return redirect("student_settings")

        messages.error(
            request,
            "Invalid Settings form. Please try again.",
        )

        return redirect("student_settings")

    # ========================================================
    # DISPLAY SETTINGS PAGE
    # ========================================================

    full_name = " ".join(
        part
        for part in [
            request.user.first_name,
            request.user.last_name,
        ]
        if part
    ).strip()

    return render(
        request,
        "students/settings/settings.html",
        {
            "profile": profile,
            "full_name": full_name,
        },
    )

# ============================================================
# MARKETPLACE
# ============================================================

@login_required(login_url='signin')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def marketplace_view(request):
    """Render all visible Marketplace batches with student-specific status and filters."""

    if not is_student_user(request.user):
        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )
        return redirect('signin')

    now = timezone.now()

    # All Batches is the default and includes every marketplace-visible
    # published or archived batch. Draft/hidden batches remain excluded.
    current_status = request.GET.get('status', 'all').strip().lower()
    search_query = request.GET.get('search', '').strip()
    subject_id = request.GET.get('subject', '').strip()
    batch_id = request.GET.get('batch_id', '').strip()
    teacher_id = request.GET.get('teacher', '').strip()
    sort_option = request.GET.get('sort', 'newest').strip().lower()
    discount_option = request.GET.get('discount', '').strip().lower()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()

    allowed_statuses = {
        'all', 'buy_now', 'coming_soon', 'admissions_closed', 'purchased'
    }
    if current_status not in allowed_statuses:
        current_status = 'all'

    allowed_discounts = {'', 'percentage', 'fixed', 'none'}
    if discount_option not in allowed_discounts:
        discount_option = ''

    # Keep the actual purchase timestamp for this student, not the batch's
    # creation/publish date. If multiple active records exist, use the latest.
    active_purchases = (
        StudentBatchPurchase.objects.filter(
            student=request.user,
            status=StudentBatchPurchase.Status.ACTIVE,
        )
        .order_by('purchased_at')
        .values_list('batch_id', 'purchased_at')
    )
    purchased_batch_dates = {
        batch_pk: purchased_at
        for batch_pk, purchased_at in active_purchases
    }
    purchased_batch_ids = set(purchased_batch_dates.keys())

    # Dynamic batch-name chips only use real visible Marketplace batches.
    marketplace_filter_batches = (
        Batch.objects.filter(
            marketplace_visible=True,
            batch_status__in=('published', 'archived'),
        )
        .order_by('batch_name')
    )

    batch_queryset = Batch.objects.filter(
        marketplace_visible=True,
        batch_status__in=('published', 'archived'),
    )

    if batch_id:
        try:
            batch_queryset = batch_queryset.filter(pk=int(batch_id))
        except (TypeError, ValueError):
            batch_id = ''

    if teacher_id:
        try:
            batch_queryset = batch_queryset.filter(assigned_teachers__pk=int(teacher_id))
        except (TypeError, ValueError):
            teacher_id = ''

    if subject_id:
        try:
            batch_queryset = batch_queryset.filter(subjects__pk=int(subject_id))
        except (TypeError, ValueError):
            subject_id = ''

    if search_query:
        batch_queryset = batch_queryset.filter(
            Q(batch_name__icontains=search_query)
            | Q(batch_description__icontains=search_query)
            | Q(subjects__subject_name__icontains=search_query)
        )

    # Convert to a list so the existing model status property and the exact
    # active offer price are evaluated consistently for each Marketplace card.
    batches = list(
        batch_queryset.distinct().prefetch_related('subjects', 'assigned_teachers')
    )

    for batch in batches:
        batch.marketplace_card_status = batch.marketplace_status
        batch.student_purchase_date = purchased_batch_dates.get(batch.pk)
        batch.current_selling_price = batch.get_current_price()
        original_price_value = float(batch.original_price or 0)
        current_price_value = float(batch.current_selling_price or 0)
        batch.has_current_discount = current_price_value < original_price_value
        batch.current_discount_amount = max(
            original_price_value - current_price_value, 0
        )

    # A student's purchase takes priority over the batch's current public status.
    if current_status == 'purchased':
        batches = [b for b in batches if b.pk in purchased_batch_ids]
    elif current_status == 'buy_now':
        batches = [
            b for b in batches
            if b.pk not in purchased_batch_ids and b.marketplace_card_status == 'buy_now'
        ]
    elif current_status == 'coming_soon':
        batches = [
            b for b in batches
            if b.pk not in purchased_batch_ids and b.marketplace_card_status == 'coming_soon'
        ]
    elif current_status == 'admissions_closed':
        batches = [
            b for b in batches
            if b.pk not in purchased_batch_ids and b.marketplace_card_status == 'admissions_closed'
        ]
    # current_status == 'all': deliberately do not remove any visible status.

    # Discount filter: blank means All Discounts (no discount filtering).
    if discount_option == 'percentage':
        batches = [
            b for b in batches
            if b.discount_type == 'percentage' and b.has_current_discount
        ]
    elif discount_option == 'fixed':
        batches = [
            b for b in batches
            if b.discount_type == 'fixed' and b.has_current_discount
        ]
    elif discount_option == 'none':
        batches = [b for b in batches if not b.has_current_discount]

    min_price_value = None
    max_price_value = None
    if min_price:
        try:
            min_price_value = float(min_price)
            if min_price_value < 0:
                min_price, min_price_value = '', None
        except (TypeError, ValueError):
            min_price, min_price_value = '', None
    if max_price:
        try:
            max_price_value = float(max_price)
            if max_price_value < 0:
                max_price, max_price_value = '', None
        except (TypeError, ValueError):
            max_price, max_price_value = '', None

    if min_price_value is not None:
        batches = [
            b for b in batches
            if float(b.current_selling_price or 0) >= min_price_value
        ]
    if max_price_value is not None:
        batches = [
            b for b in batches
            if float(b.current_selling_price or 0) <= max_price_value
        ]

    sort_choices = [
        ('newest', 'Newest'),
        ('oldest', 'Oldest'),
        ('a_z', 'A → Z'),
        ('z_a', 'Z → A'),
        ('price_low', 'Price: Low → High'),
        ('price_high', 'Price: High → Low'),
        ('discount', 'Highest Discount'),
    ]
    allowed_sorts = {value for value, _label in sort_choices}
    if sort_option not in allowed_sorts:
        sort_option = 'newest'

    if sort_option == 'oldest':
        batches.sort(key=lambda b: b.created_at)
    elif sort_option == 'a_z':
        batches.sort(key=lambda b: (b.batch_name or '').lower())
    elif sort_option == 'z_a':
        batches.sort(key=lambda b: (b.batch_name or '').lower(), reverse=True)
    elif sort_option == 'price_low':
        batches.sort(key=lambda b: float(b.current_selling_price or 0))
    elif sort_option == 'price_high':
        batches.sort(
            key=lambda b: float(b.current_selling_price or 0), reverse=True
        )
    elif sort_option == 'discount':
        batches.sort(
            key=lambda b: (b.current_discount_amount, b.created_at),
            reverse=True,
        )
    else:
        batches.sort(key=lambda b: b.created_at, reverse=True)

    # Keep the agreed 12 cards per page.
    paginator = Paginator(batches, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    batches = page_obj.object_list

    wishlisted_batch_ids = set(
        StudentWishlist.objects.filter(student=request.user)
        .values_list('batch_id', flat=True)
    )

    try:
        cart = Cart.objects.get(student=request.user)
        cart_batch_ids = set(cart.items.values_list('batch_id', flat=True))
    except Cart.DoesNotExist:
        cart_batch_ids = set()

    subjects = (
        Subject.objects.filter(
            batch__marketplace_visible=True,
            batch__batch_status__in=('published', 'archived'),
        )
        .order_by('subject_name')
        .distinct()
    )

    # Teacher filter data is retained for compatibility with existing views/templates.
    filter_batch_rows = list(
        marketplace_filter_batches.prefetch_related('assigned_teachers')
    )
    teacher_batch_counts = {}
    for filter_batch in filter_batch_rows:
        for assigned_teacher in filter_batch.assigned_teachers.all():
            teacher_batch_counts[assigned_teacher.pk] = (
                teacher_batch_counts.get(assigned_teacher.pk, 0) + 1
            )
    marketplace_filter_teachers = list(
        Teacher.objects.filter(pk__in=teacher_batch_counts.keys()).order_by('full_name')
    )
    for marketplace_teacher in marketplace_filter_teachers:
        marketplace_teacher.marketplace_batch_count = teacher_batch_counts.get(
            marketplace_teacher.pk, 0
        )

    return render(
        request,
        'students/marketplace/marketplace.html',
        {
            'batches': batches,
            'marketplace_filter_batches': marketplace_filter_batches,
            'subjects': subjects,
            'current_status': current_status,
            'search_query': search_query,
            'subject_id': subject_id,
            'batch_id': batch_id,
            'teacher_id': teacher_id,
            'marketplace_filter_teachers': marketplace_filter_teachers,
            'sort_option': sort_option,
            'sort_choices': sort_choices,
            'discount_option': discount_option,
            'min_price': min_price,
            'max_price': max_price,
            'wishlisted_batch_ids': wishlisted_batch_ids,
            'cart_batch_ids': cart_batch_ids,
            'purchased_batch_ids': purchased_batch_ids,
            'purchased_batch_dates': purchased_batch_dates,
            'page_obj': page_obj,
            'paginator': paginator,
        },
    )

# ============================================================
# MARKETPLACE DETAIL
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def marketplace_detail_view(request, batch_id):
    """Display the public details for a published Marketplace batch.

    This view deliberately reuses the existing Batch, Subject, Teacher,
    gallery, feature, demo, cart, wishlist and purchase records. It does not
    grant access to protected course chapters or lessons.
    """

    if not is_student_user(request.user):
        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )
        return redirect('signin')

    now = timezone.now()

    batch = get_object_or_404(
        Batch.objects.filter(
            batch_status__in=('published', 'archived'),
            marketplace_visible=True,
        ).prefetch_related(
            'gallery_images',
            'features',
        ),
        pk=batch_id,
    )

    # Only published subjects are displayed to Marketplace visitors.
    subjects = list(
        Subject.objects.filter(
            batch=batch,
            subject_status='published',
        ).annotate(
            published_chapter_count=Count(
                'course_chapters',
                filter=Q(course_chapters__status='published'),
                distinct=True,
            ),
        ).prefetch_related(
            Prefetch(
                'assigned_teachers',
                queryset=TeacherSubject.objects.filter(
                    batch=batch,
                    is_active=True,
                    teacher__is_blocked=False,
                ).select_related('teacher'),
                to_attr='active_teacher_assignments',
            ),
        ).order_by('created_at', 'pk')
    )

    # Add a convenient list of real assigned teacher profiles to each
    # subject. The related manager contains TeacherSubject assignments.
    for subject in subjects:
        subject.detail_teachers = [
            assignment.teacher
            for assignment in subject.active_teacher_assignments
        ]

    # Include teachers assigned either to the whole batch or to at least
    # one published subject in this batch. Never show blocked/inactive links.
    teachers = list(
        Teacher.objects.filter(
            is_blocked=False,
        ).filter(
            Q(
                assigned_batches__batch=batch,
                assigned_batches__is_active=True,
            )
            |
            Q(
                assigned_subjects__batch=batch,
                assigned_subjects__is_active=True,
                assigned_subjects__subject__subject_status='published',
            )
        ).distinct().order_by('full_name')
    )

    # Main thumbnail first, followed by the ordered additional gallery.
    gallery_images = []
    if batch.batch_thumbnail:
        gallery_images.append({
            'url': batch.batch_thumbnail.url,
            'alt': f'{batch.batch_name} main image',
            'is_main': True,
        })

    for gallery_image in batch.gallery_images.all():
        if gallery_image.image:
            gallery_images.append({
                'url': gallery_image.image.url,
                'alt': f'{batch.batch_name} gallery image',
                'is_main': False,
            })

    # Overall demo is optional. BatchDemo is a OneToOne relation.
    try:
        batch_demo = batch.demo
        if not (batch_demo.video_file or batch_demo.external_url):
            batch_demo = None
    except Batch.demo.RelatedObjectDoesNotExist:
        batch_demo = None

    # The supplied admins/models.py defines a batch-wide demo but does not
    # define a subject-demo model. Keep this empty until the actual subject
    # demo storage model is confirmed; do not fabricate demo URLs.
    subject_demos = []

    # Current student state: wishlist, cart and active purchase.
    is_wishlisted = StudentWishlist.objects.filter(
        student=request.user,
        batch=batch,
    ).exists()

    cart = Cart.objects.filter(student=request.user).first()
    is_in_cart = bool(
        cart and cart.items.filter(batch=batch).exists()
    )

    active_purchase = StudentBatchPurchase.objects.filter(
        student=request.user,
        batch=batch,
        status=StudentBatchPurchase.Status.ACTIVE,
    ).first()
    already_purchased = active_purchase is not None

    # Use the model's existing marketplace status and offer calculation.
    marketplace_status = batch.marketplace_status
    offer_is_active = batch.is_offer_active
    offer_end_timestamp = None
    if offer_is_active and batch.offer_end_date:
        offer_end_timestamp = int(batch.offer_end_date.timestamp())

    duration_parts = []
    if batch.course_duration_years:
        duration_parts.append(
            f"{batch.course_duration_years} "
            f"{'Year' if batch.course_duration_years == 1 else 'Years'}"
        )
    if batch.course_duration_months:
        duration_parts.append(
            f"{batch.course_duration_months} "
            f"{'Month' if batch.course_duration_months == 1 else 'Months'}"
        )
    course_duration_display = ' '.join(duration_parts) or 'Not specified'

    # Admission dates and course end date are existing Batch fields.
    admission_closing = batch.admission_close_datetime
    course_end_date = batch.course_end_date

    return render(
        request,
        'students/marketplace/marketplace-detail.html',
        {
            'batch': batch,
            'gallery_images': gallery_images,
            'subjects': subjects,
            'teachers': teachers,
            'batch_demo': batch_demo,
            'subject_demos': subject_demos,
            'is_wishlisted': is_wishlisted,
            'is_in_cart': is_in_cart,
            'already_purchased': already_purchased,
            'active_purchase': active_purchase,
            'marketplace_status': marketplace_status,
            'can_purchase': marketplace_status == 'buy_now' and not already_purchased,
            'offer_is_active': offer_is_active,
            'offer_end_timestamp': offer_end_timestamp,
            'course_duration_display': course_duration_display,
            'admission_closing': admission_closing,
            'course_end_date': course_end_date,
            'current_time': now,
        },
    )


# ============================================================
# WISHLIST PAGE
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def wishlist_view(request):
    """Show saved batches in every marketplace status for this student."""

    if not is_student_user(request.user):
        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )
        return redirect('signin')

    # A successfully purchased batch no longer needs to remain in Wishlist.
    # This deletes only StudentWishlist rows; cart records are never touched.
    active_purchased_ids = set(
        StudentBatchPurchase.objects.filter(
            student=request.user,
            status=StudentBatchPurchase.Status.ACTIVE,
        ).values_list('batch_id', flat=True)
    )
    if active_purchased_ids:
        StudentWishlist.objects.filter(
            student=request.user,
            batch_id__in=active_purchased_ids,
        ).delete()

    wishlist_items = list(
        StudentWishlist.objects.filter(student=request.user)
        .select_related('batch')
        .prefetch_related('batch__subjects', 'batch__assigned_teachers')
        .order_by('-created_at')
    )

    wishlist_batch_ids = [item.batch_id for item in wishlist_items]
    purchased_batch_ids = set(active_purchased_ids.intersection(wishlist_batch_ids))

    for item in wishlist_items:
        batch = item.batch
        batch.marketplace_card_status = batch.marketplace_status
        batch.is_already_purchased = batch.pk in purchased_batch_ids
        batch.current_selling_price = batch.get_current_price()
        batch.has_current_discount = (
            float(batch.current_selling_price or 0) < float(batch.original_price or 0)
        )

    cart_batch_ids = set(
        CartItem.objects.filter(
            cart__student=request.user,
            batch_id__in=wishlist_batch_ids,
        ).values_list('batch_id', flat=True)
    )

    wishlist_count = len(wishlist_items)
    cart_count = CartItem.objects.filter(cart__student=request.user).count()

    return render(
        request,
        'students/wishlist/wishlist.html',
        {
            'wishlist_items': wishlist_items,
            'wishlist_count': wishlist_count,
            'purchased_batch_ids': purchased_batch_ids,
            'cart_batch_ids': cart_batch_ids,
            'cart_count': cart_count,
        },
    )


# ============================================================
# TOGGLE WISHLIST
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def toggle_wishlist_view(request, batch_id):

    # ========================================================
    # STUDENT ACCESS
    # ========================================================

    if not is_student_user(request.user):

        if request.headers.get(
            'X-Requested-With'
        ) == 'XMLHttpRequest':

            return JsonResponse(
                {
                    'success': False,
                    'message': 'Student access required.',
                },
                status=403,
            )

        messages.error(
            request,
            'Student access required.'
        )

        return redirect('marketplace')

    # ========================================================
    # ONLY POST
    # ========================================================

    if request.method != 'POST':

        if request.headers.get(
            'X-Requested-With'
        ) == 'XMLHttpRequest':

            return JsonResponse(
                {
                    'success': False,
                    'message': 'Invalid wishlist request.',
                },
                status=400,
            )

        messages.error(
            request,
            'Invalid wishlist request.'
        )

        return redirect('marketplace')

    # ========================================================
    # EXPLICIT REMOVE (works for every saved batch status)
    # ========================================================

    if request.POST.get('wishlist_action') == 'remove' or request.POST.get('action') == 'remove':
        # Do not fetch/validate the Batch here. A saved wishlist row must be
        # removable even if its batch is Coming Soon, Admissions Closed,
        # archived, hidden from Marketplace, or otherwise unavailable.
        deleted_count, _ = StudentWishlist.objects.filter(
            student=request.user,
            batch_id=batch_id,
        ).delete()

        wishlist_count = StudentWishlist.objects.filter(
            student=request.user
        ).count()
        cart_count = CartItem.objects.filter(
            cart__student=request.user
        ).count()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if deleted_count:
                messages.info(request, 'Batch removed from your wishlist.')
            return JsonResponse({
                'success': True,
                'wishlisted': False,
                'removed': bool(deleted_count),
                'wishlist_count': wishlist_count,
                'cart_count': cart_count,
                'batch_id': batch_id,
            })

        if deleted_count:
            messages.info(request, 'Batch removed from your wishlist.')
        return redirect(request.META.get('HTTP_REFERER') or 'marketplace')

    # ========================================================
    # VALID MARKETPLACE BATCH
    # ========================================================

    batch = get_object_or_404(
        Batch,
        id=batch_id,
        batch_status__in=('published', 'archived'),
        marketplace_visible=True,
    )

    # ========================================================
    # CHECK EXISTING WISHLIST
    # ========================================================

    wishlist = StudentWishlist.objects.filter(
        student=request.user,
        batch=batch,
    ).first()

    # ========================================================
    # REMOVE
    # ========================================================

    if wishlist:

        wishlist.delete()

        wishlisted = False

    # ========================================================
    # ADD
    # ========================================================

    else:

        StudentWishlist.objects.create(
            student=request.user,
            batch=batch,
        )

        wishlisted = True

    # ========================================================
    # UPDATED COUNT
    # ========================================================

    wishlist_count = StudentWishlist.objects.filter(
        student=request.user
    ).count()

    # ========================================================
    # AJAX RESPONSE
    # ========================================================

    if request.headers.get(
        'X-Requested-With'
    ) == 'XMLHttpRequest':

        if wishlisted:
            messages.success(
                request,
                f'\"{batch.batch_name}\" has been added to your wishlist.'
            )
        else:
            messages.info(
                request,
                f'\"{batch.batch_name}\" has been removed from your wishlist.'
            )

        return JsonResponse(
            {
                'success': True,
                'wishlisted': wishlisted,
                'wishlist_count': wishlist_count,
                'cart_count': CartItem.objects.filter(cart__student=request.user).count(),
                'batch_id': batch.id,
                'message': (
                    f'\"{batch.batch_name}\" has been added to your wishlist.'
                    if wishlisted else
                    f'\"{batch.batch_name}\" has been removed from your wishlist.'
                ),
            }
        )

    # ========================================================
    # NORMAL POST FALLBACK
    # ========================================================

    if wishlisted:

        messages.success(
            request,
            f'"{batch.batch_name}" has been added to your wishlist.'
        )

    else:

        messages.info(
            request,
            f'"{batch.batch_name}" has been removed from your wishlist.'
        )

    return redirect('marketplace')


# ============================================================
# WISHLIST COUNT
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def wishlist_count_view(request):

    if not is_student_user(request.user):

        return JsonResponse(
            {
                'success': False,
                'count': 0,
                'message': 'Student access required.',
            },
            status=403,
        )

    count = StudentWishlist.objects.filter(
        student=request.user
    ).count()

    return JsonResponse(
        {
            'success': True,
            'count': count,
        }
    )


# ============================================================
# ADD TO CART
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def add_to_cart_view(request, batch_id):
    """Add a purchasable batch to the cart; supports AJAX and normal POST."""

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def cart_response(success, message, status=200, redirect_url=None):
        if is_ajax:
            # The Wishlist reloads after a successful AJAX action, so the
            # existing base_student message/toast UI can display this message.
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)

            cart_count = CartItem.objects.filter(cart__student=request.user).count()
            wishlist_count = StudentWishlist.objects.filter(student=request.user).count()
            return JsonResponse({
                'success': success,
                'message': message,
                'cart_count': cart_count,
                'wishlist_count': wishlist_count,
                'batch_id': batch_id,
                'redirect_url': reverse(redirect_url) if redirect_url else None,
            }, status=status)
        if success:
            messages.success(request, message)
        else:
            messages.info(request, message)
        return redirect(redirect_url or 'marketplace')

    if not is_student_user(request.user):
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Student access required.'}, status=403)
        messages.error(request, 'Admin login is not allowed here. Please use the admin login area.')
        return redirect('signin')

    if request.method != 'POST':
        return cart_response(False, 'Invalid cart request.', status=400)

    # Buy Now uses the same cart rules, then opens the cart immediately.
    buy_now = request.POST.get('buy_now') == '1'

    batch = get_object_or_404(
        Batch, id=batch_id, batch_status='published', marketplace_visible=True
    )

    if batch.marketplace_status != 'buy_now':
        return cart_response(False, 'This batch is not currently available for purchase.', status=400)

    if StudentBatchPurchase.objects.filter(
        student=request.user,
        batch=batch,
        status=StudentBatchPurchase.Status.ACTIVE,
    ).exists():
        return cart_response(
            True,
            f'"{batch.batch_name}" is already in your learning.',
            redirect_url='my_learning',
        )

    cart, _ = Cart.objects.get_or_create(student=request.user)
    _, item_created = CartItem.objects.get_or_create(cart=cart, batch=batch)

    if item_created:
        message = f'"{batch.batch_name}" has been added to your cart.'
    else:
        message = f'"{batch.batch_name}" is already in your cart.'

    return cart_response(
        True,
        message,
        redirect_url='cart' if buy_now else None,
    )


@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def cart_view(request):

    if not is_student_user(request.user):

        messages.error(
            request,
            "Student access required."
        )

        return redirect("signin")

    cart, created = Cart.objects.get_or_create(
        student=request.user
    )

    cart_items = list(
        cart.items
        .select_related("batch")
        .prefetch_related(
            "batch__subjects",
            "batch__assigned_teachers__teacher",
        )
    )

    # --------------------------------------------------------
    # CART-ONLY CURRENT BATCH PRICES
    # --------------------------------------------------------
    # The shared cart coupon helpers read batch.final_price.
    # That stored field can still contain an expired offer price.
    # Resolve the time-aware selling price for this Cart request and
    # override final_price only on these in-memory Batch instances.
    # Nothing is saved to the database, and no shared pricing logic
    # or Marketplace/Admin/Checkout code is changed.
    #
    # Active offer: get_current_price() returns the offer price.
    # Expired/no offer: get_current_price() returns original_price.
    # --------------------------------------------------------

    for cart_item in cart_items:
        batch = cart_item.batch
        batch.final_price = batch.get_current_price()

    # --------------------------------------------------------
    # CALCULATE CURRENT CART TOTALS
    # --------------------------------------------------------

    totals = calculate_student_cart_totals(
        cart,
        cart_items,
        request.user,
    )

    # --------------------------------------------------------
    # SHOW MESSAGES FOR INVALID COUPONS
    # --------------------------------------------------------

    for invalid in totals["invalid_coupons"]:

        messages.warning(
            request,
            (
                f"Coupon removed: "
                f"{invalid['reason']}"
            )
        )

    # --------------------------------------------------------
    # AVAILABLE COUPONS
    # --------------------------------------------------------

    coupon_catalog = get_available_student_coupons(
        cart_items,
        request.user,
        applied_entries=list(
            cart.cart_coupons
            .select_related("coupon", "batch")
        ),
    )

    cart_count = len(cart_items)

    return render(
        request,
        "students/cart/cart.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "cart_count": cart_count,

            "subtotal": totals["subtotal"],
            "discount_total": totals["discount_total"],
            "total": totals["total"],

            "applied_coupons": totals[
                "applied_coupons"
            ],

            # Full coupon catalog for the coupon panel.
            # Each card contains is_available/reason so the template can
            # keep relevant coupons visible while disabling incompatible ones.
            "coupon_catalog": coupon_catalog,

            # Backward-compatible key for any existing template code.
            "available_coupons": coupon_catalog,
        },
    )

# ============================================================
# REMOVE FROM CART
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def remove_from_cart_view(request, batch_id):

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    if request.method != 'POST':

        messages.error(
            request,
            'Invalid cart request.'
        )

        return redirect('cart')

    try:

        cart = Cart.objects.get(
            student=request.user
        )

    except Cart.DoesNotExist:

        messages.info(
            request,
            'Your cart is already empty.'
        )

        return redirect('cart')

    cart_item = (
        CartItem.objects.filter(
            cart=cart,
            batch_id=batch_id,
        )
        .select_related(
            'batch'
        )
        .first()
    )

    if not cart_item:

        messages.warning(
            request,
            'This item is not in your cart.'
        )

        return redirect('cart')

    batch_name = cart_item.batch.batch_name

    cart_item.delete()

    messages.success(
        request,
        f'"{batch_name}" has been removed from your cart.'
    )

    return redirect('cart')


# ============================================================
# CLEAR CART
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def clear_cart_view(request):

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    if request.method != 'POST':

        messages.error(
            request,
            'Invalid cart request.'
        )

        return redirect('cart')

    try:

        cart = Cart.objects.get(
            student=request.user
        )

    except Cart.DoesNotExist:

        messages.info(
            request,
            'Your cart is already empty.'
        )

        return redirect('cart')

    # --------------------------------------------------------
    # REMOVE TEMPORARY APPLIED COUPONS
    # --------------------------------------------------------

    cart.cart_coupons.all().delete()

    # --------------------------------------------------------
    # REMOVE CART ITEMS
    # --------------------------------------------------------

    deleted_count, _ = cart.items.all().delete()

    if deleted_count:

        messages.success(
            request,
            'Your cart has been cleared successfully.'
        )

    else:

        messages.info(
            request,
            'Your cart is already empty.'
        )

    return redirect('cart')

# ============================================================
# APPLY COUPON
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def apply_coupon_view(request):

    if not is_student_user(request.user):
        messages.error(request, "Student access required.")
        return redirect("signin")

    if request.method != "POST":
        messages.error(request, "Invalid coupon request.")
        return redirect("cart")

    cart, created = Cart.objects.get_or_create(
        student=request.user
    )

    code = normalize_coupon_code(
        request.POST.get("coupon_code")
    )

    if not code:
        messages.error(request, "Please enter a coupon code.")
        return redirect("cart")

    coupon = (
        Coupon.objects
        .filter(code__iexact=code)
        .prefetch_related("batch_rules__batch")
        .first()
    )

    if coupon is None:
        messages.error(request, "Invalid coupon code.")
        return redirect("cart")

    cart_items = list(
        cart.items
        .select_related("batch")
    )

    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    applied_entries = list(
        cart.cart_coupons
        .select_related("coupon", "batch")
    )

    # --------------------------------------------------------
    # Coupon already applied
    # --------------------------------------------------------
    if any(
        entry.coupon_id == coupon.pk
        for entry in applied_entries
    ):
        messages.info(
            request,
            "This coupon is already applied."
        )
        return redirect("cart")

    # --------------------------------------------------------
    # Cart batch information
    # --------------------------------------------------------
    cart_batch_ids = {
        item.batch_id
        for item in cart_items
    }

    multiple_batches = len(cart_batch_ids) > 1

    # --------------------------------------------------------
    # Already applied coupon modes
    # --------------------------------------------------------
    batch_entries = [
        entry
        for entry in applied_entries
        if entry.coupon.coupon_type == "batch_specific"
    ]

    multi_entries = [
        entry
        for entry in applied_entries
        if entry.coupon.coupon_type == "multi_checkout"
    ]

    general_entries = [
        entry
        for entry in applied_entries
        if entry.coupon.coupon_type == "general"
    ]

    # ========================================================
    # GENERAL COUPON
    # ========================================================
    if coupon.coupon_type == "general":

        if multiple_batches:
            messages.error(
                request,
                "General coupons are not available for multiple-batch checkout."
            )
            return redirect("cart")

        if general_entries:
            messages.error(
                request,
                "Only one general coupon can be applied."
            )
            return redirect("cart")

        if batch_entries or multi_entries:
            messages.error(
                request,
                "General coupons cannot be combined with another coupon mode."
            )
            return redirect("cart")

        result = calculate_general_cart_coupon(
            coupon,
            cart_items,
            student=request.user,
        )

        if not result["eligible"]:
            messages.error(
                request,
                result["reason"]
            )
            return redirect("cart")

        CartCoupon.objects.create(
            cart=cart,
            coupon=coupon,
            batch=None,
        )

    # ========================================================
    # MULTI CHECKOUT COUPON
    # ========================================================
    elif coupon.coupon_type == "multi_checkout":

        if not multiple_batches:
            messages.error(
                request,
                "Multi Checkout coupons require multiple batches in the cart."
            )
            return redirect("cart")

        if multi_entries:
            messages.error(
                request,
                "Only one Multi Checkout coupon can be applied."
            )
            return redirect("cart")

        if batch_entries:
            messages.error(
                request,
                "Multi Checkout cannot be combined with Batch Specific coupons."
            )
            return redirect("cart")

        if general_entries:
            messages.error(
                request,
                "Multi Checkout cannot be combined with General coupons."
            )
            return redirect("cart")

        result = calculate_multi_checkout_coupon(
            coupon,
            cart_items,
            student=request.user,
        )

        if not result["eligible"]:
            messages.error(
                request,
                result["reason"]
            )
            return redirect("cart")

        CartCoupon.objects.create(
            cart=cart,
            coupon=coupon,
            batch=None,
        )

    # ========================================================
    # BATCH SPECIFIC COUPON
    # ========================================================
    elif coupon.coupon_type == "batch_specific":

        if multi_entries:
            messages.error(
                request,
                "Batch Specific coupons cannot be combined with Multi Checkout."
            )
            return redirect("cart")

        if general_entries:
            messages.error(
                request,
                "Batch Specific coupons cannot be combined with General coupons."
            )
            return redirect("cart")

        # IMPORTANT:
        # marketplace_visible is NOT checked here.
        #
        # A Batch Specific coupon can be hidden from the
        # marketplace but still be applied manually using
        # its coupon code.
        #
        # The actual coupon eligibility is checked below.

        result = calculate_batch_coupon_for_cart(
            coupon,
            cart_items,
            student=request.user,
        )

        if not result["eligible"]:
            messages.error(
                request,
                result["reason"]
            )
            return redirect("cart")

        selected_batch = result.get("batch")

        if selected_batch is None:
            messages.error(
                request,
                "This coupon is not connected to a cart batch."
            )
            return redirect("cart")

        # ----------------------------------------------------
        # Exactly one Batch Specific coupon per batch
        # ----------------------------------------------------
        if any(
            entry.batch_id == selected_batch.pk
            for entry in batch_entries
        ):
            messages.error(
                request,
                f"Only one Batch Specific coupon can be applied to "
                f"{selected_batch.batch_name} at a time."
            )
            return redirect("cart")

        CartCoupon.objects.create(
            cart=cart,
            coupon=coupon,
            batch=selected_batch,
        )

    # ========================================================
    # INVALID COUPON TYPE
    # ========================================================
    else:
        messages.error(
            request,
            "Invalid coupon type."
        )
        return redirect("cart")

    # ========================================================
    # SUCCESS
    # ========================================================
    messages.success(
        request,
        f"Coupon {coupon.code} applied successfully."
    )

    return redirect("cart")

# ============================================================
# REMOVE COUPON
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def remove_coupon_view(request, coupon_id):

    if not is_student_user(request.user):

        messages.error(
            request,
            "Student access required."
        )

        return redirect("signin")

    if request.method != "POST":

        messages.error(
            request,
            "Invalid coupon request."
        )

        return redirect("cart")

    try:

        cart = Cart.objects.get(
            student=request.user
        )

    except Cart.DoesNotExist:

        messages.info(
            request,
            "Your cart is empty."
        )

        return redirect("cart")

    cart_coupon = (
        CartCoupon.objects
        .filter(
            cart=cart,
            coupon_id=coupon_id,
        )
        .select_related("coupon")
        .first()
    )

    if not cart_coupon:

        messages.warning(
            request,
            "This coupon is not applied."
        )

        return redirect("cart")

    code = cart_coupon.coupon.code

    cart_coupon.delete()

    messages.success(
        request,
        f"Coupon {code} removed successfully."
    )

    return redirect("cart")

# ============================================================
# MY LEARNING
# ============================================================


@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def my_learning_view(request):

    # ========================================================
    # STUDENT ACCESS VALIDATION
    # ========================================================

    if not is_student_user(request.user):
        messages.error(
            request,
            "Admin login is not allowed here. Please use the admin login area."
        )
        return redirect("signin")

    # ========================================================
    # FETCH ACTIVE PURCHASED BATCHES
    # ========================================================

    purchased_batches = list(
        StudentBatchPurchase.objects.filter(
            student=request.user,
            status=StudentBatchPurchase.Status.ACTIVE,
        )
        .select_related(
            "batch",
            "order",
            "order_item",
        )
        .order_by("-purchased_at")
    )

    # ========================================================
    # GET PURCHASED BATCH IDS
    # ========================================================

    batch_ids = {
        purchase.batch_id
        for purchase in purchased_batches
    }

    # ========================================================
    # ACTIVE TEACHER-BATCH ASSIGNMENTS
    # ========================================================

    active_batch_assignments = TeacherBatch.objects.filter(
        batch_id__in=batch_ids,
        is_active=True,
        teacher__is_blocked=False,
        teacher__user__is_active=True,
    ).values_list(
        "batch_id",
        "teacher_id",
    )

    valid_batch_teacher_pairs = set(
        active_batch_assignments
    )

    # ========================================================
    # ACTIVE TEACHER-SUBJECT ASSIGNMENTS
    # ========================================================

    subject_assignments = (
        TeacherSubject.objects.filter(
            batch_id__in=batch_ids,
            is_active=True,
            teacher__is_blocked=False,
            teacher__user__is_active=True,
        )
        .select_related("teacher")
        .order_by("teacher__full_name")
    )

    # ========================================================
    # GROUP UNIQUE TEACHERS BY BATCH
    # ========================================================

    teachers_by_batch = {}

    for assignment in subject_assignments:

        assignment_key = (
            assignment.batch_id,
            assignment.teacher_id,
        )

        # Teacher must also have an active batch assignment.
        if assignment_key not in valid_batch_teacher_pairs:
            continue

        batch_teachers = teachers_by_batch.setdefault(
            assignment.batch_id,
            {},
        )

        # Prevent duplicate teachers appearing in the same batch.
        batch_teachers[assignment.teacher_id] = (
            assignment.teacher
        )

    # ========================================================
    # ATTACH TEACHER DATA TO PURCHASED BATCHES
    # ========================================================

    for purchase in purchased_batches:

        assigned_teachers = teachers_by_batch.get(
            purchase.batch_id,
            {},
        )

        purchase.batch_teachers = list(
            assigned_teachers.values()
        )

        purchase.batch_teacher_count = len(
            purchase.batch_teachers
        )

    # ========================================================
    # RENDER MY LEARNING
    # ========================================================

    return render(
        request,
        "students/my_learning/my_learning.html",
        {
            "purchased_batches": purchased_batches,
        },
    )


# ============================================================
# MY LEARNING - BATCH SUBJECTS
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def my_learning_batch_view(request, batch_id):

    if not is_student_user(request.user):
        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )
        return redirect('signin')

    # A student can open this page only when the batch has an active purchase.
    purchase = get_object_or_404(
        StudentBatchPurchase.objects.select_related('batch'),
        student=request.user,
        batch_id=batch_id,
        status=StudentBatchPurchase.Status.ACTIVE,
    )

    batch = purchase.batch

    # Only published subjects belonging to this purchased batch.
    subjects = list(
        Subject.objects.filter(
            batch=batch,
            subject_status='published',
        ).order_by('subject_name')
    )

    subject_ids = [subject.pk for subject in subjects]

    # First collect teachers who still have an active assignment to this batch.
    active_batch_teacher_pairs = set(
        TeacherBatch.objects.filter(
            batch=batch,
            is_active=True,
            teacher__is_blocked=False,
            teacher__user__is_active=True,
        ).values_list(
            'batch_id',
            'teacher_id',
        )
    )

    # Then fetch active teacher-to-subject assignments for these subjects.
    subject_assignments = (
        TeacherSubject.objects.filter(
            batch=batch,
            subject_id__in=subject_ids,
            is_active=True,
            teacher__is_blocked=False,
            teacher__user__is_active=True,
        )
        .select_related('teacher', 'teacher__user', 'subject')
        .order_by('teacher__full_name', 'teacher_id')
    )

    # Group unique, valid teachers by subject.
    teachers_by_subject = {}

    for assignment in subject_assignments:

        # The teacher must also have an active TeacherBatch assignment
        # for this exact batch.
        if (
            assignment.batch_id,
            assignment.teacher_id,
        ) not in active_batch_teacher_pairs:
            continue

        subject_teachers = teachers_by_subject.setdefault(
            assignment.subject_id,
            {},
        )

        # A teacher assigned through multiple records must appear once.
        subject_teachers[assignment.teacher_id] = assignment.teacher

    # Attach display values to each subject for the template.
    for subject in subjects:

        assigned_teachers = teachers_by_subject.get(
            subject.pk,
            {},
        )

        subject.card_teachers = list(
            assigned_teachers.values()
        )

        subject.card_teacher_count = len(
            subject.card_teachers
        )

        # The card displays at most three overlapping avatars.
        subject.card_teacher_preview = subject.card_teachers[:3]

        # The +N avatar is shown only when there are more than three.
        subject.card_teacher_extra_count = max(
            subject.card_teacher_count - 3,
            0,
        )

    return render(
        request,
        'students/my_learning/batch_subjects.html',
        {
            'batch': batch,
            'subjects': subjects,
        },
    )

# ============================================================
# MY LEARNING - SUBJECT CHAPTERS
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def my_learning_subject_view(request, batch_id, subject_id):

    if not is_student_user(request.user):
        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )
        return redirect('signin')

    purchase = get_object_or_404(
        StudentBatchPurchase.objects.select_related(
            'batch'
        ),
        student=request.user,
        batch_id=batch_id,
        status=StudentBatchPurchase.Status.ACTIVE,
    )

    batch = purchase.batch

    subject = get_object_or_404(
        Subject,
        id=subject_id,
        batch=batch,
        subject_status='published',
    )

    chapters = (
        CourseChapter.objects
        .filter(
            batch=batch,
            subject=subject,
            status='published',
        )
        .order_by(
            'chapter_order',
            'pk',
        )
    )

    return render(
        request,
        'students/my_learning/subject_chapters.html',
        {
            'batch': batch,
            'subject': subject,
            'chapters': chapters,
        },
    )

# ============================================================
# MY LEARNING - CHAPTER CONTENT
# ============================================================


# ============================================================
# MY LEARNING - CHAPTER CONTENT
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def my_learning_chapter_view(request, batch_id, subject_id, chapter_id):
    if not is_student_user(request.user):
        messages.error(
            request,
            "Admin login is not allowed here. Please use the admin login area.",
        )
        return redirect("signin")

    # VERIFY ACTIVE PURCHASE
    purchase = get_object_or_404(
        StudentBatchPurchase.objects.select_related("batch"),
        student=request.user,
        batch_id=batch_id,
        status=StudentBatchPurchase.Status.ACTIVE,
    )
    batch = purchase.batch

    # VERIFY SUBJECT AND CHAPTER ACCESS
    subject = get_object_or_404(
        Subject,
        pk=subject_id,
        batch=batch,
        subject_status="published",
    )
    chapter = get_object_or_404(
        CourseChapter,
        pk=chapter_id,
        batch=batch,
        subject=subject,
        status="published",
    )

    # LOAD PUBLISHED CHAPTER CONTENT
    videos = ChapterVideo.objects.filter(
        chapter=chapter,
        status="published",
    ).order_by("video_order", "pk")

    pdfs = ChapterPDF.objects.filter(
        chapter=chapter,
        status="published",
    ).order_by("pdf_order", "pk")

    quizzes = list(
        ChapterQuiz.objects.filter(
            chapter=chapter,
            status="published",
        ).order_by("quiz_order", "pk")
    )

    # CLOSE EXPIRED ATTEMPTS. Timed-out attempts consume the limit.
    now = timezone.now()
    QuizAttempt.objects.filter(
        student=request.user,
        quiz__chapter=chapter,
        status=QuizAttempt.Status.IN_PROGRESS,
        expires_at__lte=now,
    ).update(
        status=QuizAttempt.Status.TIMED_OUT,
        submitted_at=now,
        score=0,
    )

    # FIND ACTIVE ATTEMPTS SO STUDENTS CAN RESUME THEIR TIMER
    active_quiz_attempts = {}
    active_attempts = (
        QuizAttempt.objects.filter(
            student=request.user,
            quiz__chapter=chapter,
            status=QuizAttempt.Status.IN_PROGRESS,
            expires_at__gt=now,
        )
        .select_related("quiz")
        .order_by("-started_at", "-pk")
    )

    for active_attempt in active_attempts:
        if active_attempt.quiz_id not in active_quiz_attempts:
            active_quiz_attempts[active_attempt.quiz_id] = active_attempt

    # SUBMITTED AND TIMED_OUT ATTEMPTS BOTH CONSUME AN ATTEMPT
    quiz_cards = []
    for quiz in quizzes:
        attempts_used = QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz,
            status__in=[
                QuizAttempt.Status.SUBMITTED,
                QuizAttempt.Status.TIMED_OUT,
            ],
        ).count()

        quiz_cards.append(
            {
                "quiz": quiz,
                "active_attempt": active_quiz_attempts.get(quiz.pk),
                "attempts_used": attempts_used,
            }
        )

    # DEFAULT QUIZ DISPLAY STATE
    quiz_attempt = None
    quiz_answers = []
    quiz_mode = "list"
    remaining_seconds = 0
    quiz_percentage = 0

    # OPEN A SPECIFIC ATTEMPT OR RESULT
    attempt_id = request.GET.get("attempt", "").strip()
    if attempt_id:
        quiz_attempt = get_object_or_404(
            QuizAttempt.objects.select_related("quiz", "quiz__chapter"),
            pk=attempt_id,
            student=request.user,
            quiz__chapter=chapter,
        )

        # CLOSE THIS ATTEMPT IF ITS TIMER HAS EXPIRED
        if (
            quiz_attempt.status == QuizAttempt.Status.IN_PROGRESS
            and timezone.now() >= quiz_attempt.expires_at
        ):
            now = timezone.now()
            quiz_attempt.status = QuizAttempt.Status.TIMED_OUT
            quiz_attempt.submitted_at = now
            quiz_attempt.score = 0
            quiz_attempt.save(
                update_fields=[
                    "status",
                    "submitted_at",
                    "score",
                    "updated_at",
                ]
            )

            # Keep the displayed attempt count consistent immediately.
            for card in quiz_cards:
                if card["quiz"].pk == quiz_attempt.quiz_id:
                    card["attempts_used"] += 1
                    break

        quiz_answers = list(quiz_attempt.answers.all().order_by("pk"))

        if quiz_attempt.status == QuizAttempt.Status.IN_PROGRESS:
            quiz_mode = "take"
            remaining_seconds = max(
                0,
                int(
                    (
                        quiz_attempt.expires_at - timezone.now()
                    ).total_seconds()
                ),
            )
        else:
            quiz_mode = "result"
            if quiz_attempt.maximum_marks:
                quiz_percentage = round(
                    float(quiz_attempt.score or 0)
                    / float(quiz_attempt.maximum_marks)
                    * 100,
                    2,
                )

    # --------------------------------------------------------
    # CHAPTER LIVE CLASSES
    # --------------------------------------------------------
    # The chapter view has already verified that this student owns an
    # ACTIVE purchase for this batch and that the subject/chapter belong
    # to that batch. Reuse that same verified scope for LiveClass records.
    chapter_live_classes = list(
        LiveClass.objects.filter(
            batch=batch,
            subject=subject,
            chapter=chapter,
        ).select_related(
            "batch",
            "subject",
            "chapter",
            "teacher",
        )
    )

    chapter_live_class_counts = {
        "total": len(chapter_live_classes),
        "upcoming": 0,
        "live": 0,
        "completed": 0,
        "cancelled": 0,
        "no_show": 0,
    }

    now = timezone.now()

    for live_class in chapter_live_classes:
        if live_class.status == "cancelled":
            display_status = "cancelled"
        elif live_class.status == "no_show":
            display_status = "no_show"
        elif live_class.status == "completed" or live_class.actual_end_at:
            display_status = "completed"
        elif (
            live_class.status == "confirmed"
            and live_class.actual_start_at
            and live_class.actual_start_at <= now
            and not live_class.actual_end_at
        ):
            display_status = "live"
        else:
            # A scheduled time passing does not start a class. Only the
            # Admin/Teacher start action sets actual_start_at.
            display_status = "upcoming"

        live_class.display_status = display_status
        live_class.local_start = timezone.localtime(live_class.start_at)
        live_class.local_end = timezone.localtime(live_class.end_at)
        live_class.duration_minutes = max(
            1,
            int((live_class.end_at - live_class.start_at).total_seconds() // 60),
        )
        if live_class.duration_minutes >= 60:
            hours, minutes = divmod(live_class.duration_minutes, 60)
            live_class.duration_display = (
                f"{hours} hr" if not minutes else f"{hours} hr {minutes} min"
            )
        else:
            live_class.duration_display = f"{live_class.duration_minutes} min"

        # The current ZIP contains provider identifiers but no student
        # meeting/join endpoint or provider URL builder. Do not fabricate
        # a meeting destination from provider_room_id.
        live_class.student_join_url = ""
        live_class.student_can_join = False

        chapter_live_class_counts[display_status] += 1

    # Live first, then nearest upcoming, then most recently completed,
    # followed by cancelled/no-show records. This keeps useful access at top.
    status_order = {
        "live": 0,
        "upcoming": 1,
        "completed": 2,
        "cancelled": 3,
        "no_show": 4,
    }

    chapter_live_classes.sort(
        key=lambda item: (
            status_order[item.display_status],
            item.start_at if item.display_status in {"live", "upcoming"}
            else -item.start_at.timestamp(),
            item.pk,
        )
    )

    return render(
        request,
        "students/my_learning/chapter_learning.html",
        {
            "batch": batch,
            "subject": subject,
            "chapter": chapter,
            "videos": videos,
            "pdfs": pdfs,
            "quizzes": quizzes,
            "quiz_cards": quiz_cards,
            "active_quiz_attempts": active_quiz_attempts,
            "quiz_attempt": quiz_attempt,
            "quiz_answers": quiz_answers,
            "quiz_mode": quiz_mode,
            "remaining_seconds": remaining_seconds,
            "quiz_percentage": quiz_percentage,
            "chapter_live_classes": chapter_live_classes,
            "chapter_live_class_counts": chapter_live_class_counts,
        },
    )


# ============================================================
# STUDENT ORDER HISTORY
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def order_history_view(request):

    # ========================================================
    # STUDENT ACCESS
    # ========================================================

    if not is_student_user(request.user):

        messages.error(
            request,
            "Admin login is not allowed here. Please use the admin login area.",
        )

        return redirect("signin")

    # ========================================================
    # QUERY PARAMETERS
    # ========================================================

    search_query = request.GET.get(
        "search",
        "",
    ).strip()

    current_status = request.GET.get(
        "status",
        "all",
    ).strip().lower()

    date_range = request.GET.get(
        "date_range",
        "all",
    ).strip().lower()

    start_date_value = request.GET.get(
        "start_date",
        "",
    ).strip()

    end_date_value = request.GET.get(
        "end_date",
        "",
    ).strip()

    # ========================================================
    # VALID STATUS FILTERS
    # ========================================================

    allowed_statuses = {
    "all",
    "paid",
    "payment_failed",
    "cancelled",
    "partially_refunded",
    "refunded",
    }

    if current_status not in allowed_statuses:
        current_status = "all"

    # ========================================================
    # VALID DATE FILTERS
    # ========================================================

    allowed_date_ranges = {
        "all",
        "7",
        "30",
        "3m",
        "6m",
        "year",
        "custom",
    }

    if date_range not in allowed_date_ranges:
        date_range = "all"

    # ========================================================
    # CURRENT TIME
    # ========================================================

    now = timezone.now()

    # ========================================================
    # DATE FILTER STATE
    # ========================================================

    start_datetime = None
    end_datetime = None

    current_date_range = "All Time"

    # ========================================================
    # PRESET DATE FILTERS
    # ========================================================

    if date_range == "7":

        start_datetime = now - timedelta(days=7)

        current_date_range = "Last 7 Days"

    elif date_range == "30":

        start_datetime = now - timedelta(days=30)

        current_date_range = "Last 30 Days"

    elif date_range == "3m":

        start_datetime = now - timedelta(days=90)

        current_date_range = "Last 3 Months"

    elif date_range == "6m":

        start_datetime = now - timedelta(days=180)

        current_date_range = "Last 6 Months"

    elif date_range == "year":

        local_now = timezone.localtime(now)

        year_start = datetime(
            local_now.year,
            1,
            1,
        )

        start_datetime = timezone.make_aware(
            year_start,
            timezone.get_current_timezone(),
        )

        current_date_range = "This Year"

    # ========================================================
    # CUSTOM DATE RANGE
    # ========================================================

    elif date_range == "custom":

        try:

            start_date = datetime.strptime(
                start_date_value,
                "%Y-%m-%d",
            ).date()

            end_date = datetime.strptime(
                end_date_value,
                "%Y-%m-%d",
            ).date()

            if start_date > end_date:

                date_range = "all"
                start_date_value = ""
                end_date_value = ""
                current_date_range = "All Time"

            else:

                start_datetime = timezone.make_aware(
                    datetime.combine(
                        start_date,
                        datetime.min.time(),
                    ),
                    timezone.get_current_timezone(),
                )

                # End date is inclusive.
                # We use the next midnight as an exclusive boundary.
                end_datetime = timezone.make_aware(
                    datetime.combine(
                        end_date + timedelta(days=1),
                        datetime.min.time(),
                    ),
                    timezone.get_current_timezone(),
                )

                current_date_range = (
                    f"{start_date.strftime('%d %b %Y')}"
                    f" – "
                    f"{end_date.strftime('%d %b %Y')}"
                )

        except (
            TypeError,
            ValueError,
        ):

            date_range = "all"
            start_date_value = ""
            end_date_value = ""
            current_date_range = "All Time"

    # ========================================================
    # BASE ORDER QUERY
    #
    # IMPORTANT:
    # Only the currently logged-in student's orders.
    # ========================================================

    orders = (
        Order.objects
        .filter(
            user=request.user,
        )
        .prefetch_related(
            "items__batch",
        )
        .select_related(
            "payment",
            "invoice",
        )
        .order_by(
            "-created_at",
        )
    )

    # ========================================================
    # STATUS FILTER
    # ========================================================

    if current_status != "all":

        orders = orders.filter(
            status=current_status,
        )

    # ========================================================
    # DATE FILTER
    # ========================================================

    if start_datetime is not None:

        orders = orders.filter(
            created_at__gte=start_datetime,
        )

    if end_datetime is not None:

        orders = orders.filter(
            created_at__lt=end_datetime,
        )

    # ========================================================
    # SEARCH
    #
    # Search:
    #   - Order number
    #   - Batch name
    #   - Invoice number
    # ========================================================

    if search_query:

        orders = orders.filter(
            Q(
                order_number__icontains=search_query,
            )
            |
            Q(
                items__batch_name__icontains=search_query,
            )
            |
            Q(
                invoice__invoice_number__icontains=search_query,
            )
        ).distinct()

    # ========================================================
    # PAGINATION
    # ========================================================

    from django.core.paginator import Paginator

    paginator = Paginator(
        orders,
        8,
    )

    page_number = request.GET.get(
        "page",
        1,
    )

    orders_page = paginator.get_page(
        page_number,
    )

    # ========================================================
    # STATUS COUNTS
    #
    # Counts respect the selected DATE RANGE.
    #
    # They intentionally do not depend on the currently
    # selected status or search text.
    # ========================================================

    all_orders = Order.objects.filter(
        user=request.user,
    )

    if start_datetime is not None:

        all_orders = all_orders.filter(
            created_at__gte=start_datetime,
        )

    if end_datetime is not None:

        all_orders = all_orders.filter(
            created_at__lt=end_datetime,
        )

    status_counts = {
    "all": all_orders.count(),

    "paid": all_orders.filter(
        status=Order.Status.PAID,
    ).count(),

    "payment_failed": all_orders.filter(
        status=Order.Status.PAYMENT_FAILED,
    ).count(),

    "cancelled": all_orders.filter(
        status=Order.Status.CANCELLED,
    ).count(),

    "partially_refunded": all_orders.filter(
        status=Order.Status.PARTIALLY_REFUNDED,
    ).count(),

    "refunded": all_orders.filter(
        status=Order.Status.REFUNDED,
    ).count(),
    }

    # ========================================================
    # RENDER ORDER HISTORY
    # ========================================================

    return render(
        request,
        "students/order_history/order_history.html",
        {
            "orders": orders_page,

            # Search
            "search_query": search_query,

            # Status
            "current_status": current_status,

            # Date filtering
            "date_range": date_range,
            "current_date_range": current_date_range,
            "start_date": start_date_value,
            "end_date": end_date_value,

            # Counts
            "status_counts": status_counts,
        },
    )

# ============================================================
# STUDENT ORDER DETAILS
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def order_details_view(request, order_number):

    # ========================================================
    # STUDENT ACCESS
    # ========================================================

    if not is_student_user(request.user):

        messages.error(
            request,
            "Admin login is not allowed here. Please use the admin login area.",
        )

        return redirect("signin")

    # ========================================================
    # ORDER
    #
    # IMPORTANT:
    # The order must belong to the currently logged-in student.
    # ========================================================

    order = get_object_or_404(
        Order.objects.select_related(
            "payment",
            "invoice",
        ),
        order_number=order_number,
        user=request.user,
    )

    # ========================================================
    # ORDER ITEMS
    #
    # These are historical OrderItem records.
    # They represent what was stored when the order was created.
    # ========================================================

    order_items = list(
        order.items
        .select_related("batch")
        .order_by("id")
    )

    # ========================================================
    # HISTORICAL COUPON SNAPSHOTS
    #
    # IMPORTANT:
    # Never read the current Coupon/CartCoupon state for an
    # already-created order.
    #
    # OrderCoupon contains the historical coupon information
    # captured at checkout.
    # ========================================================

    order_coupons = list(
        OrderCoupon.objects
        .filter(order=order)
        .select_related("applied_batch")
        .order_by("id")
    )

    # ========================================================
    # PAYMENT
    # ========================================================

    payment = getattr(
        order,
        "payment",
        None,
    )

    # ========================================================
    # INVOICE
    # ========================================================

    invoice = getattr(
        order,
        "invoice",
        None,
    )

    # ========================================================
    # REFUNDS
    #
    # Only refunds belonging to this order are loaded.
    # ========================================================

    refunds = list(
        Refund.objects
        .filter(
            order=order,
        )
        .prefetch_related(
            "items__order_item",
        )
        .order_by(
            "-requested_at",
        )
    )

    # ========================================================
    # REFUND STATUS GROUPS
    # ========================================================

    completed_refunds = [
        refund
        for refund in refunds
        if refund.status == Refund.Status.COMPLETED
    ]

    requested_refunds = [
        refund
        for refund in refunds
        if refund.status == Refund.Status.REQUESTED
    ]

    processing_refunds = [
        refund
        for refund in refunds
        if refund.status == Refund.Status.PROCESSING
    ]

    rejected_refunds = [
        refund
        for refund in refunds
        if refund.status == Refund.Status.REJECTED
    ]

    failed_refunds = [
        refund
        for refund in refunds
        if refund.status == Refund.Status.FAILED
    ]

    # ========================================================
    # REFUND STATE FLAGS
    # ========================================================

    has_requested_refund = bool(
        requested_refunds
    )

    has_processing_refund = bool(
        processing_refunds
    )

    has_completed_refund = bool(
        completed_refunds
    )

    has_rejected_refund = bool(
        rejected_refunds
    )

    has_failed_refund = bool(
        failed_refunds
    )

    # ========================================================
    # EDITABLE REFUND
    #
    # Only REQUESTED refunds can be edited.
    #
    # PROCESSING / COMPLETED / REJECTED / FAILED refunds are
    # locked.
    # ========================================================

    editable_refund = next(
        (
            refund
            for refund in requested_refunds
        ),
        None,
    )

    refund_edit_allowed = (
        editable_refund is not None
    )

    # ========================================================
    # REFUNDED AMOUNT
    #
    # Always use the historical refunded amount.
    #
    # Do NOT recalculate this using the current batch price.
    # ========================================================

    refunded_amount = sum(
        (
            refund.refunded_amount or 0
            for refund in completed_refunds
        ),
        0,
    )

    # ========================================================
    # NET PAID
    # ========================================================

    net_paid = max(
        (order.final_amount or 0)
        - refunded_amount,
        0,
    )

    # ========================================================
    # REFUND WINDOW
    #
    # Refund is available for exactly 7 days from the
    # original order creation time.
    # ========================================================

    refund_deadline = (
        order.created_at
        + timedelta(days=7)
    )

    now = timezone.now()

    refund_window_open = (
        now <= refund_deadline
    )

    # ========================================================
    # COUPON TYPES
    #
    # Keep the raw historical type available to the template.
    # ========================================================

    coupon_types = [
        coupon.coupon_type
        for coupon in order_coupons
        if coupon.coupon_type
    ]

    # ========================================================
    # FULL ORDER REFUND CHECK
    #
    # A multi-checkout coupon means the order must be treated
    # as a full-order refund.
    #
    # Single-batch orders are also full-refund only.
    # ========================================================

    has_multi_checkout_coupon = any(
        coupon.coupon_type == "multi_checkout"
        for coupon in order_coupons
    )

    # ========================================================
    # CURRENT REFUNDABLE ORDER ITEMS
    #
    # IMPORTANT:
    # This is calculated from the refund helper.
    #
    # The helper excludes items that are already reserved by
    # REQUESTED / PROCESSING / COMPLETED refunds.
    #
    # Therefore:
    #
    # PAID
    #     -> all refundable batches are available
    #
    # PARTIALLY_REFUNDED
    #     -> only the remaining refundable batches are available
    #
    # REFUNDED
    #     -> no refundable batches remain
    # ========================================================

    refundable_order_items = []

    if (
        order.status in {
            Order.Status.PAID,
            Order.Status.PARTIALLY_REFUNDED,
        }
        and refund_window_open
    ):
        refundable_order_items = list(
            get_refundable_order_items(order)
        )

    refundable_order_item_ids = {
        item.id
        for item in refundable_order_items
    }

    refundable_item_count = len(
        refundable_order_items
    )

    # ========================================================
    # PARTIAL REFUND POSSIBILITY
    #
    # Rules:
    #
    # 1. Multi-checkout coupon
    #       -> FULL REFUND ONLY
    #
    # 2. One refundable batch
    #       -> FULL REFUND ONLY
    #
    # 3. More than one refundable batch
    #       -> PARTIAL REFUND AVAILABLE
    #
    # IMPORTANT:
    # The actual validation is still done server-side by the
    # refund helper.
    # ========================================================

    partial_refund_allowed = (
        not has_multi_checkout_coupon
        and refundable_item_count > 1
    )

    # ========================================================
    # REFUND ELIGIBILITY
    #
    # Refund is available when:
    #
    # - order is PAID or PARTIALLY_REFUNDED
    # - refund window is still open
    # - there is no currently REQUESTED refund
    # - there is no currently PROCESSING refund
    # - at least one refundable batch remains
    #
    # IMPORTANT:
    # We intentionally do NOT block PARTIALLY_REFUNDED orders
    # just because a previous refund was COMPLETED.
    #
    # This allows the student to refund remaining batches.
    # ========================================================

    refund_eligible = (
        order.status in {
            Order.Status.PAID,
            Order.Status.PARTIALLY_REFUNDED,
        }
        and refund_window_open
        and not has_requested_refund
        and not has_processing_refund
        and bool(refundable_order_items)
    )

    # ========================================================
    # ORDER STATUS LABEL
    #
    # Customer-facing order status.
    #
    # Internal PENDING / PAYMENT_PROCESSING are retained in
    # the model but are not intended as normal customer-facing
    # refund states.
    # ========================================================

    status_labels = {
        Order.Status.PENDING: "PENDING",
        Order.Status.PAYMENT_PROCESSING: "PAYMENT PROCESSING",
        Order.Status.PAID: "COMPLETED",
        Order.Status.PAYMENT_FAILED: "PAYMENT FAILED",
        Order.Status.CANCELLED: "CANCELLED",
        Order.Status.PARTIALLY_REFUNDED: "PARTIALLY REFUNDED",
        Order.Status.REFUNDED: "REFUNDED",
    }

    status_label = status_labels.get(
        order.status,
        str(order.status).replace(
            "_",
            " ",
        ).upper(),
    )

    # ========================================================
    # ORDER ITEM + PURCHASE INFORMATION
    #
    # Attach the corresponding StudentBatchPurchase to each
    # OrderItem.
    #
    # This allows the template to display whether the student's
    # access is currently ACTIVE or REFUNDED.
    # ========================================================

    purchases = {
        purchase.order_item_id: purchase
        for purchase in (
            StudentBatchPurchase.objects
            .filter(
                order=order,
                student=request.user,
            )
        )
    }

    order_item_rows = []

    for item in order_items:

        order_item_rows.append(
            {
                "item": item,
                "purchase": purchases.get(
                    item.id
                ),
            }
        )

    # ========================================================
    # COUPON SUMMARY
    #
    # These values come from the historical OrderCoupon
    # snapshots.
    # ========================================================

    coupon_discount = sum(
        (
            coupon.discount_amount or 0
            for coupon in order_coupons
        ),
        0,
    )

    coupon_count = len(
        order_coupons
    )

    # ========================================================
    # RENDER ORDER DETAILS
    # ========================================================

    return render(
        request,
        "students/order_details/order_details.html",
        {
            # ------------------------------------------------
            # ORDER
            # ------------------------------------------------

            "order": order,

            # ------------------------------------------------
            # ORDER ITEMS
            # ------------------------------------------------

            "order_items": order_item_rows,

            # ------------------------------------------------
            # PAYMENT
            # ------------------------------------------------

            "payment": payment,

            # ------------------------------------------------
            # INVOICE
            # ------------------------------------------------

            "invoice": invoice,

            # ------------------------------------------------
            # HISTORICAL COUPONS
            # ------------------------------------------------

            "order_coupons": order_coupons,
            "coupon_discount": coupon_discount,
            "coupon_count": coupon_count,
            "coupon_types": coupon_types,

            # ------------------------------------------------
            # REFUND DATA
            # ------------------------------------------------

            "refunds": refunds,
            "completed_refunds": completed_refunds,
            "refunded_amount": refunded_amount,
            "net_paid": net_paid,

            # ------------------------------------------------
            # REFUND STATUS GROUPS
            # ------------------------------------------------

            "requested_refunds": requested_refunds,
            "processing_refunds": processing_refunds,
            "rejected_refunds": rejected_refunds,
            "failed_refunds": failed_refunds,

            # ------------------------------------------------
            # REFUND STATE FLAGS
            # ------------------------------------------------

            "has_requested_refund": (
                has_requested_refund
            ),
            "has_processing_refund": (
                has_processing_refund
            ),
            "has_completed_refund": (
                has_completed_refund
            ),
            "has_rejected_refund": (
                has_rejected_refund
            ),
            "has_failed_refund": (
                has_failed_refund
            ),

            # ------------------------------------------------
            # EDITABLE REFUND
            # ------------------------------------------------

            "editable_refund": editable_refund,
            "refund_edit_allowed": (
                refund_edit_allowed
            ),

            # ------------------------------------------------
            # REFUND WINDOW
            # ------------------------------------------------

            "refund_deadline": refund_deadline,
            "refund_window_open": (
                refund_window_open
            ),
            "refund_eligible": refund_eligible,

            # ------------------------------------------------
            # REFUNDABLE ITEMS
            # ------------------------------------------------

            "refundable_order_items": (
                refundable_order_items
            ),
            "refundable_order_item_ids": (
                refundable_order_item_ids
            ),
            "refundable_item_count": (
                refundable_item_count
            ),

            # ------------------------------------------------
            # REFUND RULES
            # ------------------------------------------------

            "has_multi_checkout_coupon": (
                has_multi_checkout_coupon
            ),
            "partial_refund_allowed": (
                partial_refund_allowed
            ),

            # ------------------------------------------------
            # ORDER STATUS
            # ------------------------------------------------

            "status_label": status_label,
        },
    )


# ============================================================
# STUDENT QUIZ - START ATTEMPT
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def start_quiz_view(request, batch_id, subject_id, chapter_id, quiz_id):
    if not is_student_user(request.user):
        messages.error(request, "Student access required.")
        return redirect("signin")

    chapter_url = reverse(
        "my_learning_chapter",
        kwargs={
            "batch_id": batch_id,
            "subject_id": subject_id,
            "chapter_id": chapter_id,
        },
    )

    if request.method != "POST":
        return redirect(f"{chapter_url}?tab=quizzes")

    with transaction.atomic():
        purchase = get_object_or_404(
            StudentBatchPurchase.objects.select_for_update(),
            student=request.user,
            batch_id=batch_id,
            status=StudentBatchPurchase.Status.ACTIVE,
        )

        quiz = get_object_or_404(
            ChapterQuiz.objects.select_for_update().select_related(
                "chapter",
                "chapter__batch",
                "chapter__subject",
            ),
            pk=quiz_id,
            chapter_id=chapter_id,
            chapter__batch_id=purchase.batch_id,
            chapter__subject_id=subject_id,
            chapter__status="published",
            chapter__subject__subject_status="published",
            status="published",
        )

        now = timezone.now()

        # CLOSE EXPIRED ATTEMPTS FIRST
        QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz,
            status=QuizAttempt.Status.IN_PROGRESS,
            expires_at__lte=now,
        ).update(
            status=QuizAttempt.Status.TIMED_OUT,
            submitted_at=now,
            score=0,
        )

        # RESUME AN ACTIVE ATTEMPT WITHOUT RESETTING ITS TIMER
        active_attempt = (
            QuizAttempt.objects.filter(
                student=request.user,
                quiz=quiz,
                status=QuizAttempt.Status.IN_PROGRESS,
                expires_at__gt=now,
            )
            .order_by("-started_at", "-pk")
            .first()
        )
        if active_attempt:
            return redirect(
                f"{chapter_url}?attempt={active_attempt.pk}&tab=quizzes"
            )

        # VALIDATE QUIZ SETTINGS
        if quiz.maximum_attempts < 1 or quiz.answering_time < 1:
            messages.error(
                request,
                "This quiz has invalid attempt or timing settings.",
            )
            return redirect(f"{chapter_url}?tab=quizzes")

        # SUBMITTED AND TIMED_OUT ATTEMPTS BOTH CONSUME THE LIMIT
        attempts_used = QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz,
            status__in=[
                QuizAttempt.Status.SUBMITTED,
                QuizAttempt.Status.TIMED_OUT,
            ],
        ).count()

        if attempts_used >= quiz.maximum_attempts:
            messages.error(
                request,
                "You have used all available attempts for this quiz.",
            )
            return redirect(f"{chapter_url}?tab=quizzes")

        # LOAD AND VALIDATE QUESTIONS
        questions = list(
            QuizQuestion.objects.filter(quiz=quiz)
            .prefetch_related("options")
            .order_by("pk")
        )

        if not questions:
            messages.error(
                request,
                "This quiz does not have any questions yet.",
            )
            return redirect(f"{chapter_url}?tab=quizzes")

        question_data = []
        for question in questions:
            options = list(question.options.all())
            correct_options = [
                option for option in options if option.is_correct
            ]

            if len(options) != 4 or len(correct_options) != 1:
                messages.error(
                    request,
                    "This quiz contains an incomplete question. "
                    "Please contact your teacher.",
                )
                return redirect(f"{chapter_url}?tab=quizzes")

            question_data.append(
                {
                    "question": question,
                    "options": options,
                    "correct_option": correct_options[0],
                }
            )

        # INTERNAL ATTEMPT RECORD NUMBER; NOT THE ATTEMPTS-USED COUNT
        previous_attempt_records = QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz,
        ).count()

        # CREATE THE NEW ATTEMPT
        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            quiz_title_snapshot=quiz.quiz_name,
            attempt_number=previous_attempt_records + 1,
            answering_time_minutes_snapshot=quiz.answering_time,
            maximum_attempts_snapshot=quiz.maximum_attempts,
            marks_per_question_snapshot=quiz.marks_per_question,
            maximum_marks=len(question_data) * quiz.marks_per_question,
            expires_at=now + timedelta(minutes=quiz.answering_time),
        )

        # CREATE QUESTION AND OPTION SNAPSHOTS
        answer_snapshots = []
        for item in question_data:
            question = item["question"]
            options = item["options"]
            correct_option = item["correct_option"]

            answer_snapshots.append(
                QuizAttemptAnswer(
                    attempt=attempt,
                    question=question,
                    question_snapshot_key=str(question.pk),
                    question_text_snapshot=question.question_text,
                    options_snapshot=[
                        {
                            "label": option.option_label,
                            "text": option.option_text,
                        }
                        for option in options
                    ],
                    correct_option_label_snapshot=correct_option.option_label,
                )
            )

        QuizAttemptAnswer.objects.bulk_create(answer_snapshots)

    return redirect(
        f"{chapter_url}?attempt={attempt.pk}&tab=quizzes"
    )


# ============================================================
# STUDENT QUIZ - SAVE INDIVIDUAL ANSWER
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def student_quiz_answer_save_view(request, attempt_id, answer_id):

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Only POST requests are allowed.",
            },
            status=405,
        )

    if not is_student_user(request.user):
        return JsonResponse(
            {
                "success": False,
                "message": "Student access required.",
            },
            status=403,
        )

    selected_label = (
        request.POST.get("selected_option")
        or request.POST.get("selected_option_label")
        or request.POST.get("option_label")
        or ""
    ).strip().upper()

    if not selected_label:
        return JsonResponse(
            {
                "success": False,
                "message": "Please select an answer.",
            },
            status=400,
        )

    with transaction.atomic():

        attempt = (
            QuizAttempt.objects
            .select_for_update()
            .filter(
                pk=attempt_id,
                student=request.user,
            )
            .first()
        )

        if attempt is None:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Quiz attempt not found.",
                },
                status=404,
            )

        if attempt.status != QuizAttempt.Status.IN_PROGRESS:
            return JsonResponse(
                {
                    "success": False,
                    "message": "This quiz attempt is already closed.",
                },
                status=400,
            )

        now = timezone.now()

        if now >= attempt.expires_at:
            return JsonResponse(
                {
                    "success": False,
                    "time_expired": True,
                    "message": "Your quiz time has expired.",
                },
                status=400,
            )

        answer = (
            QuizAttemptAnswer.objects
            .select_for_update()
            .filter(
                pk=answer_id,
                attempt=attempt,
            )
            .first()
        )

        if answer is None:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Question answer record not found.",
                },
                status=404,
            )

        # A previously saved answer cannot be changed.
        if answer.selected_option_label:
            return JsonResponse(
                {
                    "success": True,
                    "locked": True,
                    "selected_option": answer.selected_option_label,
                    "message": "This answer is already saved.",
                }
            )

        selected_option = next(
            (
                option
                for option in (answer.options_snapshot or [])
                if str(option.get("label", "")).strip().upper()
                == selected_label
            ),
            None,
        )

        if selected_option is None:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid answer option.",
                },
                status=400,
            )

        answer.selected_option_label = selected_label
        answer.selected_option_text_snapshot = selected_option.get(
            "text", ""
        )
        answer.answered_at = now

        answer.save(
            update_fields=[
                "selected_option_label",
                "selected_option_text_snapshot",
                "answered_at",
                "updated_at",
            ]
        )

    return JsonResponse(
        {
            "success": True,
            "locked": True,
            "selected_option": selected_label,
            "message": "Answer saved successfully.",
        }
    )


# ============================================================
# STUDENT QUIZ - TAKE AND SUBMIT
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def student_quiz_take_view(request, attempt_id):
    if not is_student_user(request.user):
        messages.error(request, "Student access required.")
        return redirect("signin")

    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "quiz__chapter"),
        pk=attempt_id,
        student=request.user,
    )

    if attempt.quiz is None:
        messages.error(
            request,
            "This quiz is no longer available. Your attempt record has been retained.",
        )
        return redirect("my_learning")

    chapter = attempt.quiz.chapter
    get_object_or_404(
        StudentBatchPurchase,
        student=request.user,
        batch_id=chapter.batch_id,
        status=StudentBatchPurchase.Status.ACTIVE,
    )

    chapter_url = reverse(
        "my_learning_chapter",
        kwargs={
            "batch_id": chapter.batch_id,
            "subject_id": chapter.subject_id,
            "chapter_id": chapter.pk,
        },
    )

    if request.method != "POST":
        return redirect(
            f"{chapter_url}?attempt={attempt.pk}&tab=quizzes"
        )

    with transaction.atomic():
        # Lock only the QuizAttempt row. Do not combine select_for_update()
        # with nullable quiz/chapter joins: PostgreSQL rejects FOR UPDATE on
        # the nullable side of an outer join.
        locked_attempt = get_object_or_404(
            QuizAttempt.objects.select_for_update(),
            pk=attempt.pk,
            student=request.user,
        )

        if locked_attempt.status != QuizAttempt.Status.IN_PROGRESS:
            return redirect(
                f"{chapter_url}?attempt={locked_attempt.pk}&tab=quizzes"
            )

        submitted_at = timezone.now()
        has_expired = submitted_at >= locked_attempt.expires_at
        answers = list(
            locked_attempt.answers.select_for_update().all().order_by("pk")
        )
        score = 0

        # Grade the final POST even if it arrived just after the deadline.
        # The attempt is marked timed_out, but submitted selections are retained.
        for answer in answers:
            selected_label = request.POST.get(
                f"answer_{answer.pk}",
                "",
            ).strip().upper()

            allowed_labels = {
                str(option.get("label", "")).upper()
                for option in (answer.options_snapshot or [])
            }
            if selected_label not in allowed_labels:
                selected_label = ""

            selected_text = ""
            for option in (answer.options_snapshot or []):
                if str(option.get("label", "")).upper() == selected_label:
                    selected_text = option.get("text", "")
                    break

            is_correct = (
                bool(selected_label)
                and selected_label
                == str(answer.correct_option_label_snapshot or "").upper()
            )
            marks_awarded = (
                locked_attempt.marks_per_question_snapshot
                if is_correct
                else 0
            )

            answer.selected_option_label = selected_label
            answer.selected_option_text_snapshot = selected_text
            answer.answered_at = submitted_at if selected_label else None
            answer.is_correct = is_correct
            answer.marks_awarded = marks_awarded
            answer.save(
                update_fields=[
                    "selected_option_label",
                    "selected_option_text_snapshot",
                    "answered_at",
                    "is_correct",
                    "marks_awarded",
                    "updated_at",
                ]
            )
            score += marks_awarded

        locked_attempt.status = (
            QuizAttempt.Status.TIMED_OUT
            if has_expired
            else QuizAttempt.Status.SUBMITTED
        )
        locked_attempt.score = score
        locked_attempt.submitted_at = submitted_at
        locked_attempt.save(
            update_fields=[
                "status",
                "score",
                "submitted_at",
                "updated_at",
            ]
        )

    return redirect(
        f"{chapter_url}?attempt={attempt.pk}&tab=quizzes"
    )


# ============================================================
# STUDENT QUIZ - RESULT
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def student_quiz_result_view(request, attempt_id):
    if not is_student_user(request.user):
        messages.error(request, "Student access required.")
        return redirect("signin")

    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "quiz__chapter"),
        pk=attempt_id,
        student=request.user,
    )

    if attempt.quiz is None:
        messages.error(
            request,
            "This quiz is no longer available. Your attempt record has been retained.",
        )
        return redirect("my_learning")

    chapter = attempt.quiz.chapter
    get_object_or_404(
        StudentBatchPurchase,
        student=request.user,
        batch_id=chapter.batch_id,
        status=StudentBatchPurchase.Status.ACTIVE,
    )

    chapter_url = reverse(
        "my_learning_chapter",
        kwargs={
            "batch_id": chapter.batch_id,
            "subject_id": chapter.subject_id,
            "chapter_id": chapter.pk,
        },
    )
    return redirect(
        f"{chapter_url}?attempt={attempt.pk}&tab=quizzes"
    )

# ============================================================
# STUDENT FAQ & HELP VIDEOS
# ============================================================

@login_required(login_url="signin")
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True,
)
def student_help_videos_view(request):

    # --------------------------------------------------------
    # STUDENT ACCESS VALIDATION
    # --------------------------------------------------------

    if not is_student_user(request.user):
        messages.error(
            request,
            "Student access required.",
        )
        return redirect("signin")

    # --------------------------------------------------------
    # PUBLISHED VIDEOS FOR STUDENTS
    # --------------------------------------------------------

    videos = FAQVideo.objects.filter(
        status="published",
        audience__in=("students", "both"),
    ).order_by(
        "display_order",
        "-created_at",
        "-pk",
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    if search_query:
        videos = videos.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    # --------------------------------------------------------
    # CATEGORY FILTER
    # --------------------------------------------------------

    selected_category = request.GET.get(
        "category",
        "",
    ).strip()

    category_choices = FAQVideo.CATEGORY_CHOICES

    allowed_categories = {
        value
        for value, label in category_choices
    }

    if selected_category in allowed_categories:
        videos = videos.filter(
            category=selected_category,
        )
    else:
        selected_category = ""

    # --------------------------------------------------------
    # PAGINATION
    # --------------------------------------------------------

    paginator = Paginator(
        videos,
        12,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    # --------------------------------------------------------
    # RENDER PAGE
    # --------------------------------------------------------

    return render(
        request,
        "students/support/help_videos.html",
        {
            "videos": page_obj.object_list,
            "page_obj": page_obj,
            "search_query": search_query,
            "selected_category": selected_category,
            "category_choices": category_choices,
        },
    )

# ============================================================
# STUDENT MY TIMETABLE
# ============================================================

@login_required(login_url="signin")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def student_timetable_view(request):
    """Read-only weekly timetable with a separate today-only summary."""
    if not is_student_user(request.user):
        messages.error(
            request,
            "Student access required. Please use the student login area.",
        )
        return redirect("signin")

    purchased_batches = Batch.objects.filter(
        student_purchases__student=request.user,
        student_purchases__status=StudentBatchPurchase.Status.ACTIVE,
    ).distinct().order_by("batch_name")

    selected_batch_id = (request.GET.get("batch") or "").strip()
    selected_batch = None
    if selected_batch_id:
        selected_batch = purchased_batches.filter(pk=selected_batch_id).first()
    if selected_batch is None:
        selected_batch = purchased_batches.first()

    today = timezone.localdate()
    requested_date = request.GET.get("week", "").strip()
    week_date = today
    if requested_date:
        parsed = parse_date(requested_date)
        if parsed:
            week_date = parsed

    week_start = week_date
    week_end = week_start + timedelta(days=7)
    days = [week_start + timedelta(days=offset) for offset in range(7)]
    current_tz = timezone.get_current_timezone()

    week_start_dt = timezone.make_aware(
        datetime.combine(week_start, datetime.min.time()), current_tz
    )
    week_end_dt = timezone.make_aware(
        datetime.combine(week_end, datetime.min.time()), current_tz
    )
    today_start_dt = timezone.make_aware(
        datetime.combine(today, datetime.min.time()), current_tz
    )
    tomorrow_start_dt = timezone.make_aware(
        datetime.combine(today + timedelta(days=1), datetime.min.time()),
        current_tz,
    )
    now = timezone.now()

    def get_display_status(live_class):
        if live_class.status == "cancelled":
            return "cancelled"
        if live_class.status == "no_show":
            return "no_show"
        if live_class.status == "completed" or live_class.actual_end_at:
            return "completed"
        if (
            live_class.actual_start_at
            and live_class.actual_start_at <= now
            and not live_class.actual_end_at
        ):
            return "live"
        return "upcoming"

    classes = []
    counts = {
        "total": 0,
        "upcoming": 0,
        "live": 0,
        "completed": 0,
        "cancelled": 0,
    }

    if selected_batch:
        base_qs = LiveClass.objects.filter(batch=selected_batch).select_related(
            "batch", "subject", "chapter", "teacher"
        )

        weekly_classes = base_qs.filter(
            start_at__lt=week_end_dt,
            end_at__gt=week_start_dt,
        ).order_by("start_at", "pk")

        for live_class in weekly_classes:
            live_class.display_status = get_display_status(live_class)
            live_class.local_start = timezone.localtime(live_class.start_at)
            live_class.local_end = timezone.localtime(live_class.end_at)
            live_class.duration_minutes = max(
                1,
                int(
                    (live_class.end_at - live_class.start_at).total_seconds()
                    // 60
                ),
            )
            classes.append(live_class)

        # Daily summary is independent of the week selected in the calendar.
        # It counts sessions whose scheduled start date is today.
        todays_classes = base_qs.filter(
            start_at__gte=today_start_dt,
            start_at__lt=tomorrow_start_dt,
        ).order_by("start_at", "pk")

        for live_class in todays_classes:
            display_status = get_display_status(live_class)
            counts["total"] += 1
            if display_status == "upcoming":
                counts["upcoming"] += 1
            elif display_status == "live":
                counts["live"] += 1
            elif display_status == "completed":
                counts["completed"] += 1
            elif display_status in {"cancelled", "no_show"}:
                counts["cancelled"] += 1

    context = {
        "purchased_batches": purchased_batches,
        "selected_batch": selected_batch,
        "selected_batch_id": str(selected_batch.pk) if selected_batch else "",
        "days": days,
        "week_start": week_start,
        "week_end": week_end - timedelta(days=1),
        "previous_week": week_start - timedelta(days=7),
        "next_week": week_start + timedelta(days=7),
        "today": today,
        "classes": classes,
        "class_counts": counts,
        "time_slots": range(5, 24),
    }
    return render(
        request,
        "students/live_classes/student_timetable.html",
        context,
    )


# ============================================================
# STUDENT - TODAY'S LIVE SCHEDULES
# ============================================================

@login_required(login_url="signin")
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def student_today_live_schedules_view(request):
    """Show today's live and upcoming sessions across active purchases."""

    if not is_student_user(request.user):
        messages.error(
            request,
            "Student access required. Please use the student login area.",
        )
        return redirect("signin")

    today = timezone.localdate()
    current_tz = timezone.get_current_timezone()
    today_start = timezone.make_aware(
        datetime.combine(today, datetime.min.time()),
        current_tz,
    )
    tomorrow_start = timezone.make_aware(
        datetime.combine(today + timedelta(days=1), datetime.min.time()),
        current_tz,
    )
    now = timezone.now()

    # Only batches with an ACTIVE purchase belonging to this student.
    active_batch_ids = StudentBatchPurchase.objects.filter(
        student=request.user,
        status=StudentBatchPurchase.Status.ACTIVE,
    ).values_list("batch_id", flat=True).distinct()

    todays_classes = list(
        LiveClass.objects.filter(
            batch_id__in=active_batch_ids,
            start_at__gte=today_start,
            start_at__lt=tomorrow_start,
        ).select_related(
            "batch",
            "subject",
            "chapter",
            "teacher",
        ).order_by("start_at", "pk")
    )

    counts = {
        "total": 0,
        "live": 0,
        "upcoming": 0,
        "completed": 0,
    }
    schedule_cards = []

    for live_class in todays_classes:
        # Cancelled and No Show sessions are intentionally excluded from
        # the four agreed summary counts and from the schedule card grid.
        if live_class.status in {"cancelled", "no_show"}:
            continue

        if live_class.status == "completed" or live_class.actual_end_at:
            display_status = "completed"
        elif (
            live_class.actual_start_at
            and live_class.actual_start_at <= now
            and not live_class.actual_end_at
        ):
            display_status = "live"
        else:
            # Reaching the scheduled start time does not start a class.
            # Only the existing Admin/Teacher start action sets actual_start_at.
            display_status = "upcoming"

        counts["total"] += 1
        counts[display_status] += 1

        live_class.display_status = display_status
        live_class.local_start = timezone.localtime(live_class.start_at)
        live_class.local_end = timezone.localtime(live_class.end_at)
        live_class.duration_minutes = max(
            1,
            int((live_class.end_at - live_class.start_at).total_seconds() // 60),
        )
        if live_class.duration_minutes >= 60:
            hours, minutes = divmod(live_class.duration_minutes, 60)
            live_class.duration_display = (
                f"{hours} hr" if not minutes else f"{hours} hr {minutes} min"
            )
        else:
            live_class.duration_display = f"{live_class.duration_minutes} min"

        # Use the Admin-managed subject thumbnail. Fall back to the batch
        # thumbnail if the subject image is unavailable.
        live_class.card_thumbnail_url = ""
        try:
            if live_class.subject.subject_thumbnail:
                live_class.card_thumbnail_url = live_class.subject.subject_thumbnail.url
        except (AttributeError, ValueError):
            pass
        if not live_class.card_thumbnail_url:
            try:
                if live_class.batch.batch_thumbnail:
                    live_class.card_thumbnail_url = live_class.batch.batch_thumbnail.url
            except (AttributeError, ValueError):
                pass

        live_class.teacher_display_name = (
            getattr(live_class.teacher, "full_name", "")
            or getattr(getattr(live_class.teacher, "user", None), "get_full_name", lambda: "")()
            or getattr(getattr(live_class.teacher, "user", None), "username", "")
            or "Teacher"
        )

        # The supplied LiveClass model stores provider + room identifiers,
        # but the supplied project has no student join URL/endpoint builder.
        # Keep the action unavailable until the real meeting integration exists.
        live_class.student_join_url = ""
        live_class.student_can_join = False

        # Completed sessions contribute to the count only. The card grid
        # contains today's Live Now and Upcoming sessions.
        if display_status in {"live", "upcoming"}:
            schedule_cards.append(live_class)

    # Live sessions first; upcoming sessions then follow by nearest start time.
    schedule_cards.sort(
        key=lambda item: (
            0 if item.display_status == "live" else 1,
            item.start_at,
            item.pk,
        )
    )

    return render(
        request,
        "students/live_classes/today_live_schedules.html",
        {
            "today": today,
            "counts": counts,
            "schedule_cards": schedule_cards,
        },
    )