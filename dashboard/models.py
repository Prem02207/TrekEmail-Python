from django.db import models


class EmailLog(models.Model):
    # Choices for better data management
    STATUS_CHOICES = [
        ('Sent', 'Sent'),
        ('Read', 'Read'),
    ]

    DELIVERABILITY_CHOICES = [
        ('Inbox', 'Inbox'),
        ('Spam', 'Spam'),
        ('Pending', 'Pending'),
    ]

    email_address = models.EmailField()

    # Ye rahi wo fields jo aapne add karne ko kaha tha
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Sent'
    )

    deliverability = models.CharField(
        max_length=20,
        choices=DELIVERABILITY_CHOICES,
        default='Pending'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email_address} | {self.status} | {self.deliverability}"