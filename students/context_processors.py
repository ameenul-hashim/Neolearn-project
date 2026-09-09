from .models import Cart, StudentWishlist


def student_navigation_counts(request):
    """
    Global student navigation counts.

    Available in base_student.html and therefore
    available on all templates using the student base.

    Provides:

        cart_count
        wishlist_count

    These values are intentionally handled here
    instead of being duplicated inside individual
    student page views.
    """

    cart_count = 0
    wishlist_count = 0

    if not request.user.is_authenticated:
        return {
            'cart_count': cart_count,
            'wishlist_count': wishlist_count,
        }

    # ========================================================
    # CART COUNT
    # ========================================================

    cart = Cart.objects.filter(
        student=request.user
    ).first()

    if cart:
        cart_count = cart.items.count()

    # ========================================================
    # WISHLIST COUNT
    # ========================================================

    wishlist_count = StudentWishlist.objects.filter(
        student=request.user
    ).count()

    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
    }