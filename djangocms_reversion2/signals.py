
from cms.operations import REVERT_PAGE_TRANSLATION_TO_LIVE
from django.db.models import signals

from djangocms_reversion2.settings import ADD_VERSION_ON_PUBLISH, PROMPT_VERSION_ON_PUBLISH


def make_page_version_dirty(page, language):
    pv = page.page_versions.filter(active=True, language=language)
    if pv.count() > 0:
        pv = pv.first()
        if not pv.dirty:
            pv.dirty = True
            pv.save()


def mark_title_dirty(sender, instance, **kwargs):
    page = instance.page
    language = instance.language
    make_page_version_dirty(page, language)


def handle_placeholder_change(**kwargs):
    language = kwargs.get('language')
    placeholder = kwargs.get('placeholder')
    target_placeholder = kwargs.get('target_placeholder', None)
    page = None
    if placeholder:
        page = placeholder.page
    elif target_placeholder:
        page = target_placeholder.page

    if page:
        make_page_version_dirty(page, language)


def handle_page_publish(**kwargs):
    language = kwargs.get('language')
    page = kwargs.get('instance')
    # when the page is published create a backup automatically
    from djangocms_reversion2.models import PageVersion
    try:
        # Only trigger publish signal if not prompting for version
        if (ADD_VERSION_ON_PUBLISH and not PROMPT_VERSION_ON_PUBLISH) and not page.application_namespace:
            PageVersion.create_version(page, language,
                                       version_parent=None,
                                       title = 'auto',
                                       comment='Auto before publish')

            make_page_version_dirty(page, language)
    except AssertionError:
        # AssertionError page is not dirty
        pass


def handle_page_reverted_to_live(**kwargs):
    operation = kwargs.get('operation')
    if operation == REVERT_PAGE_TRANSLATION_TO_LIVE:
        page = kwargs.get('obj')
        from cms.models import Page
        if not type(page) == type(Page):
            return
        translation = kwargs.get('translation', None)
        if not translation:
            title = page.title_set.all()[0]
            language = title.language
        else:
            language = translation.language

        from djangocms_reversion2.models import PageVersion
        # if a page draft is replaced by the currently published page, then we have to make a backup and also
        # set the active flag correctly
        try:
            PageVersion.create_version(draft=page,
                                       language=language,
                                       version_parent=None,
                                       title='Auto - before revert',
                                       comment='Auto before revert to live',
                                       version_id=None)

            make_page_version_dirty(page, language)
        except AssertionError:
            # AssertionError page is not dirty
            pass


def handle_page_delete(sender, instance, **kwargs):
    # deleting a real page will delete all of its hidden versions
    page = instance

    for pv in page.page_versions.iterator():
        pv.hidden_page.delete()
        pv.delete()


# def delete_hidden_page(sender, **kwargs):
#     # deleting a PageVersion deletes its hidden page in the PageTree
#     # This signal handler deletes the hidden page associated to a PageVersion
#     # (reverse to on_delete=models.CASCADE)
#     # Problem was that an infinite loop can be originated
#     # if kwargs['instance'] and kwargs['instance'].hidden_page:
#     #     hidden_page = kwargs['instance'].hidden_page
#     #     try:
#     #         hidden_page.delete()
#     #     except Exception as e:
#     #         print(e)
#     pass


def connect_all_plugins():
    from cms.signals import post_placeholder_operation, post_publish, pre_obj_operation

    post_placeholder_operation.connect(handle_placeholder_change, dispatch_uid='reversion2_placeholder')
    signals.post_save.connect(mark_title_dirty, sender='cms.Title', dispatch_uid='reversion2_title')
    signals.pre_delete.connect(handle_page_delete, sender='cms.Page', dispatch_uid='reversion2_page')
    # signals.pre_delete.connect(delete_hidden_page, sender='djangocms_reversion2.PageVersion',
    #                             dispatch_uid='reversion2_page_version')
    post_publish.connect(handle_page_publish, dispatch_uid='reversion2_page_publish')
    pre_obj_operation.connect(handle_page_reverted_to_live,
                               dispatch_uid='reversion2_page_revert_to_live')

