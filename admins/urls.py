from django.urls import path
from . views import *
urlpatterns = [
    path('signin/',admin_signin_view,name='admin_signin'),
    path('dashboard/',admin_dashboard_view,name='admin_dashboard'),
    path('logout/',admin_logout_view,name='admin_logout'),
    path('students/',admin_students_view,name='admin_students'),
    path('students/block/<int:user_id>/',block_student_view,name='block_student'),
    path('students/unblock/<int:user_id>/',unblock_student_view,name='unblock_student'),
    path('students/delete/<int:user_id>/',delete_student_view,name='delete_student'),
    
]