from __future__ import absolute_import, print_function, unicode_literals
from django.conf.urls import *  # NOQA

from .views import view_revision

app_name = 'djangocms_reversion2'

urlpatterns = [
    # Get Category Pages by Category Id
    # --------------------------------
    url(r'^view/(?P<revision_pk>\d+)$', view_revision, name='view_revision'),
]
