from django.urls import path
from django.conf.urls import re_path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'ingest'
urlpatterns = [
    # Main/home page
    path('', views.index, name='index'),
    # The signup should probably be moved somewhere else.
    re_path(r'^signup/$', views.signup, name='signup'),
    # All the image data pages
    re_path(r'^create_image_upload_area/$', views.create_image_upload_area, name='create_image_upload_area'),
    re_path(r'^image_data_dirs_list/$', views.image_data_dirs_list, name='image_data_dirs_list'),
    path('image_data/<int:pk>/', views.ImageDataDetail.as_view(), name='image_data_dirs_detail'),
    path('image_data_delete/<int:pk>/', views.ImageDataDelete.as_view(), name='image_data_delete'),
    # All the image metadata pages
    path('metadata/<int:pk>/', views.ImageMetadataDetail.as_view(), name='image_metadata_detail'),
    path('metadata_update/<int:pk>/', views.ImageMetadataUpdate.as_view(), name='image_metadata_update'),
    path('metadata_delete/<int:pk>/', views.ImageMetadataDelete.as_view(), name='image_metadata_delete'),
    re_path(r'^submit_metadata/$', views.submit_image_metadata, name='submit_image_metadata'),
    re_path(r'^upload_metadata/$', views.upload_image_metadata, name='upload_image_metadata'),
    re_path(r'^metadata_list/$', views.image_metadata_list, name='image_metadata_list'),
    # All the collection pages.
    path('collection_update/<int:pk>', views.CollectionUpdate.as_view(), name='collection_update'),
    path('collection_delete/<int:pk>', views.CollectionDelete.as_view(), name='collection_delete'),
    path('collection/<int:pk>', views.CollectionDetail.as_view(), name='collection_detail'),
    re_path(r'^submit_collection/$', views.submit_collection, name='submit_collection'),
    re_path(r'^collection_list/$', views.collection_list, name='collection_list')
]
