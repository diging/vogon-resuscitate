from django.contrib import admin
from external_accounts.models import *

# Register your models here.
admin.site.register(CitesphereAccount)
admin.site.register(CitesphereGroup)
admin.site.register(CitesphereCollection)