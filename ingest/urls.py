from django.urls import path
from django.contrib.auth import views as auth_views
from django.urls import re_path
from . import views

app_name = 'ingest'
urlpatterns = [
    path('', views.index, name='index'),
    re_path(r'^logout/$', views.logout, name='logout'),
    re_path(r'^signup/$', views.signup, name='signup'),
    path('descriptive_metadata/<int:pk>/', views.DescriptiveMetadataDetail.as_view(), name='descriptive_metadata_detail'),
    re_path(r'^ingest/descriptive_metadata_upload/(?P<associated_collection>\d+)/$', views.descriptive_metadata_upload, name='descriptive_metadata_upload'),
    re_path(r'^descriptive_metadata_list/$', views.descriptive_metadata_list, name='descriptive_metadata_list'),
    path('collection_update/<int:pk>', views.CollectionUpdate.as_view(), name='collection_update'),
    path('collection_delete/<int:pk>', views.collection_delete, name='collection_delete'),
    path('collection/<int:pk>', views.collection_detail, name='collection_detail'),
    path('collection_data_path/<int:pk>', views.collection_data_path, name='collection_data_path'),
    re_path(r'^collection_create/$', views.collection_create, name='collection_create'),
    re_path(r'^collection_list/$', views.CollectionList.as_view(), name='collection_list'),
    re_path(r'^submit_validate_collection_list/$', views.SubmitValidateCollectionList.as_view(), name='submit_validate_collection_list'),
    re_path(r'^submit_request_collection_list/$', views.SubmitRequestCollectionList.as_view(), name ='submit_request_collection_list'),
    re_path(r'^collection_send/$', views.collection_send, name = 'collection_send'),
    re_path(r'^userModify/$', views.userModify, name = 'userModify'),
    re_path(r'^manage_projects/$', views.manageProjects, name = 'manage_projects'),
    re_path(r'^manage_collections/$', views.manageCollections, name = 'manage_collections'),
    re_path(r'pi_index/$', views.pi_index, name = 'pi_index'),
    path('project_form/', views.project_form, name = 'project_form'),
    path('create_project/', views.create_project, name = 'create_project'),
    path('view_project_people/<int:pk>', views.view_project_people, name = 'view_project_people'),
    path('new_metadata_detail/<int:pk>', views.new_metadata_detail, name = 'new_metadata_detail'),
    path('view_project_collections/<int:pk>', views.view_project_collections, name = 'view_project_collections'),
    path('no_collection/<int:pk>', views.no_collection, name = 'no_colletion'),
    path('no_people/<int:pk>', views.no_people, name = 'no_people'),
    re_path(r'list_all_users', views.list_all_users, name = 'list_all_users'),
    path('modify_user/<int:pk>', views.modify_user, name = 'modify_user'),
    path('modify_biladmin_privs/<int:pk>', views.modify_biladmin_privs, name = 'modify_biladmin_privs'),
    re_path(r'^change_bil_admin_privs/$', views.change_bil_admin_privs, name = 'change_bil_admin_privs'),
    path('add_project_user/<int:pk>', views.add_project_user, name = 'add_project_user'),
    path('people_of_pi', views.people_of_pi, name = 'people_of_pi'),
    re_path(r'^write_user_to_project_people/$', views.write_user_to_project_people, name = 'write_user_to_project_people'),
    path('collection/ondemandSubmission/<int:pk>', views.ondemandSubmission, name = 'ondemandSubmission'),
    path('submission_view', views.submission_view, name = 'submission_view'),
    path('bican_id_upload/<int:sheet_id>/', views.bican_id_upload, name='bican_id_upload'),
    path('specimen_bican/<int:sheet_id>/', views.specimen_bican, name='specimen_bican'),
    path('save_bican_ids/', views.save_bican_ids, name='save_bican_ids'),
    path('nhash_id_confirm/', views.nhash_id_confirm, name='nhash_id_confirm'),
    path('ingest/save_nhash_specimen_list/', views.save_nhash_specimen_list, name='save_nhash_specimen_list'),
    path('process_ids/', views.process_ids, name='process_ids'),
    path('save_bican_spreadsheet', views.save_bican_spreadsheet, name='save_bican_spreadsheet'),
    path('add_tags/', views.add_tags, name='add_tags'),
    path('delete_tag/', views.delete_tag, name='delete_tag'),
    path('add_tags_all/', views.add_tags_all, name='add_tags_all'),
    path('delete_tag_all/', views.delete_tag_all, name='delete_tag_all'),
]
