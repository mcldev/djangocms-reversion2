

import datetime
from collections import defaultdict

from cms import api, constants
from cms.admin.pageadmin import PageAdmin
from cms.models import Page, Title, EmptyTitle
from cms.utils import get_language_from_request
from cms.utils import page_permissions
from cms.utils.conf import get_cms_setting
from cms.utils.i18n import (
    get_language_list,
    get_site_language_from_request,
)
from django.contrib import admin
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.sites.models import Site
from django.core.exceptions import MultipleObjectsReturned
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import get_template
from sekizai.context import SekizaiContext

from djangocms_reversion2.models import PageVersion
from djangocms_reversion2.settings import *
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from djangocms_reversion2.utils import delete_page

require_POST = method_decorator(require_POST)


# Override DjangoCMS Page Admin - remove from admin site, then re-register
# -----------------------
# admin.site._registry.pop(Page).__class__):

class PageAdmin2(PageAdmin):

    # Make page dirty if changing template - i.e. new version can be saved
    @require_POST
    def change_template(self, request, object_id):
        page = get_object_or_404(self.model, pk=object_id)
        old_template = page.template
        response = super(PageAdmin2, self).change_template(request, object_id)
        page.refresh_from_db()
        if page.template != old_template:
            page.dirty = True
        return response


    def delete_model(self, request, obj):

        # is the page already under the ~BIN folder?
        page_query = obj.get_root().title_set.filter(title__in=[BIN_ROOT_TITLE, VERSION_ROOT_TITLE])
        is_in_bin = page_query.filter(title=BIN_ROOT_TITLE).exists()
        is_version = page_query.filter(title=VERSION_ROOT_TITLE).exists()

        # if in bin -> delete it permanently
        if is_in_bin:
            obj.delete()
            return

        # Do not delete versioned pages
        if is_version:
            return

        delete_page(obj)


    def get_tree_rows(self, request, pages, language, depth=1,
                      follow_descendants=True):
        """
        Used for rendering the page tree, inserts into context everything what
        we need for single item
        """
        user = request.user
        site = self.get_site(request)
        permissions_on = get_cms_setting('PERMISSION')
        template = get_template(self.page_tree_row_template)
        is_popup = (IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET)
        languages = get_language_list(site.pk)
        user_can_add = page_permissions.user_can_add_subpage

        # -------- bin/versions --------
        lang = get_language_from_request(request)
        bin_template = get_template('admin/cms/page/tree/bin_menu.html')

        def render_page_row(page):
            page.title_cache = {trans.language: trans for trans in page.filtered_translations}

            for _language in languages:
                # EmptyTitle is used to prevent the cms from trying
                # to find a translation in the database
                page.title_cache.setdefault(_language, EmptyTitle(language=_language))

            has_move_page_permission = self.has_move_page_permission(request, obj=page)

            if permissions_on and not has_move_page_permission:
                # TODO: check if this is really needed
                metadata = '{"valid_children": False, "draggable": False}'
            else:
                metadata = ''

            # Get Bin/Version Context
            # ----------
            page_query = page.get_root().title_set.filter(title__in=[BIN_ROOT_TITLE, VERSION_ROOT_TITLE])
            is_in_bin = page_query.filter(title=BIN_ROOT_TITLE).exists()
            is_version = page_query.filter(title=VERSION_ROOT_TITLE).exists()

            if is_in_bin or is_version:
                # Get the page version associated with the hidden page
                page_version = PageVersion.objects.filter(hidden_page=page.get_draft_object(), language=lang)
                # Need this as .~VERSIONS comes up as a 'version' but doesn't have a page_version
                if page_version.exists():
                    page_version = page_version.first()

                # Use Sekizai context so we can render the page
                context = SekizaiContext({
                            'admin': self,
                            'opts': self.opts,
                            'site': site,
                            'page': page,
                            'node': page.node,
                            'ancestors': [node.item for node in page.node.get_cached_ancestors()],
                            'descendants': [node.item for node in page.node.get_cached_descendants()],
                            'request': request,
                            'lang': language,
                            'metadata': metadata,
                            'page_languages': page.get_languages(),
                            'preview_language': language,
                            'follow_descendants': follow_descendants,
                            'site_languages': languages,
                            'is_popup': is_popup,
                            # -------- bin/version settings --------
                            'has_add_page_permission': False,
                            'has_change_permission': False,
                            'has_change_advanced_settings_permission': False,
                            'has_copy_page_permission': False,
                            'has_publish_permission': False,
                            'has_move_page_permission': False,
                            'is_bin': is_in_bin,
                            'is_version': is_version,
                            'page_version': page_version,
                })
                return bin_template.render(context.flatten())

            else:
                # For 'normal' pages return default context
                context = {
                    'admin': self,
                    'opts': self.opts,
                    'site': site,
                    'page': page,
                    'node': page.node,
                    'ancestors': [node.item for node in page.node.get_cached_ancestors()],
                    'descendants': [node.item for node in page.node.get_cached_descendants()],
                    'request': request,
                    'lang': language,
                    'metadata': metadata,
                    'page_languages': page.get_languages(),
                    'preview_language': language,
                    'follow_descendants': follow_descendants,
                    'site_languages': languages,
                    'is_popup': is_popup,
                    'has_add_page_permission': user_can_add(user, target=page),
                    'has_change_permission': self.has_change_permission(request, obj=page),
                    'has_publish_permission':  self.has_publish_permission(request, obj=page),
                    'has_change_advanced_settings_permission': self.has_change_advanced_settings_permission(request, obj=page),
                    'has_move_page_permission': has_move_page_permission,
                }
                return template.render(context)

        if follow_descendants:
            root_pages = (page for page in pages if page.node.depth == depth)
        else:
            # When the tree is filtered, it's displayed as a flat structure
            root_pages = pages

        if depth == 1:
            nodes = []

            for page in pages:
                page.node.__dict__['item'] = page
                nodes.append(page.node)

            for page in root_pages:
                page.node._set_hierarchy(nodes)
                yield render_page_row(page)
        else:
            for page in root_pages:
                page.node.__dict__['item'] = page
                yield render_page_row(page)


    def actions_menu(self, request, object_id, extra_context=None):
        page = self.get_object(request, object_id=object_id)

        if page is None:
            raise self._get_404_exception(object_id)

        site = self.get_site(request)
        paste_enabled = request.GET.get('has_copy') or request.GET.get('has_cut')
        context = {
            'page': page,
            'node': page.node,
            'opts': self.opts,
            'site': site,
            'page_is_restricted': page.has_view_restrictions(site),
            'paste_enabled': paste_enabled,
            'has_add_permission': page_permissions.user_can_add_subpage(request.user, target=page),
            'has_copy_page_permission': page_permissions.user_can_view_page_draft(request.user, page, site=site),
            'has_change_permission': self.has_change_permission(request, obj=page),
            'has_change_advanced_settings_permission': self.has_change_advanced_settings_permission(request, obj=page),
            'has_change_permissions_permission': self.has_change_permissions_permission(request, obj=page),
            'has_move_page_permission':  self.has_move_page_permission(request, obj=page),
            'has_delete_permission':  self.has_delete_permission(request, obj=page),
            'CMS_PERMISSION': get_cms_setting('PERMISSION'),
        }

        # Bin/Version page
        # ----------------
        page_query = page.get_root().title_set.filter(title__in=[BIN_ROOT_TITLE, VERSION_ROOT_TITLE])
        is_in_bin = page_query.filter(title=BIN_ROOT_TITLE).exists()
        is_version = page_query.filter(title=VERSION_ROOT_TITLE).exists()

        is_version_root = (page.title_set.filter(title__in=[BIN_ROOT_TITLE, VERSION_ROOT_TITLE]) | \
                          page.title_set.filter(title__startswith='.DELETED')).exists()

        if is_in_bin or is_version:
            context.update({
                'page_is_restricted': True,
                'paste_enabled': False,
                'has_add_permission': False,
                'has_change_permission': False,
                'has_change_advanced_settings_permission': False,
                'has_change_permissions_permission': False,
                'has_copy_page_permission': not is_version_root,
                'has_move_page_permission': False,
                'has_delete_permission': False,
                'CMS_PERMISSION': False,
            })
        # ----------------

        if extra_context:
            context.update(extra_context)

        return render(request, self.actions_menu_template, context)



admin.site.unregister(Page)
admin.site.register(Page, PageAdmin2)
