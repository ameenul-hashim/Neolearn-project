
from django.urls import path

from .views import (
    dashboard_view,
    student_timetable_view,
    student_today_live_schedules_view,
    student_settings_view,
    marketplace_view,
    marketplace_detail_view,
    my_learning_view,
    my_learning_batch_view,
    my_learning_subject_view,
    my_learning_chapter_view,
    wishlist_view,
    toggle_wishlist_view,
    wishlist_count_view,
    cart_view,
    add_to_cart_view,
    remove_from_cart_view,
    clear_cart_view,
    apply_coupon_view,
    remove_coupon_view,
    order_history_view,
    order_details_view,
    start_quiz_view,
    student_quiz_take_view,
    student_quiz_result_view,
    student_quiz_answer_save_view,
    student_help_videos_view,

    # Student Teachers
    student_my_teachers_view,
    student_teacher_profile_view,
)

urlpatterns = [
    path("dashboard/", dashboard_view, name="dashboard"),

    path(
        "my-timetable/",
        student_timetable_view,
        name="student_timetable",
    ),

    path(
        "today-live-schedules/",
        student_today_live_schedules_view,
        name="student_today_live_schedules",
    ),

    # Student Teachers
    path(
        "teachers/",
        student_my_teachers_view,
        name="student_my_teachers",
    ),
    path(
        "teachers/<int:teacher_id>/",
        student_teacher_profile_view,
        name="student_teacher_profile",
    ),

    path("settings/", student_settings_view, name="student_settings"),

    path("marketplace/", marketplace_view, name="marketplace"),
    path(
        "marketplace/<int:batch_id>/",
        marketplace_detail_view,
        name="marketplace_detail",
    ),

    path("wishlist/", wishlist_view, name="wishlist"),
    path(
        "wishlist/toggle/<int:batch_id>/",
        toggle_wishlist_view,
        name="toggle_wishlist",
    ),
    path("wishlist/count/", wishlist_count_view, name="wishlist_count"),

    path("cart/", cart_view, name="cart"),
    path(
        "cart/add/<int:batch_id>/",
        add_to_cart_view,
        name="add_to_cart",
    ),
    path(
        "cart/remove/<int:batch_id>/",
        remove_from_cart_view,
        name="remove_from_cart",
    ),
    path("cart/clear/", clear_cart_view, name="clear_cart"),
    path(
        "cart/apply-coupon/",
        apply_coupon_view,
        name="apply_coupon",
    ),
    path(
        "cart/remove-coupon/<int:coupon_id>/",
        remove_coupon_view,
        name="remove_coupon",
    ),

    path("my-learning/", my_learning_view, name="my_learning"),
    path(
        "my-learning/<int:batch_id>/",
        my_learning_batch_view,
        name="my_learning_batch",
    ),
    path(
        "my-learning/<int:batch_id>/subjects/<int:subject_id>/",
        my_learning_subject_view,
        name="my_learning_subject",
    ),
    path(
        "my-learning/<int:batch_id>/subjects/<int:subject_id>/chapters/<int:chapter_id>/",
        my_learning_chapter_view,
        name="my_learning_chapter",
    ),
    path(
        "my-learning/<int:batch_id>/subjects/<int:subject_id>/chapters/<int:chapter_id>/quizzes/<int:quiz_id>/start/",
        start_quiz_view,
        name="student_quiz_start",
    ),
    path(
        "my-learning/quiz-attempts/<int:attempt_id>/",
        student_quiz_take_view,
        name="student_quiz_take",
    ),
    path(
        "my-learning/quiz-attempts/<int:attempt_id>/answers/<int:answer_id>/save/",
        student_quiz_answer_save_view,
        name="student_quiz_answer_save",
    ),
    path(
        "my-learning/quiz-attempts/<int:attempt_id>/result/",
        student_quiz_result_view,
        name="student_quiz_result",
    ),

    path("orders/", order_history_view, name="order_history"),
    path(
        "orders/<str:order_number>/",
        order_details_view,
        name="order_details",
    ),

    path(
        "help-videos/",
        student_help_videos_view,
        name="student_help_videos",
    ),
]
