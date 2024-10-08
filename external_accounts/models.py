from django.db import models
from django.conf import settings
from django.utils import timezone
from django.conf import settings
from requests.exceptions import RequestException
from django.db.models.signals import post_save
from repository.models import Repository
from django.dispatch import receiver
import requests
import json

class CitesphereAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='citesphere_account')
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='citesphere_accounts')
    citesphere_user_id = models.CharField(max_length=255, help_text="Unique identifier for the Citesphere user")
    access_token = models.CharField(max_length=255, help_text="OAuth access token")
    refresh_token = models.CharField(max_length=255, help_text="OAuth refresh token")
    token_expires_at = models.DateTimeField(help_text="The datetime the access token expires")
    extra_data = models.TextField(default='{}', help_text="Any extra data returned by Citesphere in JSON format")

    def __str__(self):
        return f"Citesphere account for {self.user.username}"

    @property
    def extra_data_json(self):
        return json.loads(self.extra_data)

    @extra_data_json.setter
    def extra_data_json(self, value):
        self.extra_data = json.dumps(value)

    def is_token_expired(self):
        return timezone.now() >= self.token_expires_at

@receiver(post_save, sender=CitesphereAccount)
def fetch_citesphere_user_id(sender, instance, created, **kwargs):
    if created:
        repository = instance.repository

        try:
            response = requests.get(
                f'{repository.endpoint}/api/v1/test/',
                headers={'Authorization': f'Bearer {instance.access_token}'}
            )
            response.raise_for_status()  # Raises an HTTPError for bad responses
            response_data = response.json()

            citesphere_user_id = response_data[0]['user']

            if citesphere_user_id:
                instance.citesphere_user_id = citesphere_user_id
                instance.save()
        except RequestException as e:
            print(f"Failed to fetch citesphere_user_id due to network error: {str(e)}")
        except ValueError as e:
            print(f"Failed to decode JSON: {str(e)}")
