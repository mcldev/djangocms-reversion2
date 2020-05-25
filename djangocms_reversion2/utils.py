
from __future__ import unicode_literals

import datetime

from cms import api, constants
from cms.api import publish_page
from cms.constants import PUBLISHER_STATE_DIRTY, PUBLISHER_STATE_PENDING
from cms.exceptions import PublicIsUnmodifiable
from cms.models import Page, Title
from django.conf import settings
from django.db import IntegrityError
from django.template.defaultfilters import slugify

from .settings import VERSION_ROOT_TITLE, VERSION_START_VALUE, BIN_ROOT_TITLE, PUBLISH_HIDDEN_PAGE, \
    ADD_VERSION_ON_PUBLISH, \
    BATCH_ADD_UNVERSIONED_ONLY, BIN_BUCKET_NAMING, BIN_PAGE_LANGUAGE


def copy_page(page,
              parent_page,
              version_id=None,
              language=None,
              include_descendants=False):

    if include_descendants:
        new_page = page.copy_with_descendants(target_node=parent_page.node,
                                              position='last-child',
                                              copy_permissions=False,
                                              target_site=page.node.site)
    else:
        new_page = page.copy(
            site=page.node.site,
            parent_node=parent_page.node,
            language=language,
            translations=True,
            permissions=False,
            extensions=True)

    # Get translations i.e. on delete it's all languages, on version only 1
    if language:
        translations = new_page.title_set.filter(language=language)
    else:
        translations = new_page.title_set.all()

    # copy titles of this page
    for title in translations:
        title_slug = page.get_slug(language=language)

        new_slug = get_hidden_page_slug(title_slug, language, version_id)

        base = parent_page.get_path(language)
        new_path = '%s/%s' % (base, new_slug) if base else title.slug
        title.slug = new_slug
        title.path = new_path
        title.save()

    new_page.in_navigation = False
    new_page.save()

    new_page.clear_cache(menu=True)

    return new_page


def get_or_create_version_page_root(site, user, language=settings.LANGUAGES[0][0]):
    try:
        version_page = Page.objects.get(title_set__title=VERSION_ROOT_TITLE,
                                        publisher_is_draft=True,
                                        node__site=site)
    except Page.DoesNotExist:
        version_page = api.create_page(VERSION_ROOT_TITLE,
                                       constants.TEMPLATE_INHERITANCE_MAGIC,
                                       language,
                                       site=site)
        version_page.clear_cache(menu=False)

    if PUBLISH_HIDDEN_PAGE and not version_page.get_public_object():
        # Need to publish parent page to allow child pages to be published
        published_page = api.publish_page(version_page, user, language)
        if not published_page.get_public_object():
            raise Exception('Error Publishing Version Root Page!')
        published_page.clear_cache(menu=False)

    return version_page


def get_or_create_bin_page_root(site):
    # Retrieve the bin page or create it
    try:
        bin_root_page = Page.objects.get(title_set__title=BIN_ROOT_TITLE,
                                         node__site=site)
    except Page.DoesNotExist:
        bin_root_page = api.create_page(BIN_ROOT_TITLE,
                                        constants.TEMPLATE_INHERITANCE_MAGIC,
                                        language=BIN_PAGE_LANGUAGE,
                                        site=site)
        bin_root_page.clear_cache(menu=False)
    except Page.MultipleObjectsReturned:
        bin_root_page = Page.objects.filter(title_set__title=BIN_ROOT_TITLE,
                                            node__site=site).first()

    # Get the sub-bin page
    bucket_title = datetime.datetime.now().strftime(BIN_BUCKET_NAMING)
    try:
        bin_page = Page.objects.get(title_set__title=bucket_title,
                                    node__site=site)
    except Page.DoesNotExist:
        bin_page = api.create_page(bucket_title,
                                   constants.TEMPLATE_INHERITANCE_MAGIC,
                                   BIN_PAGE_LANGUAGE,
                                   parent=bin_root_page,
                                   site=site)
        bin_page.clear_cache(menu=False)

    return bin_page


def get_hidden_page_slug(slug, language, version_id):
    return slugify('{slug}-{lang}-{ver}'.format(slug=slug,
                                                lang=language,
                                                ver=str(version_id).replace('.', '-')))


def revise_page(page, language, user, version_id=None):
    """
    Copy a page [ and all its descendants to a new location ]
    Doesn't checks for add page permissions anymore, this is done in PageAdmin.

    Note for issue #1166: when copying pages there is no need to check for
    conflicting URLs as pages are copied unpublished.
    --> get_queryset_by_path(...).get() will fail
    """
    if not page.publisher_is_draft:
        raise PublicIsUnmodifiable("revise page is not allowed for public pages")

    # if the active version is not dirty -> do not create a revision
    if page.page_versions.filter(active=True, dirty=False, language=language).count() > 0:
        return None

    # Error if the parent isn't published...
    if PUBLISH_HIDDEN_PAGE and \
            page.publisher_public_id and \
            page.publisher_public.get_publisher_state(language) == PUBLISHER_STATE_PENDING or \
            page.get_publisher_state(language) == PUBLISHER_STATE_PENDING:
        raise Exception('Parent Page is not published')

    # avoid muting input param
    page = Page.objects.get(pk=page.pk)

    # Get Version root page
    site = page.node.site
    version_page_root = get_or_create_version_page_root(site=site, user=user)

    # create a copy of this page
    new_page = copy_page(page, version_id=version_id, parent_page=version_page_root, language=language)

    # Publish the page if required
    if PUBLISH_HIDDEN_PAGE:
        new_page = publish_page(new_page, user, language)

    # invalidate the menu for this site
    new_page.clear_cache(menu=True)

    print('Created new version {ver} for: "{page}"'.format(ver=version_id, page=new_page.get_title(language=language)))

    return new_page


def delete_page(page):
    # avoid muting input param
    page = Page.objects.get(pk=page.pk)

    # Get site and bucket page
    site = page.node.site
    bin_page_root = get_or_create_bin_page_root(site=site)

    # create a copy of this page
    new_page = page.move_page(target_node=bin_page_root.node, position='last-child')

    # invalidate the menu for this site
    new_page.in_navigation = False
    new_page.save()

    new_page.clear_cache(menu=True)

    print('Created copy of deleted page: "{page}"'.format(page=new_page.get_title(language=settings.LANGUAGES[0][0])))

    return new_page


def revert_page(page_version, language):
    from .models import PageVersion
    # copy all relevant attributes from hidden_page to draft
    source = page_version.hidden_page
    target = page_version.draft

    _copy_titles(source, target, language)
    source._copy_contents(target, language)

    source._copy_attributes(target)

    PageVersion.objects.filter(draft=page_version.draft, language=language).update(active=False)
    page_version.active = True
    page_version.dirty = False
    page_version.save()


def _copy_titles(source, target, language):
    """
    Copy all the titles to a new page (which must have a pk).
    The title has a published attribute that needs to be set to false.
        There is also the publisher_is_draft attribute
    :param target: The page where the new titles should be stored
    """

    assert source.publisher_is_draft
    assert target.publisher_is_draft

    old_titles = dict(target.title_set.filter(language=language).values_list('language', 'pk'))
    for title in source.title_set.filter(language=language):

        # If an old title exists, overwrite. Otherwise create new
        target_pk = old_titles.pop(title.language, None)
        title.pk = target_pk
        title.page = target

        # target fields that we keep
        target_title = Title.objects.get(pk=target_pk) if target_pk else None
        title.slug = getattr(target_title, 'slug', '')
        title.path = getattr(target_title, 'path', '')
        title.has_url_overwrite = getattr(target_title, 'has_url_overwrite', False)
        title.redirect = getattr(target_title, 'redirect', None)
        title.publisher_public_id = getattr(target_title, 'publisher_public_id', None)
        # has to be false
        title.published = getattr(target_title, 'published', False)

        # dirty since we are overriding current draft
        title.publisher_state = PUBLISHER_STATE_DIRTY

        title.save()

    if old_titles:
        Title.objects.filter(id__in=old_titles.values()).delete()


def is_version_page(page):
    from .models import PageVersion
    return PageVersion.objects.filter(hidden_page=page).exists()


def get_draft_of_version_page(page):
    return page.page_version.draft


def revise_all_pages():

    raise Exception('''TODO - 
                        1. French versions are not getting labels correctly??
                        2. Copy/repace this function with a prompt for version and initial revision i.e. OAT Versions
                        3. Spinning wheel when publishing > close modal on complete
                        ''')



    """
    Revise all pages (exclude the bin and versioned pages)
    :return: number of created revisions
    """
    from .models import PageVersion
    num = 0
    integrity_errors = 0

    # Exclude Version Pages
    get_pages_to_version = Page.objects.all().exclude(title_set__title=BIN_ROOT_TITLE).exclude(
                                             parent__title_set__title=BIN_ROOT_TITLE).exclude(
                                             parent__title_set__title=VERSION_ROOT_TITLE)
    # Get published pages only
    if ADD_VERSION_ON_PUBLISH:
        get_pages_to_version.filter(published = True, parent__published=True)

    for page in get_pages_to_version.iterator():
        draft = page.get_draft_object()

        for language in page.languages.split(','):

            # Skip if the page already has a version
            if draft.page_versions.filter(language=language).exists() and BATCH_ADD_UNVERSIONED_ONLY:
                continue
            try:
                try:
                    # this is necessary, because an IntegrityError makes a rollback necessary
                    #with transaction.atomic():
                    PageVersion.create_version(draft=draft,
                                               language=language,
                                               version_parent=None,
                                               title='Initial',
                                               comment='Initial Revision - batch created',
                                               version_id=VERSION_START_VALUE)
                except IntegrityError as e:
                    print("Integrity Error - {}".format(e))
                    integrity_errors += 1
                else:
                    print("num: {}, \ti:{}".format(num, integrity_errors))
                    num += 1
            except AssertionError as a:
                print("Assertion Error - {}".format(a))
                pass
    print('integrity_errors: {}'.format(integrity_errors))
    return num


