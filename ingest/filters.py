import django_filters

from .models import Collection


class CollectionFilter(django_filters.FilterSet):
    """ Interactively filter display locked or unlocked collecions. """

    class Meta:
        model = Collection
        fields = ['validation_status']
