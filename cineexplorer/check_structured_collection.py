#!/usr/bin/env python3
"""
Script pour vérifier l'état de la collection movies_complete_ALL
"""
import os
import django
import time

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from movies.services.mongo_service import get_database

def check_collection():
    db = get_database()
    
    print("=" * 60)
    print("VÉRIFICATION DE LA COLLECTION STRUCTURÉE")
    print("=" * 60)
    
    # Vérifier si la collection existe
    collections = db.list_collection_names()
    
    if "movies_complete_ALL" not in collections:
        print("\n❌ La collection 'movies_complete_ALL' n'existe pas encore.")
        print("   Le script migrate_strctured.py est peut-être en cours d'exécution.")
        return False
    
    # Compter les documents
    count = db.movies_complete_ALL.count_documents({})
    total_expected = db.Movies.estimated_document_count()
    
    print(f"\n📊 Collection: movies_complete_ALL")
    print(f"   Documents: {count:,}")
    print(f"   Attendu: {total_expected:,}")
    print(f"   Progression: {100*count/total_expected:.1f}%")
    
    if count == 0:
        print("\n⏳ La collection est vide. Migration en cours...")
        return False
    
    # Examiner un document exemple
    print(f"\n🔍 Exemple de document structuré:")
    sample = db.movies_complete_ALL.find_one({})
    if sample:
        print(f"   ID: {sample.get('_id')}")
        print(f"   Titre: {sample.get('title')}")
        print(f"   Année: {sample.get('year')}")
        print(f"   Genres: {sample.get('genres', [])}")
        print(f"   Note: {sample.get('rating', {}).get('average')}/10")
        print(f"   Casting: {len(sample.get('cast', []))} acteurs")
        print(f"   Réalisateurs: {len(sample.get('directors', []))} réalisateurs")
        
        # Tester get_movie_detail
        print(f"\n✅ Test de get_movie_detail avec {sample.get('_id')}:")
        from movies.services import mongo_service
        detail = mongo_service.get_movie_detail(sample.get('_id'))
        if detail:
            print(f"   ✅ Fonction get_movie_detail fonctionne!")
            print(f"      Titre: {detail.get('primaryTitle')}")
            print(f"      Acteurs: {len(detail.get('cast', []))}")
        else:
            print(f"   ❌ Erreur dans get_movie_detail")
    
    if count == total_expected:
        print(f"\n🎉 Migration terminée avec succès!")
        return True
    else:
        print(f"\n⏳ Migration en cours... {count}/{total_expected}")
        return False

if __name__ == "__main__":
    while True:
        is_complete = check_collection()
        if is_complete:
            break
        print(f"\n⏱️  Attente de 10 secondes avant nouvelle vérification...")
        time.sleep(10)
