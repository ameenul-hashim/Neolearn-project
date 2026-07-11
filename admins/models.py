from django.db import models
from django.contrib.auth.models import User

class Batch(models.Model):

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    batch_name = models.CharField(max_length=200, unique=True)
    batch_description = models.TextField()
    batch_thumbnail = models.ImageField(upload_to='batch_thumbnails/')
    batch_price = models.DecimalField(max_digits=10, decimal_places=2)
    batch_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Batch"
        verbose_name_plural = "Batches"

    def __str__(self):
        return self.batch_name
    
    
from django.db import models
from cloudinary.models import CloudinaryField


class Subject(models.Model):

    STATUS_CHOICES = [('draft', 'Draft'),('published', 'Published')]
    batch = models.ForeignKey(Batch,on_delete=models.CASCADE,related_name='subjects')
    subject_name = models.CharField(max_length=200)
    subject_description = models.TextField()
    subject_thumbnail = CloudinaryField('subject_thumbnail')
    subject_status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at']
        unique_together = ['batch', 'subject_name']
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
    def __str__(self):
        return f"{self.batch.batch_name} - {self.subject_name}"
    




class Teacher(models.Model):

    user = models.OneToOneField(User,on_delete=models.CASCADE,related_name="teacher_profile")
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=10, unique=True)
    profile_image = models.ImageField(upload_to="teachers/profile/",blank=True,null=True)
    is_first_login = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    qualification = models.CharField(max_length=255,blank=True)
    specialization = models.CharField(max_length=255,blank=True)
    experience = models.PositiveIntegerField(default=0,help_text="Years of experience")
    bio = models.TextField(blank=True)
    linkedin = models.URLField(blank=True)
    website = models.URLField(blank=True)
    language = models.CharField(max_length=100,blank=True)
    profile_completed = models.BooleanField(default=False)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,related_name="created_teachers",null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def initials(self):

        if not self.full_name:
            return "NA"

        words = self.full_name.split()

        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()

        return self.full_name[:2].upper()
    def __str__(self):

        return self.full_name