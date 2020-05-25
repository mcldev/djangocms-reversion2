
from cms.toolbar.items import LinkItem
from django.urls import reverse
from django.http.request import QueryDict
from django.utils.translation import ugettext_lazy as _

from cms.toolbar_pool import toolbar_pool
from cms.toolbar_base import CMSToolbar

from djangocms_reversion2.settings import ALLOW_MANUAL_SNAPSHOTS
from djangocms_reversion2.utils import is_version_page


@toolbar_pool.register
class Reversion2Modifier(CMSToolbar):

    def populate(self):
        page = self.request.current_page
        if not page:
            return

        # if the current page is an archived page we want to disable the toolbar
        is_archived = is_version_page(page)
        if is_archived:
            # disable all menus
            for name, menu in self.request.toolbar.menus.items():
                menu.disabled = True
            # remove the publish button


        if page:
            reversion_menu = self.toolbar.get_or_create_menu('djangocms_reversion2', _('Reversion'))

            if is_archived:
                reversion_menu.add_item(LinkItem(_('This is an archived version'), url=''))
                return


            if ALLOW_MANUAL_SNAPSHOTS and page.publisher_is_draft:
                reversion_menu.add_modal_item(
                    _('Create a snapshot of current page'),
                    url=self.get_url('admin:djangocms_reversion2_pageversion_add', query_args={'draft': page.id,
                                                                                               'language': self.current_lang})
                )

            reversion_menu.add_modal_item(
                _('Show history'),
                url=self.get_url('admin:djangocms_reversion2_diff_view',
                                 arguments={'left_pk': '0', 'right_pk': '0', 'page_pk': page.id},
                                 query_args={'language': self.current_lang}))
            reversion_menu.add_break()
            reversion_menu.add_modal_item(
                _('Create a snapshot of all unrevised pages'),
                url=self.get_url('admin:djangocms_reversion2_pagerevision_batch_add',
                                 arguments={'pk': page.id},
                                 query_args={'language': self.current_lang}
                            ))


    def post_template_populate(self):
        pass

    def request_hook(self):
        pass

    def get_url(self, viewname, arguments=None, query_args=None):
        arguments = arguments or {}
        query_args = query_args or {}
        query_dict = QueryDict(mutable=True)
        query_dict.update(**query_args)
        return '{url}?{query}'.format(
            url=reverse(viewname=viewname, kwargs=arguments),
            query=query_dict.urlencode()
        )



