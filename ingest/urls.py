from django.urls import path
from django.conf.urls import url
from django.contrib.auth import views as auth_views

from . import views

app_name = 'ingest'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    path('new/', views.post_new, name='post_new'),
    url(r'^signup/$', views.signup, name='signup'),
    url(r'^login/$', auth_views.login, {'template_name': 'ingest/login.html'}, name='login'),
    url(r'^logout/$', auth_views.logout, {'template_name': 'ingest/logged_out.html'}, name='logout'),

]
