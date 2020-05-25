

from cms.models import Page
from cms.utils import get_language_from_request
from cms.utils.page_permissions import user_can_view_page, user_can_publish_page, user_can_change_page
from cms.utils.permissions import get_current_user
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django.urls import reverse
from django.http.response import Http404
from django.shortcuts import redirect, render_to_response, get_object_or_404, render
from django.utils.translation import ugettext_lazy as _
from sekizai.context import SekizaiContext

from djangocms_reversion2.diff import create_placeholder_contents
from djangocms_reversion2.forms import PageVersionForm
from djangocms_reversion2.models import PageVersion
from djangocms_reversion2.signals import make_page_version_dirty
from djangocms_reversion2.utils import revert_page, revise_all_pages
from djangocms_reversion2.views import view_revision


# Admin for Page Versions
# -----------------------
class PageVersionAdmin(admin.ModelAdmin):
    form = PageVersionForm
    list_display = (
        '__str__', 'date', 'user', 'comment', 'language'
    )
    list_display_links = None
    diff_view_template = 'admin/diff.html'
    view_revision_template = 'admin/view_revision.html'

    def get_urls(self):
        urls = super(PageVersionAdmin, self).get_urls()
        admin_urls = [
            url(r'^diff-view/page/(?P<page_pk>\d+)/left/(?P<left_pk>\d+)/right/(?P<right_pk>\d+)/$',self.diff_view, name='djangocms_reversion2_diff_view'),
            url(r'^revert/page/(?P<page_pk>\d+)/to/(?P<version_pk>\d+)$', self.revert, name='djangocms_reversion2_revert_page'),
            url(r'^batch-add/(?P<pk>\w+)$', self.batch_add, name='djangocms_reversion2_pagerevision_batch_add'),
            url(r'^view-revision/(?P<revision_pk>\d+)$', view_revision, name='djangocms_reversion2_view_revision'),
        ]
        return admin_urls + urls

    # Revert function to set a page to a previous version
    def revert(self, request, **kwargs):
        page_pk = kwargs.get('page_pk')
        to_version_pk = kwargs.get('version_pk')
        language = request.GET.get('language')

        page = get_object_or_404(Page, pk=page_pk)
        page_version = get_object_or_404(PageVersion, pk=to_version_pk)

        # when the page_version you want to use as target and the current page mismatch
        # -> don't know why this should happen (but we can keep it as a guard)
        if not page_version.draft == page:
            raise Http404

        # check if the current user is allowed to revert the page by checking the page publish permission
        user = get_current_user()
        if not user_can_publish_page(user, page_version.draft):
            messages.error(request, _('Missing permission to publish this page which is necessary for the rollback'))
            prev = request.META.get('HTTP_REFERER')
            if prev:
                return redirect(prev)
            else:
                raise Http404

        # Create a page_version of the page if it is dirty
        # prior to reverting
        try:
            PageVersion.create_version(page, language, version_parent=None, title='auto', comment='Auto before revert', version_id=None)
        except AssertionError as e:
            # AssertionError == page is not dirty
            pass

        revert_page(page_version, language)
        make_page_version_dirty(page, language)

        messages.info(request, _(u'You have succesfully reverted to {rev}').format(rev=page_version))
        return self.render_close_frame()

    # Not currently used - TODO
    def batch_add(self, request, **kwargs):
        # only superusers are allowed to trigger this

        user = get_current_user()
        if not user.is_superuser:
            messages.error(request, _('Only superusers are allowed to use the batch page revision creation mode'))
        else:
            num = revise_all_pages()
            messages.info(request, _(u'{num} unversioned pages have been versioned.').format(num=num))

        pk = kwargs.get('pk')
        language = request.GET.get('language')
        page = Page.objects.get(pk=pk)
        return redirect(page.get_absolute_url(language), permanent=True)

    # Display the diff between page versions
    def diff_view(self, request, **kwargs):
        # view that shows a revision on the left and one on the right
        # if the right revision has value zero: the current page is used!
        # -> page id is only necessary in the utter case
        # if the comparison_pk is zero: the latest version is used
        # comparison_pk and base_pk are primary keys for *pages*!

        # also called left_pk
        left_pk = kwargs.pop('left_pk')
        # also called right_pk
        right_pk = kwargs.pop('right_pk')
        page_pk = kwargs.pop('page_pk')

        right_page_is_active_page = True

        language = request.GET.get('language')

        left = 'page'
        right = 'page'

        # get the draft we are talking about
        page_draft = get_object_or_404(Page, pk=page_pk).get_draft_object()

        # check if the current user may view the revision
        # -> if the user may see the page
        user = get_current_user()
        if not user_can_view_page(user, page_draft):
            messages.error(request, _('Missing permission to view this page.'))
            prev = request.META.get('HTTP_REFERER')
            if prev:
                return redirect(prev)
            else:
                raise Http404

        # the right panel has id=0
        # -> use the draft of the page
        # -> else: fetch the page
        if int(right_pk) == 0:
            right_page = page_draft
            right_page_is_active_page = True
        else:
            right = 'pageVersion'
            right_page = PageVersion.objects.get(pk=right_pk)
            right_page_is_active_page = False

        # the left panel has id=0
        # -> use the latest PageVersion draft of the page
        # -> else: fetch the page
        if int(left_pk) == 0:
            page_draft_versions = PageVersion.objects.filter(draft=page_draft, active=True, language=language)\
                .order_by('-hidden_page__changed_date')[:1]

            if page_draft_versions.count() > 0:
                left_page = page_draft_versions.first()
                left = 'pageVersion'
            else:
                messages.info(request, _(u'There are no snapshots for this page'))
                return self.render_close_frame()
        else:
            left = 'pageVersion'
            left_page = PageVersion.objects.get(pk=left_pk)

        # list of page's revisions to show as the left sidebar
        revision_list = PageVersion.objects.filter(draft=page_draft, language=language)
        # group the revisions by date
        grouped_revisions = {}
        for rev in revision_list.iterator():
            key = rev.hidden_page.changed_date.strftime("%Y-%m-%d")
            if key not in grouped_revisions.keys():
                grouped_revisions[key] = []
            grouped_revisions[key].insert(0, rev)
        sorted_grouped_revisions = sorted(grouped_revisions.items(), key=lambda i: i[0], reverse=True)

        # differences between the placeholders
        if left is 'pageVersion':
            l_page = left_page.hidden_page
        else:
            l_page = left_page
        if right is 'pageVersion':
            r_page = right_page.hidden_page
        else:
            r_page = right_page

        diffs = create_placeholder_contents(l_page, r_page, request, language)

        left_page_absolute_url = left_page.hidden_page.get_draft_url(language=language)

        context = SekizaiContext({
            'left': left,
            'right': right,
            'left_page': left_page,
            'right_page': right_page,
            'is_popup': True,
            'page': page_draft.pk,
            'active_left_page_version_pk': left_page.pk,
            'request': request,
            'sorted_grouped_revisions': sorted_grouped_revisions,
            'active_language': language,
            'all_languages': page_draft.languages.split(','),
            'diffs': diffs,
            'left_page_absolute_url': left_page_absolute_url,
            'right_page_is_active_page': right_page_is_active_page
        })


        return render(request, self.diff_view_template, context=context.flatten())


    def add_view(self, request, form_url='', extra_context=None):
        language = request.GET.get('language')
        draft_pk = request.GET.get('draft')

        page = get_object_or_404(Page, pk=draft_pk)

        # check if the current user may view the revision
        # -> if the user may see the page
        user = get_current_user()
        if not user_can_change_page(user, page):
            messages.error(request, _('Missing permission to edit this page which is necessary in order to create a '
                                      'page version.'))
            prev = request.META.get('HTTP_REFERER')
            if prev:
                return redirect(prev)
            else:
                raise Http404

        if page.page_versions.filter(active=True, dirty=False, language=language).exists():
            messages.info(request, _('This page already has a saved revision.'))
            return self.render_close_frame()

        return super(PageVersionAdmin, self).add_view(request, form_url=form_url, extra_context=extra_context)

    #  This should just use the parent class?
    # def get_changeform_initial_data(self, request):
    #     initial = super(PageVersionAdmin, self).get_changeform_initial_data(request)
    #     return initial

    def do_publish_on_save(self, request):
        return request.GET.get('publish_on_save', 'False').lower() == 'true'

    def response_add(self, request, obj, post_url_continue=None):
        resp = super(PageVersionAdmin, self).response_add(request, obj, post_url_continue=post_url_continue)
        if IS_POPUP_VAR in request.POST:
            return self.render_close_frame()
        return resp

    def render_close_frame(self):
        return render_to_response('admin/close_frame.html', {})

    def get_form(self, request, obj=None, **kwargs):
        form = super(PageVersionAdmin, self).get_form(request, obj=obj, **kwargs)
        language = get_language_from_request(request)
        form.base_fields['language'].initial = language
        form.publish_on_save = self.do_publish_on_save(request)
        return form

    def get_queryset(self, request):
        qs = super(PageVersionAdmin, self).get_queryset(request)
        # # TODO review the following code
        # try:
        #     request.rev_page = getattr(request, 'rev_page', None) or Page.objects.get(pk=get_page(request))
        # except Page.DoesNotExist:
        #     request.rev_page = request.current_page
        # page = request.rev_page
        # language = get_language_from_request(request, current_page=page)
        # # page_id, language = page_lang(request)
        #
        # request.GET._mutable = True
        # request.GET.pop('cms_path', None)
        # request.GET._mutable = False
        #
        # if page:
        #     qs = qs.filter(page=page)
        # if language:
        #     qs = qs.filter(language=language)
        # qs = qs.select_related('page', 'revision')
        return qs

    def revert_link(self, obj):
        return '<a href="{url}" class="btn btn-primary">{label}</a>'.format(
            url=reverse('admin:djangocms_reversion2_revert_page', kwargs={'pk': obj.id}),
            label=_('Revert')
        )
    revert_link.short_description = _('Revert')
    revert_link.allow_tags = True

    def comment(self, obj):
        return obj.comment
    comment.short_description = _('Comment')

    def user(self, obj):
        return obj.username
    user.short_description = _('By')

    def date(self, obj):
        return obj.hidden_page.changed_date.strftime('%d.%m.%Y %H:%M')
    date.short_description = _('Date')


admin.site.register(PageVersion, PageVersionAdmin)


