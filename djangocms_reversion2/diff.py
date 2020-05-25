import re

from bs4 import BeautifulSoup
from cms.models import Placeholder
from cms.plugin_rendering import ContentRenderer
from sekizai.context import SekizaiContext
from .settings import REVERSION2_DIFF_TEXT_ONLY, REVERSION2_IGNORE_WHITESPACE

# import diff_match_patch as dmp
# from tablib.packages import markup


def revert_escape(txt, transform=True):
    """
    transform replaces the '<ins ' or '<del ' with '<div '
    :type transform: bool
    """
    html = txt.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&para;<br>", "\n")
    if transform:
        html = html.replace('<ins ', '<div ').replace('<del ', '<div ').replace('</ins>', '</div>')\
            .replace('</del>', '</div>')
    return html


def create_placeholder_contents(left_page, right_page, request, language):
    # persist rendered html content for each placeholder for later use in diff
    placeholders_a = Placeholder.objects.filter(page=left_page.pk).order_by('slot')
    placeholders_b = Placeholder.objects.filter(page=right_page.pk).order_by('slot')
    slots = set()
    for p in placeholders_a or placeholders_b:
        slots.add(p.slot)
    placeholders = {x: (placeholders_a.get(slot=x) if placeholders_a.filter(slot=x).exists() else None,
                        placeholders_b.get(slot=x) if placeholders_b.filter(slot=x).exists() else None)
                    for x in slots}
    diffs = {}
    for key, (p1, p2) in placeholders.items():
        body1 = placeholder_html(p1, request, language)
        body2 = placeholder_html(p2, request, language)
        diff = diff_texts(body1, body2)
        diffs[key] = {'left': body1, 'right': body2,
                      'diff_right_to_left': diff}

    return diffs


def placeholder_html(placeholder, request, language):
    if not placeholder:
        return ''
    if hasattr(placeholder, '_plugins_cache'):
        del placeholder._plugins_cache

    renderer = ContentRenderer(request)
    context = SekizaiContext({
        'request': request,
        'cms_content_renderer': renderer,
        'CMS_TEMPLATE': placeholder.page.get_template
    })

    return renderer.render_placeholder(placeholder, context, language=language).strip()


def diff_texts(text1, text2):
    # differ = dmp.diff_match_patch()

    # Remove HTML tags and duplicate \n if specified (helps to ignore diff plugin ids)
    if REVERSION2_DIFF_TEXT_ONLY:
        text1 = BeautifulSoup(text1, features="lxml").get_text()
        text2 = BeautifulSoup(text2, features="lxml").get_text()

    if REVERSION2_IGNORE_WHITESPACE:
        text1 = re.sub(r'\n+', '\n', text1).strip()
        text2 = re.sub(r'\n+', '\n', text2).strip()

    # diffs = differ.diff_main(text1, text2)
    # differ.diff_cleanupEfficiency(diffs)
    #
    # diffs = revert_escape(differ.diff_prettyHtml(diffs))

    from lxml.html.diff import htmldiff
    diffs = htmldiff(text1, text2)

    return diffs


