from cms.models import Page
from django.db.models import Q
from djangocms_reversion2.settings import BIN_ROOT_TITLE, VERSION_ROOT_TITLE
from aldryn_search.search_indexes import TitleIndex

from .settings import EXCLUDE_VERSIONS_FROM_SEARCH, USE_REVERSION_SEARCH_INDEX


# ----------------------------------
#
# Excludes .~VERSIONS and .~DELETED
#
#  ----------------------------------

class ReversionTitleIndex(TitleIndex):

    haystack_use_for_indexing = USE_REVERSION_SEARCH_INDEX

    def get_index_queryset(self, language):
        queryset = super().get_index_queryset(language)

        if EXCLUDE_VERSIONS_FROM_SEARCH:
            bin_version_pages = Page.objects.filter(title_set__title__in=(VERSION_ROOT_TITLE, BIN_ROOT_TITLE))
            if bin_version_pages.exists():
                # Exclude bin/version root pages
                queryset = queryset.exclude(page__in=bin_version_pages.all())
                # Get root node paths
                bin_version_paths = [page.node.path for page in bin_version_pages]
                for node_path in bin_version_paths:
                    queryset = queryset.exclude(page__node__path__startswith=node_path)

        return queryset

    def should_update(self, instance, **kwargs):
        update = super().should_update(instance, **kwargs)
        if EXCLUDE_VERSIONS_FROM_SEARCH:
            if instance.page.get_root().title_set.filter(title__in=[BIN_ROOT_TITLE, VERSION_ROOT_TITLE]).exists():
                update = False
        return update