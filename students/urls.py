from django.urls import path

from .views import (
    dashboard_view,
    profile_view,
    update_profile_image_view,

    marketplace_view,
    marketplace_detail_view,

    wishlist_view,
    toggle_wishlist_view,
    wishlist_count_view,

    cart_view,
    add_to_cart_view,
    remove_from_cart_view,
    clear_cart_view,
)


urlpatterns = [

    # ============================================================
    # STUDENT DASHBOARD
    # ============================================================

    path(
        'dashboard/',
        dashboard_view,
        name='dashboard',
    ),

    # ============================================================
    # STUDENT PROFILE
    # ============================================================

    path(
        'profile/',
        profile_view,
        name='profile',
    ),

    path(
        'update-profile-image/',
        update_profile_image_view,
        name='update_profile_image',
    ),

    # ============================================================
    # MARKETPLACE
    # ============================================================

    path(
        'marketplace/',
        marketplace_view,
        name='marketplace',
    ),

    path(
        'marketplace/<int:batch_id>/',
        marketplace_detail_view,
        name='marketplace_detail',
    ),

    # ============================================================
    # WISHLIST
    # ============================================================

    path(
        'wishlist/',
        wishlist_view,
        name='wishlist',
    ),

    path(
        'wishlist/toggle/<int:batch_id>/',
        toggle_wishlist_view,
        name='toggle_wishlist',
    ),

    # Used only when a client needs the current wishlist count.
    path(
        'wishlist/count/',
        wishlist_count_view,
        name='wishlist_count',
    ),

    # ============================================================
    # CART
    # ============================================================

    path(
        'cart/',
        cart_view,
        name='cart',
    ),

    path(
        'cart/add/<int:batch_id>/',
        add_to_cart_view,
        name='add_to_cart',
    ),

    path(
        'cart/remove/<int:batch_id>/',
        remove_from_cart_view,
        name='remove_from_cart',
    ),

    path(
        'cart/clear/',
        clear_cart_view,
        name='clear_cart',
    ),
]