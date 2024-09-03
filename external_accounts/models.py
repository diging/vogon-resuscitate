from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings
from requests.exceptions import RequestException
from django.db.models.signals import post_save
from django.dispatch import receiver
import requests
import json

class CitesphereAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='citesphere_account')
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

class CitesphereGroup(models.Model):
    citesphere_accounts = models.ManyToManyField('CitesphereAccount', related_name='groups')
    group_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    version = models.IntegerField()
    num_items = models.IntegerField()
    date_created = models.DateTimeField()
    date_modified = models.DateTimeField()
    type = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(max_length=200, blank=True, null=True)
    sync_status = models.CharField(max_length=100, default='PENDING')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(CitesphereGroup, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('group_detail', kwargs={'slug': self.slug})

    def __str__(self):
        return f"{self.name} (ID: {self.group_id})"


class CitesphereCollection(models.Model):
    group = models.ForeignKey('CitesphereGroup', related_name='collections', on_delete=models.CASCADE)
    collection_id = models.CharField(max_length=255)
    key = models.CharField(max_length=100)
    version = models.IntegerField()
    content_version = models.IntegerField(default=0)
    number_of_collections = models.IntegerField(default=0)
    number_of_items = models.IntegerField(default=0)
    name = models.CharField(max_length=255)
    parent_collection_key = models.CharField(max_length=100, blank=True, null=True)
    last_modified = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class CitesphereItem(models.Model):
    key = models.CharField(max_length=100, unique=True)
    group = models.ForeignKey('CitesphereGroup', on_delete=models.CASCADE, related_name='items')
    collection = models.ForeignKey('CitesphereCollection', on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    title = models.CharField(max_length=255)
    authors = models.TextField(help_text="JSON format of authors list")
    editors = models.TextField(blank=True, null=True, help_text="JSON format of editors list")
    itemType = models.CharField(max_length=100)
    publicationTitle = models.CharField(max_length=255, blank=True, null=True)
    volume = models.CharField(max_length=50, blank=True, null=True)
    issue = models.CharField(max_length=50, blank=True, null=True)
    pages = models.CharField(max_length=50, blank=True, null=True)
    date = models.DateTimeField(null=True, blank=True)
    url = models.URLField(max_length=200, blank=True, null=True)
    abstractNote = models.TextField(blank=True, null=True)
    journalAbbreviation = models.CharField(max_length=100, blank=True, null=True)
    doi = models.CharField(max_length=100, blank=True, null=True)
    issn = models.CharField(max_length=100, blank=True, null=True)
    extra = models.TextField(blank=True, null=True)
    dateAdded = models.DateTimeField(null=True, blank=True)
    dateModified = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

@receiver(post_save, sender=CitesphereAccount)
def fetch_citesphere_user_id(sender, instance, created, **kwargs):
    if created:
        try:
            response = requests.get(
                f'{settings.CITESPHERE_ENDPOINT}/api/v1/test/',
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
