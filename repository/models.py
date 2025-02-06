from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import SafeText

class Repository(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    endpoint = models.CharField(_("Endpoint"), max_length=255, help_text="Enter the endpoint URL without a trailing slash")
    giles_endpoint = models.CharField(_("Giles Endpoint"), max_length=255, help_text="Enter the endpoint URL without a trailing slash")
    client_id = models.CharField(_("Client ID"), max_length=50)
    client_secret = models.CharField(_("Client Secret"), max_length=255)

    def manager(self, user, repository):
        from repository.managers import RepositoryManager
        return RepositoryManager(user=user, repository=repository)

    def __str__(self):
        return self.name
