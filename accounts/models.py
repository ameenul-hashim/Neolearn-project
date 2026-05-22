from django.db import models
from django.contrib.auth.models import User


class EmailOTP(models.Model):

    user=models.ForeignKey(User,on_delete=models.CASCADE,db_constraint=False)
    otp=models.CharField(max_length=6)
    is_used=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.user.email


