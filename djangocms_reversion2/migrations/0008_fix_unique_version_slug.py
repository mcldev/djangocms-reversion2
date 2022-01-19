from django.db import migrations

from djangocms_reversion2.settings import VERSION_ROOT_TITLE
from djangocms_reversion2.utils import set_title_slug_and_path


def fix_unique_version_slug(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.node__site=site
    Page = apps.get_model('cms', 'Page')
    Sites = apps.get_model('sites', 'Site')

    for site in Sites.objects.all():
        try:
            version_root_pages = Page.objects.filter(title_set__title=VERSION_ROOT_TITLE,
                                                    publisher_is_draft=True,
                                                    node__site=site)
        except Page.DoesNotExist:
            # There are no version root pages, so skip this
            continue

        for page in Page.objects.filter(page_version__isnull=False).all():
            # The version page is draft only, with a published version too
            source_page = page.page_version.draft
            version_id = page.page_version.version_id
            # Convert all draft versions to correct slug/url
            for version_title_obj in page.title_set.all():
                language = version_title_obj.language
                version_root_page = version_root_pages.get(title_set__language=language)
                set_title_slug_and_path(source_page, version_root_page, version_title_obj, language, version_id)
            # Convert all published versions to correct slug/url
            for version_title_obj in page.publisher_draft.title_set.all():
                language = version_title_obj.language
                version_root_page = version_root_pages.get(title_set__language=language)
                set_title_slug_and_path(source_page, version_root_page, version_title_obj, language, version_id)


class Migration(migrations.Migration):

    dependencies = [
        ('djangocms_reversion2', '0007_auto_20180830_1549'),
    ]

    operations = [
        migrations.RunPython(fix_unique_version_slug, reverse_code=migrations.RunPython.noop),
    ]
