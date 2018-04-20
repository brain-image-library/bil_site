from django.urls import path
from django.conf.urls import url

from . import views

app_name = 'ingest'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    path('new/', views.post_new, name='post_new'),
    url(r'^signup/$', views.signup, name='signup')
    #path('signup/', views.signup, name='signup')
]
