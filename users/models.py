from django.db import models
from django.contrib.auth.models import User
from django.core.validators import validate_email

class Profile(models.Model):
    """
    This is a user profile.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    dark_mode = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
