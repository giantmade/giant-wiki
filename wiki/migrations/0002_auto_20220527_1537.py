# Generated by Django 3.1.7 on 2022-05-27 15:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='page',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='page',
            name='is_deprecated',
            field=models.BooleanField(default=False),
        ),
    ]
