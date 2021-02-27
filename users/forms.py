from django import forms

from . import models


class ProfileForm(forms.ModelForm):
    """
    Form for eidting a profile.
    """

    class Meta:
        model = models.Profile
        fields = ('dark_mode',)
