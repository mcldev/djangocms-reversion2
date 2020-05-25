
from __future__ import unicode_literals

from cms.api import publish_page
from cms.models import User
from django import forms
from six import string_types
from versionfield.widgets import VersionWidget

from djangocms_reversion2.settings import VERSION_START_VALUE, ALLOW_BLANK_TITLE, BIN_ROOT_TITLE, \
    VERSION_ROOT_TITLE, ALLOW_VERSION_EDIT
from djangocms_reversion2.models import PageVersion


class PageVersionForm(forms.ModelForm):

    class Meta:
        model = PageVersion
        fields = ['version_id', 'title', 'comment', 'draft', 'language']
        widgets = {
            'draft': forms.HiddenInput(),
            'language': forms.HiddenInput(),
            'version_id': VersionWidget(attrs={'readonly': not ALLOW_VERSION_EDIT})
        }

    def __init__(self, *args, **kwargs):
        super(PageVersionForm, self).__init__(*args, **kwargs)

        # Set Title as required
        if not ALLOW_BLANK_TITLE:
            self.fields['title'].required = True

        # Get Latest Version Id
        if kwargs.get('initial'):
            draft_page = kwargs.get('initial').get('draft')
            language = kwargs.get('initial').get('language')
            latest_version = PageVersion.get_latest_version_id(language=language, draft=draft_page) or VERSION_START_VALUE
            if latest_version:
                  self.fields['version_id'].initial = str(latest_version)

    def save(self, commit=True):
        self.save_m2m = lambda: None
        data = self.cleaned_data

        version_id = data.get('version_id', '')
        title = data.get('title', '')
        comment = data.get('comment', '')
        draft = data['draft']
        language = data.get('language', '')

        # Detect case when editing version
        is_version_page = draft.get_root().title_set.filter(title__in=[BIN_ROOT_TITLE, VERSION_ROOT_TITLE]).exists()
        if not is_version_page:

            # Publish page first...
            if hasattr(self, 'publish_on_save') and self.publish_on_save:
                from cms.utils.permissions import get_current_user
                user = get_current_user()
                if isinstance(user, string_types):
                    user = User.objects.get(username=user)
                publish_page(draft, user, language)

            # Create Version second...
            return PageVersion.create_version(draft, language,
                                              version_parent=None,
                                              comment=comment,
                                              title=title,
                                              version_id=version_id)

    def clean(self):
        self.cleaned_data = super(PageVersionForm, self).clean()
        # Check Latest Version is incremented
        latest_version = PageVersion.get_latest_version_id(language=self.data['language'], draft=self.data['draft'])
        if latest_version and 'version_id' in self.cleaned_data:
            new_version =  self.cleaned_data['version_id']
            if latest_version >= new_version:
                raise forms.ValidationError("Version Id is not increased")
