from django.urls import path
from django.conf.urls import re_path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'ingest'
urlpatterns = [
    path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    re_path(r'^new/$', views.post_new, name='post_new'),
    re_path(r'^signup/$', views.signup, name='signup'),
    re_path(r'^login/$', auth_views.login, {'template_name': 'ingest/login.html'}, name='login'),
    re_path(r'^logout/$', auth_views.logout, {'template_name': 'ingest/logged_out.html'}, name='logout'),
    re_path(r'^index/$', views.index, name='index'),
    re_path(r'^metadata_list/$', views.metadata_list, name='metadata_list'),
]
