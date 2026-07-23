import django_filters

from .models import Collection


class CollectionFilter(django_filters.FilterSet):

    name = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Name',
    )

    submission_status = django_filters.ChoiceFilter(
        choices=[('', 'All')] + list(Collection.STATUS_CHOICES_SUBMISSION),
        empty_label=None,
        label='Submission',
    )

    validation_status = django_filters.ChoiceFilter(
        choices=[('', 'All')] + list(Collection.STATUS_CHOICES_VALIDATION),
        empty_label=None,
        label='Validation',
    )

    class Meta:
        model = Collection
        fields = ['name', 'submission_status', 'validation_status']
