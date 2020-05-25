from cms.models import Page
from django.db.models import Q

from .settings import EXCLUDE_VERSIONS_FROM_SEARCH

if EXCLUDE_VERSIONS_FROM_SEARCH:

    from djangocms_reversion2.settings import BIN_ROOT_TITLE, VERSION_ROOT_TITLE
    from aldryn_search.search_indexes import TitleIndex

    # ----------------------------------
    #
    # Excludes .~VERSIONS and .~DELETED
    #
    #  ----------------------------------


    class NEW_TitleIndex(TitleIndex):

        haystack_use_for_indexing = True

        def get_index_queryset(self, language):
            queryset = super(NEW_TitleIndex, self).get_index_queryset(language)

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
            update = super(NEW_TitleIndex, self).should_update(instance, **kwargs)
            if instance.page.get_root().title_set.filter(title__in=[BIN_ROOT_TITLE, VERSION_ROOT_TITLE]).exists():
                update = False
            return update