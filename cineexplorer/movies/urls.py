from django.urls import path
from . import views

app_name = 'movies'

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search, name='search'),
    path('movie/<str:mid>/', views.movie_detail, name='movie_detail'),
    path('replica-status/', views.replica_status, name='replica_status'),
]
