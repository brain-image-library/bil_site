from django.urls import path

from . import views

urlpatterns = [
    # ex: /ingest/
    path('', views.index, name='index'),
    # ex: /ingest/5/
    path('<int:metadata_id>/', views.detail, name='detail'),
]
