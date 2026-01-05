from django.shortcuts import render
from django.http import JsonResponse
from movies.services import sqlite_service, mongo_service


def index(request):
    """Vue d'accueil avec statistiques des deux bases."""
    try:
        mongo_stats = {
            'movie_count': mongo_service.get_movie_count(),
            'person_count': mongo_service.get_person_count(),
            'collections': mongo_service.get_collection_stats(),
        }
        replica_status = mongo_service.get_replica_status()
    except Exception as exc:
        mongo_stats = {'movie_count': 0, 'person_count': 0, 'collections': {}, 'error': str(exc)}
        replica_status = {'ok': 0, 'error': str(exc)}

    context = {
        'sqlite_stats': {
            'movie_count': sqlite_service.get_movie_count(),
            'person_count': sqlite_service.get_person_count(),
            'rating_stats': sqlite_service.get_rating_stats(),
        },
        'mongo_stats': mongo_stats,
        'replica_status': replica_status,
    }
    return render(request, 'movies/index.html', context)


def search(request):
    """Recherche de films dans les deux bases."""
    query = request.GET.get('q', '')
    source = request.GET.get('source', 'sqlite')  # sqlite ou mongo
    
    if not query:
        return JsonResponse({'error': 'Query parameter required'}, status=400)
    
    if source == 'mongo':
        results = mongo_service.search_movies(query, limit=20)
    else:
        results = sqlite_service.search_movies(query, limit=20)
    
    return JsonResponse({'results': results, 'source': source})


def movie_detail(request, mid):
    """Détails d'un film depuis SQLite ou MongoDB."""
    source = request.GET.get('source', 'sqlite')
    
    if source == 'mongo':
        movie = mongo_service.get_movie_with_rating(mid)
    else:
        movie = sqlite_service.get_movie_details(mid)
    
    if not movie:
        return JsonResponse({'error': 'Movie not found'}, status=404)
    
    return JsonResponse({'movie': movie, 'source': source})


def replica_status(request):
    """Affiche le statut du replica set MongoDB."""
    status = mongo_service.get_replica_status()
    return JsonResponse(status)
