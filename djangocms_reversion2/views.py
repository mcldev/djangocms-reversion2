from cms.utils.page_permissions import user_can_view_page
from cms.utils.permissions import get_current_user
from django.http import Http404
from django.shortcuts import render, redirect
# Create your views here.
from sekizai.context import SekizaiContext

from djangocms_reversion2.models import PageVersion

VIEW_REVISION_TEMPLATE = 'djangocms_reversion2/view_revision.html'


def view_revision(request, **kwargs):
    # render a page for a popup in an old revision
    revision_pk = kwargs.pop('revision_pk')
    language = request.GET.get('language')
    page_version = PageVersion.objects.get(id=revision_pk)

    # check if the current user may view the revision
    # -> if the user may see the page
    user = get_current_user()
    if not user_can_view_page(user, page_version.draft):
        prev = request.META.get('HTTP_REFERER')
        if prev:
            return redirect(prev)
        else:
            raise Http404

    page_absolute_url = page_version.hidden_page.get_draft_url(language=language)

    context = SekizaiContext({
        'render_page': page_version.hidden_page,
        'page_version': page_version,
        'is_popup': False,
        'request': request,
        'page_absolute_url': page_absolute_url
    })

    return render(request, VIEW_REVISION_TEMPLATE, context=context.flatten())
