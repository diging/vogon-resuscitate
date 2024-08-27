from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse
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

