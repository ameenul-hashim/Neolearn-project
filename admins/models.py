from django.db import models


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