from django import forms

from . import models

class PageForm(forms.ModelForm):
    """
    Form for creating and editing pages.
    """

    class Meta:
        model = models.Page
        fields = ('path', 'content', 'is_deprecated', 'is_deleted')