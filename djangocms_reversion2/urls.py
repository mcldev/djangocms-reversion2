from django.urls import re_path

from .views import view_revision

app_name = 'djangocms_reversion2'

urlpatterns = [
    # Get Category Pages by Category Id
    # --------------------------------
    re_path(r'^view/(?P<revision_pk>\d+)$', view_revision, name='view_revision'),
]
