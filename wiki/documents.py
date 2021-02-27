from django_elasticsearch_dsl import Document
from django_elasticsearch_dsl.registries import registry
from .models import Page


@registry.register_document
class PageDocument(Document):
    class Index:
        name = 'pages'
        settings = {'number_of_shards': 1,
                    'number_of_replicas': 0}

    class Django:
        model = Page 
        fields = [
            'content',
        ]
