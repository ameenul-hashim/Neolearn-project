from django.urls import path
from .views import *


urlpatterns = [
    path('dashboard/',dashboard_view,name='dashboard'),
    path('update-profile-image/',update_profile_image_view,name='update_profile_image'),
    path('profile/',profile_view,name='profile'),
    path("marketplace/",marketplace_view,name="marketplace",),
    path("marketplace/<int:batch_id>/",marketplace_detail_view,name="marketplace_detail"),

]