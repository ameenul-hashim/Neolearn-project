# from django.db import models
# from django.contrib.auth.models import User


# class StudentProfile(models.Model):

#     user=models.OneToOneField( User,on_delete=models.CASCADE)
#     profile_image=models.URLField(blank=True,null=True)
#     bio=models.TextField(blank=True)
#     phone=models.CharField(max_length=10,blank=True)
#     address=models.TextField(blank=True)
#     joined_at=models.DateTimeField(auto_now_add=True)
#     def __str__(self):
#         return self.user.username