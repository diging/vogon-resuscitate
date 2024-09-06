from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import SafeText

import json, datetime, requests, copy, xmltodict
from urllib.parse import urljoin
from string import Formatter
from uuid import uuid4

from repository import auth

class Repository(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def manager(self, user):
        from repository.managers import RepositoryManager
        return RepositoryManager(user=user)

    def __str__(self):
        return self.name