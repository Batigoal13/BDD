import pymongo
import json
import sys

# --- CONFIGURATION ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "IMDB_DB"
COLLECTION = "movies_complete_ALL" # On utilise votre collection complète

def view_movie():
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # Demander à l'utilisateur quel film voir
    search_title = input("\n🔎 Entrez un titre de film (ex: Inception) : ").strip()
    
    if not search_title:
        # Par défaut, on prend un film célèbre pour l'exemple
        search_title = "The Shawshank Redemption"
        print(f"   (Recherche par défaut : {search_title})")

    print(f"\n⏳ Recherche de '{search_title}'...")

    # Recherche insensible à la casse (regex)
    doc = db[COLLECTION].find_one(
        {"original_title": {"$regex": f"^{search_title}$", "$options": "i"}}
    )

    if doc:
        print("\n" + "="*50)
        print(f"🎬 FICHE FILM : {doc.get('title')}")
        print("="*50)
        
        # Affichage JSON propre
        # indent=4 : crée l'indentation
        # ensure_ascii=False : affiche les accents correctement (é, à, ñ...)
        # default=str : gère les objets dates ou IDs bizarres s'il y en a
        json_output = json.dumps(doc, indent=4, ensure_ascii=False, default=str)
        
        # On peut utiliser une librairie de coloration syntaxique si installée, 
        # sinon on print juste le texte.
        try:
            from pygments import highlight
            from pygments.lexers import JsonLexer
            from pygments.formatters import TerminalFormatter
            print(highlight(json_output, JsonLexer(), TerminalFormatter()))
        except ImportError:
            # Fallback si pygments n'est pas installé (affichage noir et blanc)
            print(json_output)
            
        print("\n" + "="*50)
    else:
        print("❌ Film introuvable. Essayez le titre original exact.")

if __name__ == "__main__":
    try:
        view_movie()
    except KeyboardInterrupt:
        print("\n👋 Au revoir !")