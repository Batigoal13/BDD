from django.urls import path
from . import views

app_name = 'movies'

urlpatterns = [
    # Pages principales
    path('', views.index, name='index'),
    path('movies/', views.movies_list, name='movies_list'),
    path('movie/<str:movie_id>/', views.movie_detail, name='movie_detail'),
    path('search/', views.search, name='search'),
    path('stats/', views.stats, name='stats'),
    
    # API endpoints
    path('api/search/', views.api_search, name='api_search'),
    path('api/stats/', views.api_movie_stats, name='api_stats'),
    path('api/replica-status/', views.replica_status, name='replica_status'),
]
