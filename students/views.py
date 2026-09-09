from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone

import cloudinary.uploader

from admins.models import Batch, Subject

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


# ============================================================
# CART PAGE
# ============================================================

@login_required(login_url='signin')
@cache_control(
    no_cache=True,
    must_revalidate=True,
    no_store=True
)
def cart_view(request):

    if not is_student_user(request.user):

        messages.error(
            request,
            'Admin login is not allowed here. Please use the admin login area.'
        )

        return redirect('signin')


    # ========================================================
    # GET / CREATE STUDENT CART
    # ========================================================

    cart, created = Cart.objects.get_or_create(
        student=request.user
    )


    # ========================================================
    # CART ITEMS
    #
    # Fetch the Batch together with:
    # - Subjects
    # - Assigned Teachers
    # - Teacher profile information
    # ========================================================

    cart_items = (
        cart.items
        .select_related('batch')
        .prefetch_related(
            'batch__subjects',
            'batch__assigned_teachers__teacher',
        )
    )


    # ========================================================
    # SUBTOTAL
    #
    # Batch.final_price already contains the Batch-level
    # discount calculated by the Batch model.
    #
    # Coupon discount will be added later.
    # ========================================================

    subtotal = sum(
        item.batch.final_price
        for item in cart_items
    )


    # ========================================================
    # CART COUNT
    #
    # Used by the Student Navbar.
    # ========================================================

    cart_count = cart.items.count()


    # ========================================================
    # RENDER
    # ========================================================

    return render(
        request,
        'students/cart/cart.html',
        {
            'cart': cart,
            'cart_items': cart_items,
            'subtotal': subtotal,
            'cart_count': cart_count,
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