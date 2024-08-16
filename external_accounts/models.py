from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class CitesphereAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='citesphere_account')
    citesphere_user_id = models.CharField(max_length=255, help_text="Unique identifier for the Citesphere user")
    access_token = models.CharField(max_length=255, help_text="OAuth access token")
    refresh_token = models.CharField(max_length=255, help_text="OAuth refresh token")
    token_expires_at = models.DateTimeField(help_text="The datetime the access token expires")
    extra_data = models.JSONField(default=dict, help_text="Any extra data returned by Citesphere")

    def __str__(self):
        return f"Citesphere account for {self.user.username}"

    def is_token_expired(self):
        return timezone.now() >= self.token_expires_at

    def refresh_access_token(self):
        # This method would handle the logic for refreshing the access token using the refresh token
        pass
