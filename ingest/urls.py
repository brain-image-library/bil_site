from django.urls import path, re_path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'ingest'
urlpatterns = [
    path('', views.index, name='index'),
    re_path(r'^logout/$', views.logout, name='logout'),
    re_path(r'^signup/$', views.signup, name='signup'),
    path('descriptive_metadata/<int:pk>/', views.DescriptiveMetadataDetail.as_view(), name='descriptive_metadata_detail'),
    re_path(r'^descriptive_metadata_upload/$', views.descriptive_metadata_upload, name='descriptive_metadata_upload'),
    re_path(r'^descriptive_metadata_list/$', views.descriptive_metadata_list, name='descriptive_metadata_list'),
    path('collection_update/<int:pk>', views.CollectionUpdate.as_view(), name='collection_update'),
    path('collection_delete/<int:pk>', views.collection_delete, name='collection_delete'),
    path('collection/<int:pk>', views.collection_detail, name='collection_detail'),
    path('collection_data_path/<int:pk>', views.collection_data_path, name='collection_data_path'),
    path('collection_validation_results/<int:pk>', views.collection_validation_results, name='collection_validation_results'),
    path('collection_submission_results/<int:pk>', views.collection_submission_results, name='collection_submission_results'),
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
    path('collection/ondemandSubmission/<int:pk>', views.ondemandSubmission, name = 'ondemandSubmission')
]
