from django.test import TestCase, Client
from django.urls import reverse

from . import models


class RegistrationTestCase(TestCase):
    """
    This tests the registration process.
    """

    def setUp(self):
        self.client = Client()

    def test_registration_view(self):
        response = self.client.get(reverse("register"))

        self.assertContains(response, "<form")
        self.assertEqual(response.status_code, 200)

    def test_invalid_registration_post(self):
        response = self.client.post(reverse("register"), {})

        self.assertContains(response, "error")

    def test_valid_registration_post(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "foobar",
                "password_1": "buzzwiggle",
                "password_2": "buzzwiggle",
            },
        )

        self.assertEqual(response.status_code, 200)

    def test_valid_user_created(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "foobar1",
                "email": "test@example.com",
                "password_1": "buzzwiggle",
                "password_2": "buzzwiggle",
            },
        )

        u = models.User.objects.get(username="foobar1")

        self.assertNotEqual(u, False)
        self.assertNotEqual(u, None)

    def test_duplicated_username_error(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "foobar1",
                "email": "test@example.com",
                "password_1": "buzzwiggle",
                "password_2": "buzzwiggle",
            },
        )

        users = models.User.objects.filter(username="foobar1")
        self.assertEqual(len(users), 1)

        response2 = self.client.post(
            reverse("register"),
            {
                "username": "foobar1",
                "email": "test@example.com",
                "password_1": "buzzwiggle",
                "password_2": "buzzwiggle",
            },
        )

        self.assertContains(response2, "That username is in use")

        users = models.User.objects.filter(username="foobar1")
        self.assertEqual(len(users), 1)

    def test_different_passwords(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "foobar2",
                "password_1": "buzzwiggle",
                "password_2": "buzzwiggle2",
            },
        )

        users = models.User.objects.filter(username="foobar2")
        self.assertEqual(len(users), 0)

        self.assertContains(response, "Your passwords do not match")

    def test_missing_passwords(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "foobar3",
                "password_1": "buzzwiggle",
                "password_2": "wigglebuzz",
            },
        )

        users = models.User.objects.filter(username="foobar3")
        self.assertEqual(len(users), 0)

        self.assertContains(response, "Your passwords do not match")
