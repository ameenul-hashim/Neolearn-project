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
    path('batches/',admin_batches_view, name='admin_batches'),
    path('batches/create/',create_batch_view, name='create_batch'),
    path('edit-batch/<int:batch_id>/',edit_batch_view,name='edit_batch'),
    path("batches/delete/<int:batch_id>/",delete_batch_view,name="delete_batch"),
    path("batches/<int:batch_id>/subjects/",batch_subjects,name="batch_subjects"),
    path("subjects/",admin_subjects_view,name="admin_subjects"),
    path("subjects/create/",create_subject_view,name="create_subject"),
    path("subjects/edit/<int:subject_id>/",edit_subject_view,name="edit_subject"),
    path("subjects/delete/<int:subject_id>/",delete_subject_view,name="delete_subject"),
    path("subjects/",admin_subjects_view,name="admin_subjects"),
    path("teachers/",admin_teachers,name="admin_teachers"),
    path("teachers/create/",create_teacher_view,name="create_teacher"),
    
]