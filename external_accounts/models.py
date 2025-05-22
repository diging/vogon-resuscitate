from django.db import models
from django.conf import settings
from django.utils import timezone
from requests.exceptions import RequestException
from django.db.models.signals import post_save
from repository.models import Repository
from django.dispatch import receiver
from django.conf import settings
from hashlib import sha256
from cryptography.fernet import Fernet
import requests
import json
import base64
import os

class CitesphereAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='citesphere_account')
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='citesphere_accounts')
    citesphere_user_id = models.CharField(max_length=255, help_text="Unique identifier for the Citesphere user")
    access_token = models.CharField(max_length=255, help_text="OAuth access token")
    refresh_token = models.CharField(max_length=255, help_text="OAuth refresh token")
    token_expires_at = models.DateTimeField(help_text="The datetime the access token expires")
    extra_data = models.TextField(default='{}', help_text="Any extra data returned by Citesphere in JSON format")

    def __str__(self):
        return f"Citesphere account:{self.user.username} Repository: {self.repository.name}"

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
            
class ConceptpowerAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conceptpower_account')
    username = models.CharField(max_length=255, unique=True)
    _password = models.CharField(max_length=255, db_column='password')
    
    def __str__(self):
        return self.username
        
    @property
    def password(self):
        """Get the decrypted password"""

        if not self._password:
            return None
        try:
            salt, encrypted = self._password.split('$', 1)
            salt = base64.b64decode(salt.encode())
            encrypted = base64.b64decode(encrypted.encode())
            key = self._derive_key(salt)
            return self._decrypt(encrypted, key)
        except Exception:
            return None
            
    @password.setter
    def password(self, value):
        """Encrypt and store the password"""

        if not value:
            self._password = ''
            return
        salt = os.urandom(16)
        key = self._derive_key(salt)
        encrypted = self._encrypt(value, key)
        self._password = f"{base64.b64encode(salt).decode()}${base64.b64encode(encrypted).decode()}"
    
    def _derive_key(self, salt):
        """Derive an encryption key from the salt using Django's SECRET_KEY"""

        key = sha256(settings.SECRET_KEY.encode() + salt).digest()
        return key
    
    def _encrypt(self, value, key):
        """Encrypt a value using the given key"""

        fernet_key = base64.urlsafe_b64encode(key[:32])
        f = Fernet(fernet_key)
        return f.encrypt(value.encode())
    
    def _decrypt(self, encrypted, key):
        """Decrypt a value using the given key"""

        fernet_key = base64.urlsafe_b64encode(key[:32])
        f = Fernet(fernet_key)
        return f.decrypt(encrypted).decode()