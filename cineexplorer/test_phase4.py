#!/usr/bin/env python3
"""
Script de test pour Phase 4 - Vérifier que toutes les données sont disponibles
"""

import os
import django
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from movies.services import sqlite_service, mongo_service

print("=" * 60)
print("TEST PHASE 4 - VÉRIFICATION DES DONNÉES")
print("=" * 60)

# Test 1: Vérifier les comptes SQLite
print("\n1. Vérification SQLite:")
try:
    movie_count = sqlite_service.get_movie_count()
    person_count = sqlite_service.get_person_count()
    print(f"   ✓ Films SQLite: {movie_count}")
    print(f"   ✓ Personnes SQLite: {person_count}")
except Exception as e:
    print(f"   ✗ Erreur SQLite: {e}")

# Test 2: Vérifier MongoDB
print("\n2. Vérification MongoDB:")
try:
    mongo_movie_count = mongo_service.get_movie_count()
    mongo_person_count = mongo_service.get_person_count()
    print(f"   ✓ Films MongoDB: {mongo_movie_count}")
    print(f"   ✓ Personnes MongoDB: {mongo_person_count}")
except Exception as e:
    print(f"   ✗ Erreur MongoDB: {e}")

# Test 3: Vérifier les genres
print("\n3. Genres disponibles:")
try:
    genres = sqlite_service.get_all_genres()
    print(f"   ✓ {len(genres)} genres trouvés: {', '.join(genres[:5])}...")
except Exception as e:
    print(f"   ✗ Erreur genres: {e}")

# Test 4: Vérifier le top 10 des films
print("\n4. Top 10 films par note:")
try:
    top_movies = sqlite_service.get_top_rated_movies(limit=10)
    print(f"   ✓ {len(top_movies)} films trouvés")
    if top_movies:
        print(f"      Premier film: {top_movies[0].get('primaryTitle')} ({top_movies[0].get('rating', 'N/A')}/10)")
except Exception as e:
    print(f"   ✗ Erreur top films: {e}")

# Test 5: Vérifier la recherche
print("\n5. Test de recherche:")
try:
    search_movies = sqlite_service.search_movies("Inception", limit=5)
    print(f"   ✓ Recherche 'Inception': {len(search_movies)} résultats")
    if search_movies:
        print(f"      Exemple: {search_movies[0].get('primaryTitle')}")
except Exception as e:
    print(f"   ✗ Erreur recherche: {e}")

# Test 6: Vérifier les agrégations
print("\n6. Agrégations statistiques:")
try:
    by_genre = sqlite_service.get_movies_by_genre()
    print(f"   ✓ Films par genre: {len(by_genre)} genres")
    
    by_decade = sqlite_service.get_movies_by_decade()
    print(f"   ✓ Films par décennie: {len(by_decade)} décennies")
    
    rating_dist = sqlite_service.get_rating_distribution()
    print(f"   ✓ Distribution des notes: {len(rating_dist)} buckets")
except Exception as e:
    print(f"   ✗ Erreur agrégations: {e}")

# Test 7: Vérifier le détail d'un film MongoDB
print("\n7. Test détail d'un film (MongoDB):")
try:
    # Obtenir un film quelconque
    sample_movie = sqlite_service.search_movies("The", limit=1)
    if sample_movie:
        movie_id = sample_movie[0].get('MID')
        detail = mongo_service.get_movie_detail(movie_id)
        if detail:
            print(f"   ✓ Film trouvé: {detail.get('primaryTitle')}")
            print(f"      Note: {detail.get('rating', 'N/A')}/10")
            print(f"      Casting: {len(detail.get('cast', []))} acteurs")
            print(f"      Réalisateurs: {len(detail.get('directors', []))}")
        else:
            print(f"   ✗ Détail non trouvé pour {movie_id}")
except Exception as e:
    print(f"   ✗ Erreur détail film: {e}")

# Test 8: Vérifier le replica set
print("\n8. Statut du replica set MongoDB:")
try:
    replica_status = mongo_service.get_replica_status()
    if replica_status.get('ok') == 1:
        print(f"   ✓ Replica set '{replica_status.get('set')}' actif")
        members = replica_status.get('members', [])
        for member in members:
            print(f"      - {member.get('name')}: {member.get('stateStr')} (health={member.get('health')})")
    else:
        print(f"   ✗ Erreur replica set: {replica_status.get('error', 'Unknown')}")
except Exception as e:
    print(f"   ✗ Erreur statut replica: {e}")

print("\n" + "=" * 60)
print("TEST TERMINÉ")
print("=" * 60)
