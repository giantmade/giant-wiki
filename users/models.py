from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    """
    This is a user profile.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    dark_mode = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
