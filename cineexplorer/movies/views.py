from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
import json
from movies.services import sqlite_service, mongo_service


# ============================================
# PAGES PRINCIPALES
# ============================================

def index(request):
    """Page d'accueil avec statistiques et top 10 films."""
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

    # Top 10 films par note (depuis SQLite)
    top_movies = sqlite_service.get_top_rated_movies(limit=10)
    
    # Films récents
    recent_movies = sqlite_service.get_recent_movies(limit=12)
    
    context = {
        'sqlite_stats': {
            'movie_count': sqlite_service.get_movie_count(),
            'person_count': sqlite_service.get_person_count(),
            'actor_count': sqlite_service.get_actor_count(),
            'director_count': sqlite_service.get_director_count(),
            'rating_stats': sqlite_service.get_rating_stats(),
        },
        'mongo_stats': mongo_stats,
        'replica_status': replica_status,
        'top_movies': top_movies,
        'recent_movies': recent_movies,
    }
    return render(request, 'movies/index.html', context)


def movies_list(request):
    """Liste paginée des films avec filtres et tri."""
    # Récupérer les paramètres
    page = request.GET.get('page', 1)
    genre = request.GET.get('genre', '')
    year_min = request.GET.get('year_min', '')
    year_max = request.GET.get('year_max', '')
    rating_min = request.GET.get('rating_min', 0)
    sort_by = request.GET.get('sort', 'title')  # title, year, rating
    view_type = request.GET.get('view', 'grid')  # grid ou list
    
    # Récupérer la liste des films (avec filtres et tri)
    all_movies = sqlite_service.get_filtered_movies(
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        rating_min=float(rating_min) if rating_min else 0,
        sort_by=sort_by
    )
    
    # Pagination (20 films par page)
    paginator = Paginator(all_movies, 20)
    movies = paginator.get_page(page)
    
    # Récupérer les genres disponibles
    genres = sqlite_service.get_all_genres()
    
    context = {
        'movies': movies,
        'genres': genres,
        'current_genre': genre,
        'current_year_min': year_min,
        'current_year_max': year_max,
        'current_rating_min': rating_min,
        'current_sort': sort_by,
        'view_type': view_type,
        'total_count': paginator.count,
    }
    return render(request, 'movies/movies_list.html', context)


def movie_detail(request, movie_id):
    """Détail complet d'un film (depuis MongoDB pour données agrégées)."""
    # Récupérer les détails depuis MongoDB (données complètes)
    movie = mongo_service.get_movie_detail(movie_id)
    
    if not movie:
        return render(request, 'movies/404.html', {'message': 'Film non trouvé'}, status=404)
    
    # Récupérer les films similaires (même genre)
    similar_movies = sqlite_service.get_similar_movies(
        genre=movie.get('genres', [None])[0] if movie.get('genres') else None,
        limit=6,
        exclude_id=movie_id
    )
    
    context = {
        'movie': movie,
        'similar_movies': similar_movies,
    }
    return render(request, 'movies/movie_detail.html', context)


def search(request):
    """Recherche par titre de film ou nom de personne."""
    query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'all')  # all, movies, people
    
    results = {
        'movies': [],
        'people': [],
        'query': query,
        'movies_by_person': {},  # {person_id: [movies]}
    }
    
    if query:
        if search_type in ['all', 'movies']:
            results['movies'] = sqlite_service.search_movies(query, limit=20)
        
        if search_type in ['all', 'people']:
            people = sqlite_service.search_people(query, limit=20)
            results['people'] = people
            
            # Pour chaque personne trouvée, récupérer ses films
            for person in people:  # Récupérer les films pour toutes les personnes
                person_id = person.get('PID')
                if person_id:
                    movies_of_person = sqlite_service.get_movies_by_person(person_id, limit=50)
                    if movies_of_person:
                        results['movies_by_person'][person_id] = movies_of_person
    
    context = {
        'results': results,
        'search_type': search_type,
        'has_results': len(results['movies']) > 0 or len(results['people']) > 0,
    }
    return render(request, 'movies/search.html', context)


# ============================================
# STATISTIQUES ET GRAPHIQUES
# ============================================

def stats(request):
    """Page des statistiques avec graphiques."""
    # Films par genre
    movies_by_genre = sqlite_service.get_movies_by_genre()
    
    # Films par décennie
    movies_by_decade = sqlite_service.get_movies_by_decade()
    
    # Distribution des notes
    rating_distribution = sqlite_service.get_rating_distribution()
    
    # Top 10 acteurs
    top_actors = sqlite_service.get_top_actors(limit=10)
    
    context = {
        'movies_by_genre': json.dumps(movies_by_genre),
        'movies_by_decade': json.dumps(movies_by_decade),
        'rating_distribution': json.dumps(rating_distribution),
        'top_actors': top_actors,
    }
    return render(request, 'movies/stats.html', context)


# ============================================
# API ENDPOINTS
# ============================================

def api_search(request):
    """API de recherche (JSON)."""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'error': 'Query too short'}, status=400)
    
    results = {
        'movies': sqlite_service.search_movies(query, limit=10),
        'people': sqlite_service.search_people(query, limit=10),
    }
    
    return JsonResponse(results)


def api_movie_stats(request):
    """API pour les statistiques des films (JSON)."""
    stats = {
        'movies_by_genre': sqlite_service.get_movies_by_genre(),
        'rating_distribution': sqlite_service.get_rating_distribution(),
        'total_movies': sqlite_service.get_movie_count(),
        'total_people': sqlite_service.get_person_count(),
    }
    return JsonResponse(stats)


def replica_status(request):
    """Affiche le statut du replica set MongoDB."""
    status = mongo_service.get_replica_status()
    return JsonResponse(status)

