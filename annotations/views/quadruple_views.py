"""
These views are mainly for debugging purposes; they provide quad-xml from
various scenarios.
"""

from django.http import HttpResponse

from annotations import quadriga
from annotations.models import (RelationSet, Appellation, Relation, VogonUser,
                                Text)

