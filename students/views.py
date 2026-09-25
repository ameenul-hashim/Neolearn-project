from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
from admins.models import (
    Batch,
    Subject,
    Coupon,
)
from orders.models import StudentBatchPurchase,Order
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
        'students/dashboard.html'
    )


# ============================================================
# STUDENT PROFILE
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def profile_view(request):

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    return render(
        request,
        'students/profile.html',
        {
            'profile': profile
        }
    )


# ============================================================
# PROFILE IMAGE UPDATE
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def update_profile_image_view(request):

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    if request.method == 'POST':

        image = request.FILES.get('profile_image')

        # ----------------------------------------------------
        # IMAGE SIZE VALIDATION
        # ----------------------------------------------------

        if image and image.size > 10 * 1024 * 1024:

            messages.error(
                request,
                'Image size must be below 10MB.'
            )

            return redirect('profile')

        # ----------------------------------------------------
        # IMAGE UPLOAD
        # ----------------------------------------------------

        if image:

            profile, created = StudentProfile.objects.get_or_create(
                user=request.user
            )

            # ------------------------------------------------
            # DELETE OLD IMAGE FROM CLOUDINARY
            # ------------------------------------------------

            if profile.cloudinary_public_id:

                try:

                    cloudinary.uploader.destroy(
                        profile.cloudinary_public_id
                    )

                except Exception:
                    pass

            # ------------------------------------------------
            # UPLOAD NEW IMAGE
            # ------------------------------------------------

            uploaded_image = cloudinary.uploader.upload(
                image,
                folder='neolearn_profiles'
            )

            # ------------------------------------------------
            # SAVE IMAGE INFORMATION
            # ------------------------------------------------

            profile.profile_image = uploaded_image[
                'secure_url'
            ]

            profile.cloudinary_public_id = uploaded_image[
                'public_id'
            ]

            profile.save()

            messages.success(
                request,
                'Profile image updated successfully.'
            )

        else:

            messages.error(
                request,
                'Please select an image.'
            )

    return redirect('profile')

# ============================================================
# MARKETPLACE
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def marketplace_view(request):

    # ========================================================
    # STUDENT ACCESS
    # ========================================================

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    # ========================================================
    # CURRENT TIME
    # ========================================================

    now = timezone.now()

    # ========================================================
    # QUERY PARAMETERS
    # ========================================================

    current_status = request.GET.get(
        'status',
        'all'
    ).strip().lower()

    search_query = request.GET.get(
        'search',
        ''
    ).strip()

    # --------------------------------------------------------
    # SUBJECT FILTER
    # --------------------------------------------------------

    subject_id = request.GET.get(
        'subject',
        ''
    ).strip()

    # --------------------------------------------------------
    # BATCH FILTER
    # --------------------------------------------------------

    batch_id = request.GET.get(
        'batch_id',
        ''
    ).strip()

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    sort_option = request.GET.get(
        'sort',
        'newest'
    ).strip().lower()

    # --------------------------------------------------------
    # DISCOUNT
    # --------------------------------------------------------

    discount_option = request.GET.get(
        'discount',
        ''
    ).strip().lower()

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    min_price = request.GET.get(
        'min_price',
        ''
    ).strip()

    max_price = request.GET.get(
        'max_price',
        ''
    ).strip()

    # ========================================================
    # VALID STATUS
    # ========================================================

    allowed_statuses = {
        'all',
        'buy_now',
        'coming_soon',
        'admissions_closed',
    }

    if current_status not in allowed_statuses:

        current_status = 'all'

    # ========================================================
    # MARKETPLACE FILTER OPTIONS
    #
    # These are dynamic database values.
    # ========================================================

    marketplace_filter_batches = (
        Batch.objects.filter(
            marketplace_visible=True
        )
        .exclude(
            batch_status='draft'
        )
        .prefetch_related(
            'subjects'
        )
        .order_by(
            'batch_name'
        )
    )

    # ========================================================
    # BASE MARKETPLACE QUERY
    #
    # Only marketplace-visible, non-draft batches.
    # ========================================================

    batches = (
        Batch.objects.filter(
            marketplace_visible=True
        )
        .exclude(
            batch_status='draft'
        )
    )

    # ========================================================
    # STATUS FILTER
    # ========================================================

    if current_status == 'buy_now':

        batches = (
            batches
            .filter(
                batch_status='published'
            )
            .filter(
                Q(
                    publish_type='immediate'
                )
                |
                Q(
                    publish_type='scheduled',
                    publish_datetime__lte=now
                )
            )
            .filter(
                Q(
                    admission_close_datetime__isnull=True
                )
                |
                Q(
                    admission_close_datetime__gt=now
                )
            )
        )

    elif current_status == 'coming_soon':

        batches = batches.filter(
            batch_status='published',
            publish_type='scheduled',
            publish_datetime__gt=now
        )

    elif current_status == 'admissions_closed':

        batches = batches.filter(
            Q(
                batch_status='archived'
            )
            |
            Q(
                batch_status='published',
                admission_close_datetime__isnull=False,
                admission_close_datetime__lte=now
            )
        )

    else:

        # ----------------------------------------------------
        # ALL BATCHES
        #
        # Every marketplace-visible, non-draft batch.
        # ----------------------------------------------------

        pass

    # ========================================================
    # BATCH FILTER
    #
    # If a specific Batch is selected, only that Batch
    # is displayed.
    # ========================================================

    if batch_id:

        try:

            batch_id_value = int(batch_id)

            batches = batches.filter(
                id=batch_id_value
            )

        except (TypeError, ValueError):

            batch_id = ''

    # ========================================================
    # SUBJECT FILTER
    #
    # The subject ID comes from the real Subject table.
    # ========================================================

    if subject_id:

        try:

            subject_id_value = int(subject_id)

            batches = batches.filter(
                subjects__id=subject_id_value
            )

        except (TypeError, ValueError):

            subject_id = ''

    # ========================================================
    # SEARCH
    #
    # Search dynamically across:
    #
    #   Batch name
    #   Batch description
    #   Subject name
    # ========================================================

    if search_query:

        batches = batches.filter(
            Q(
                batch_name__icontains=search_query
            )
            |
            Q(
                batch_description__icontains=search_query
            )
            |
            Q(
                subjects__subject_name__icontains=search_query
            )
        )

    # ========================================================
    # DISCOUNT FILTER
    # ========================================================

    if discount_option in {
        'percentage',
        'fixed',
        'none',
    }:

        batches = batches.filter(
            discount_type=discount_option
        )

    elif discount_option:

        discount_option = ''

    # ========================================================
    # MINIMUM PRICE
    # ========================================================

    if min_price:

        try:

            min_price_value = float(
                min_price
            )

            if min_price_value >= 0:

                batches = batches.filter(
                    final_price__gte=min_price_value
                )

            else:

                min_price = ''

        except (TypeError, ValueError):

            min_price = ''

    # ========================================================
    # MAXIMUM PRICE
    # ========================================================

    if max_price:

        try:

            max_price_value = float(
                max_price
            )

            if max_price_value >= 0:

                batches = batches.filter(
                    final_price__lte=max_price_value
                )

            else:

                max_price = ''

        except (TypeError, ValueError):

            max_price = ''

    # ========================================================
    # SORTING
    # ========================================================

    sort_mapping = {

        'newest': '-created_at',

        'oldest': 'created_at',

        'a_z': 'batch_name',

        'z_a': '-batch_name',

        'price_low': 'final_price',

        'price_high': '-final_price',

    }

    if sort_option == 'discount':

        batches = batches.order_by(
            '-discount_value',
            '-created_at'
        )

    elif sort_option in sort_mapping:

        batches = batches.order_by(
            sort_mapping[sort_option]
        )

    else:

        sort_option = 'newest'

        batches = batches.order_by(
            '-created_at'
        )

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    batches = batches.distinct()

    # ========================================================
    # PREFETCH MARKETPLACE DATA
    # ========================================================

    batches = batches.prefetch_related(
        'subjects',
        'assigned_teachers',
    )

    # ========================================================
    # WISHLIST IDS
    #
    # Used by Marketplace to determine whether a batch
    # is already in the student's wishlist.
    # ========================================================

    wishlisted_batch_ids = set(
        StudentWishlist.objects.filter(
            student=request.user
        ).values_list(
            'batch_id',
            flat=True
        )
    )

    # ========================================================
    # CART BATCH IDS
    #
    # IMPORTANT:
    #
    # This is different from cart_count.
    #
    # cart_count = number of items in the cart.
    #
    # cart_batch_ids = IDs of the actual batches currently
    # inside the cart.
    #
    # Marketplace uses this to show:
    #
    #   🛒 Add to Cart
    #
    # or
    #
    #   ✓ Added to Cart
    # ========================================================

    try:

        cart = Cart.objects.get(
            student=request.user
        )

        cart_batch_ids = set(
            cart.items.values_list(
                'batch_id',
                flat=True
            )
        )

    except Cart.DoesNotExist:

        cart_batch_ids = set()

    # ========================================================
    # PURCHASED BATCH IDS
    #
    # These are the batches already purchased by the
    # currently logged-in student.
    #
    # Marketplace will use this to show:
    #
    #   ✓ Purchased
    #   View My Learning
    #
    # instead of Add to Cart.
    # ========================================================

    purchased_batch_ids = set(
        StudentBatchPurchase.objects.filter(
            student=request.user,
            status=StudentBatchPurchase.Status.ACTIVE,
        ).values_list(
            'batch_id',
            flat=True,
        )
    )

    # ========================================================
    # FLAT SUBJECT LIST
    #
    # Kept for compatibility with existing templates.
    #
    # Do not remove this.
    # ========================================================

    subjects = (
        Subject.objects.filter(
            batch__marketplace_visible=True
        )
        .exclude(
            batch__batch_status='draft'
        )
        .order_by(
            'subject_name'
        )
        .distinct()
    )

    # ========================================================
    # RENDER MARKETPLACE
    # ========================================================

    return render(
        request,
        'students/marketplace.html',
        {
            # ------------------------------------------------
            # MAIN MARKETPLACE RESULTS
            # ------------------------------------------------

            'batches': batches,

            # ------------------------------------------------
            # DYNAMIC FILTER BATCHES
            # ------------------------------------------------

            'marketplace_filter_batches': marketplace_filter_batches,

            # ------------------------------------------------
            # SUBJECTS
            # ------------------------------------------------

            'subjects': subjects,

            # ------------------------------------------------
            # CURRENT FILTER STATE
            # ------------------------------------------------

            'current_status': current_status,

            'search_query': search_query,

            'subject_id': subject_id,

            'batch_id': batch_id,

            'sort_option': sort_option,

            'discount_option': discount_option,

            'min_price': min_price,

            'max_price': max_price,

            # ------------------------------------------------
            # WISHLIST
            #
            # Page-specific wishlist state.
            # ------------------------------------------------

            'wishlisted_batch_ids': wishlisted_batch_ids,

            # ------------------------------------------------
            # CART
            #
            # Page-specific cart state.
            #
            # This is what Marketplace needs for the
            # Add to Cart / Added to Cart button.
            # ------------------------------------------------

            'cart_batch_ids': cart_batch_ids,

            # ------------------------------------------------
            # PURCHASED BATCHES
            #
            # Page-specific purchased state.
            #
            # This is what Marketplace needs to determine
            # whether the student already owns the batch.
            # ------------------------------------------------

            'purchased_batch_ids': purchased_batch_ids,
        }
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

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    batch = get_object_or_404(
        Batch.objects.prefetch_related(
            'subjects',
            'assigned_teachers',
        ),
        id=batch_id,
        batch_status='published',
        marketplace_visible=True,
    )

    return render(
        request,
        'students/marketplace-detail.html',
        {
            'batch': batch,
        }
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

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    wishlist_items = (
        StudentWishlist.objects.filter(
            student=request.user
        )
        .select_related(
            'batch'
        )
        .order_by(
            '-created_at'
        )
    )

    wishlist_count = wishlist_items.count()

    return render(
        request,
        'students/wishlist/wishlist.html',
        {
            'wishlist_items': wishlist_items,
            'wishlist_count': wishlist_count,
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
    # VALID MARKETPLACE BATCH
    # ========================================================

    batch = get_object_or_404(
        Batch,
        id=batch_id,
        batch_status='published',
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

        return JsonResponse(
            {
                'success': True,
                'wishlisted': wishlisted,
                'wishlist_count': wishlist_count,
                'batch_id': batch.id,
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

        return redirect('marketplace')

    batch = get_object_or_404(
        Batch,
        id=batch_id,
        batch_status='published',
        marketplace_visible=True,
    )

    if batch.marketplace_status != 'buy_now':

        messages.warning(
            request,
            'This batch is not currently available for purchase.'
        )

        return redirect('marketplace')

    # ========================================================
    # ALREADY PURCHASED
    # ========================================================
    # A student who already owns an active purchase must never
    # be able to add the same batch to the cart again.
    #
    # This is enforced server-side so it cannot be bypassed by
    # manually submitting the add-to-cart request.
    # ========================================================

    if StudentBatchPurchase.objects.filter(
        student=request.user,
        batch=batch,
        status=StudentBatchPurchase.Status.ACTIVE,
    ).exists():

        messages.info(
            request,
            f'"{batch.batch_name}" is already in your learning.'
        )

        return redirect('my_learning')

    cart, created = Cart.objects.get_or_create(
        student=request.user
    )

    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        batch=batch,
    )

    if item_created:

        messages.success(
            request,
            f'"{batch.batch_name}" has been added to your cart.'
        )

    else:

        messages.info(
            request,
            f'"{batch.batch_name}" is already in your cart.'
        )

    return redirect('marketplace')


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

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def my_learning_view(request):

    # ========================================================
    # STUDENT ACCESS
    # ========================================================

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')

    # ========================================================
    # PURCHASED BATCHES
    # ========================================================

    purchased_batches = (
        StudentBatchPurchase.objects
        .filter(
            student=request.user,
            status=StudentBatchPurchase.Status.ACTIVE,
        )
        .select_related(
            'batch',
            'order',
            'order_item',
        )
        .order_by(
            '-purchased_at'
        )
    )

    # ========================================================
    # RENDER MY LEARNING
    # ========================================================

    return render(
        request,
        'students/my_learning/my_learning.html',
        {
            'purchased_batches': purchased_batches,
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
        "pending",
        "payment_processing",
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

        "pending": all_orders.filter(
            status=Order.Status.PENDING,
        ).count(),

        "payment_processing": all_orders.filter(
            status=Order.Status.PAYMENT_PROCESSING,
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