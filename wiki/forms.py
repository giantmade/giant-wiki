from django import forms
from django.core.files.storage import default_storage

from . import models


class PageForm(forms.ModelForm):
    """
    Form for creating and editing pages.
    """

    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}), required=False)

    class Meta:
        model = models.Page
        fields = ("path", "content", "files", "is_deprecated")
        widgets = {
            "path": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        if not self.request.user:
            return

        instance = super().save(commit=False)
        instance.last_edited_by = self.request.user

        if commit:
            instance.save()

        if files := self.request.FILES.getlist("files"):
            for file in files:
                file_path = default_storage.save(f'page_files/{file.name}', file)
                models.FileUpload.objects.create(
                    page=instance, file=file_path,
                )

        return instance
