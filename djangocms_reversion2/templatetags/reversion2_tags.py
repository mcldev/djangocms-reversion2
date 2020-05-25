from django import template

from djangocms_reversion2.settings import BIN_ROOT_TITLE, VERSION_ROOT_TITLE
from djangocms_reversion2.models import PageVersion
from djangocms_reversion2.utils import get_draft_of_version_page

register = template.Library()


@register.inclusion_tag("djangocms_reversion2/tags/page_version_list.html", takes_context=True)
def page_version_list(context):
    request = context['request']
    current_page = request.current_page.get_draft_object()
    language = request.LANGUAGE_CODE
    page_versions = current_page.page_versions.filter(language=language).order_by('-id')
    if page_versions.exists():
        return {
            'page_versions': page_versions,
        }

@register.simple_tag(takes_context=True)
def page_versions(context, hidden_page=None, draft=None):
    request = context['request']
    language = request.LANGUAGE_CODE
    if not draft and not hidden_page:
        draft = request.current_page.get_draft_object()
    page_versions = PageVersion.get_versions(language, hidden_page=hidden_page, draft=draft)
    if page_versions.exists():
        return page_versions


@register.simple_tag(takes_context=True)
def has_page_versions(context):
    request = context['request']
    current_page = request.current_page.get_draft_object()
    language = request.LANGUAGE_CODE
    page_versions = current_page.page_versions.filter(language=language).order_by('-id')
    return page_versions.exists()


@register.simple_tag(takes_context=True)
def current_page_version(context):
    request = context['request']
    current_page = request.current_page.get_draft_object()
    page_version = PageVersion.objects.filter(hidden_page=current_page)
    if page_version.exists():
        return page_version.first()

