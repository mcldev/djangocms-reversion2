

from cms import constants
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils.encoding import python_2_unicode_compatible, force_text
from django.utils.translation import ugettext_lazy as _
from six import string_types
from treebeard.mp_tree import MP_Node
from versionfield import VersionField

from djangocms_reversion2.settings import ALLOW_BLANK_TITLE
from .utils import revise_page


@python_2_unicode_compatible
class PageVersion(MP_Node):
    hidden_page = models.OneToOneField('cms.Page', on_delete=models.CASCADE, verbose_name=_('Hidden Page'),
                                       related_name='page_version', help_text=_('This Page object holds the versioned '
                                                                                'contents of this PageVersion.'))
    draft = models.ForeignKey('cms.Page', on_delete=models.CASCADE, verbose_name=_('Draft'),
                              related_name='page_versions', help_text=_('Current active draft.'))

    version_id = VersionField(verbose_name=_("Version Id"), null=True, blank=True)
    title = models.CharField(_('Version Title'), blank=True, max_length=63)
    comment = models.TextField(_('Version Comment'), blank=True, help_text=_('Particular information concerning this Version'))

    active = models.BooleanField(_('Active'), default=False,
                                 help_text=_('This the active version of current draft. There can be only one such '
                                             'version per Page version tree.'))
    dirty = models.BooleanField(_('Dirty'), default=False,
                                help_text=_('Only new PageVersions are not dirty of if a page has been reverted to a '
                                            'PageVersion.'))
    language = models.CharField(_('Language'), blank=True, max_length=20)
    owner = models.CharField(_("owner"), max_length=constants.PAGE_USERNAME_MAX_LENGTH, editable=False, default='script')

    @property
    def get_title(self):
        return self.hidden_page.get_title(self.language)

    @property
    def get_full_title(self):
        return '{page} - {lang} [{ver} - {title}]'.format(page=self.get_title,
                                                          lang=self.language,
                                                          ver=self.version_id,
                                                          title=self.title[:30])

    @property
    def get_revision_view_url(self):
        return reverse('djangocms_reversion2:view_revision2', kwargs={'revision_pk': self.id})

    @property
    def get_revision_public_url(self):
        if self.hidden_page and self.hidden_page.get_public_object():
            return self.hidden_page.get_public_url(language=self.language)

    @property
    def get_draft_url(self):
        return self.draft.get_draft_url(language=self.language)

    @property
    def get_draft_public_url(self):
        return self.draft.get_public_url(language=self.language)

    @property
    def latest_version(self):
        latest_version = PageVersion.get_latest_version(language=self.language, draft=self.draft)
        if latest_version and latest_version.version_id:
            return latest_version

    @property
    def is_latest_version(self):
        return self == self.latest_version


    # Main Class Queries here
    # -----------------------
    @classmethod
    def get_versions(cls, language, hidden_page=None, draft=None, order_by='-id'):
        if hidden_page and not draft:
            page_versions = cls.objects.filter(hidden_page=hidden_page.get_draft_object(), language=language)
            if page_versions.exists():
                draft = page_versions.first().draft
        if draft and hasattr(draft,'get_draft_object'):
            draft = draft.get_draft_object()
        if draft:
            return cls.objects.filter(draft=draft, language=language).order_by(order_by)

    @classmethod
    def get_latest_version(cls, language, hidden_page=None, draft=None):
        page_versions = cls.get_versions(language, hidden_page=hidden_page, draft=draft)
        if page_versions and page_versions.exists():
            return page_versions.first()

    @classmethod
    def get_latest_version_id(cls, language, hidden_page=None, draft=None):
        latest_version = cls.get_latest_version(language, hidden_page=hidden_page, draft=draft)
        if latest_version and latest_version.version_id:
            return latest_version.version_id


    # Main Method to create a version
    # -------------------------------
    @classmethod
    def create_version(cls, draft, language, version_parent=None, comment='', title='', version_id=None):
        if draft.page_versions.filter(active=True, dirty=False, language=language).count() > 0:
            raise AssertionError('not dirty')

        # Check that title is included if required -
        if not title and not ALLOW_BLANK_TITLE:
            raise AssertionError('Version Title cannot be blank')

        # owner of the PageVersion is the last editor
        from cms.utils.permissions import get_current_user
        user = get_current_user()
        if user:
            try:
                owner = force_text(user)
            except AttributeError:
                # AnonymousUser may not have USERNAME_FIELD
                owner = "anonymous"
            else:
                # limit changed_by and created_by to avoid problems with Custom User Model
                if len(owner) > constants.PAGE_USERNAME_MAX_LENGTH:
                    owner = u'{0}... (id={1})'.format(owner[:constants.PAGE_USERNAME_MAX_LENGTH - 15], user.pk)
        else:
            owner = "script"

        if isinstance(user, string_types):
            from cms.models import User
            user = User.objects.get(username=user)

        hidden_page = revise_page(draft, language, user, version_id)

        if not version_parent and draft.page_versions.filter(language=language).exists():
            version_parent = draft.page_versions.get(active=True, language=language)

        if version_parent:
            page_version = version_parent.add_child(hidden_page=hidden_page, draft=draft, comment=comment, title=title,
                                                    version_id=version_id,
                                                    active=version_parent.active, language=language, owner=owner)
            version_parent.deactivate()
        else:
            page_version = PageVersion.add_root(hidden_page=hidden_page, draft=draft, comment=comment, title=title,
                                                version_id=version_id,
                                                active=True, language=language, owner=owner)

        return page_version

    def save(self, **kwargs):
        self.title = self.title or self.generate_title()
        self.comment = self.comment or self.generate_comment()
        super(PageVersion, self).save(**kwargs)

    def generate_title(self):
        return ''

    def generate_comment(self):
        return ''

    @property
    def username(self):
        return self.hidden_page.changed_by

    def deactivate(self, commit=True):
        self.active = False
        if commit:
            self.save()
    deactivate.alters_data = True

    def __str__(self):
        if self.title:
            return self.title
        return self.hidden_page.get_title()

    class Meta:
        # example: user.has_perm('djangocms_reversion2.view_page_version')
        # permissions = (
        #     ('view_page_version', _('permission to view the page version')),
        #     ('delete_page_version', _('permission to delete the page version')),
        #     ('create_page_version', _('permission to create the page version')),
        #     ('edit_page_version', _('permission to edit a page version')),
        #     ('revert_to_page_version', _('permission to revert a page to the page version')),
        # )
        default_permissions = () #'add', 'change', 'delete')

