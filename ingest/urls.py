from django.urls import path

from . import views

app_name = 'ingest'
urlpatterns = [
    path('', views.index, name='index'),
    path('<int:metadata_id>/', views.detail, name='detail'),
]

