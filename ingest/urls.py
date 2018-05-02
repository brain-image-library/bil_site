from django.urls import path
from django.conf.urls import re_path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'ingest'
urlpatterns = [
    path('collection_update/<int:pk>', views.CollectionUpdate.as_view(), name='collection_update'),
    path('collection_delete/<int:pk>', views.CollectionDelete.as_view(), name='collection_delete'),
    path('collection/<int:pk>', views.CollectionDetail.as_view(), name='collection_detail'),
    path('metadata/<int:pk>/', views.MetadataDetail.as_view(), name='metadata_detail'),
    path('metadata_update/<int:pk>/', views.ImageMetadataUpdate.as_view(), name='metadata_update'),
    path('metadata_delete/<int:pk>/', views.ImageMetadataDelete.as_view(), name='metadata_delete'),
    re_path(r'^submit_collection/$', views.submit_collection, name='submit_collection'),
    re_path(r'^submit_metadata/$', views.submit_metadata, name='submit_metadata'),
    re_path(r'^signup/$', views.signup, name='signup'),
    re_path(r'^login/$', auth_views.login, {'template_name': 'ingest/login.html'}, name='login'),
    re_path(r'^logout/$', auth_views.logout, {'template_name': 'ingest/logged_out.html'}, name='logout'),
    re_path(r'^index/$', views.index, name='index'),
    re_path(r'^metadata_list/$', views.metadata_list, name='metadata_list'),
    re_path(r'^collection_list/$', views.collection_list, name='collection_list')
]
