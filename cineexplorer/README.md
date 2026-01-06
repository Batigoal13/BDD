# 🎬 CineExplorer - IMDB Database Explorer

Application web Django pour l'exploration d'une base de données IMDB complète avec architecture dual-database (SQLite + MongoDB Replica Set).

## 📋 Table des matières

- [Contexte du projet](#contexte-du-projet)
- [Architecture technique](#architecture-technique)
- [Technologies utilisées](#technologies-utilisées)
- [Structure du projet](#structure-du-projet)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Fonctionnalités](#fonctionnalités)
- [API Endpoints](#api-endpoints)
- [Tests](#tests)
- [Auteurs](#auteurs)

---

## 🎯 Contexte du projet

Projet réalisé dans le cadre du cours de Bases de Données (4A Polytech).

**Objectif** : Comparer les performances et capacités de deux types de bases de données (relationnelle vs NoSQL) sur un dataset IMDB complet contenant 291 238 films et 632 324 personnes.

### Phases du projet

- **Phase 1** : Modélisation et import des données dans SQLite
- **Phase 2** : Migration vers MongoDB avec trois modèles (flat, structured, optimized)
- **Phase 3** : Configuration d'un replica set MongoDB avec failover automatique
- **Phase 4** : Interface web Django avec exploitation des deux bases de données

---

## 🏗️ Architecture technique

### Architecture Dual-Database

```
┌─────────────────────────────────────────────────┐
│              Django Application                 │
│                                                 │
│  ┌──────────────┐         ┌─────────────────┐   │
│  │ SQLite       │         │ MongoDB Replica │   │
│  │ Service      │         │ Set Service     │   │
│  └──────────────┘         └─────────────────┘   │
│         │                          │            │
└─────────┼──────────────────────────┼────────────┘
          │                          │
          ▼                          ▼
   ┌─────────────┐          ┌──────────────────┐
   │  SQLite DB  │          │  MongoDB Cluster │
   │             │          │                  │
   │  imdb.db    │          │  ┌─────────────┐ │
   │             │          │  │ PRIMARY     │ │
   │ 291K films  │          │  │ :27017      │ │
   │ 632K people │          │  └─────────────┘ │
   └─────────────┘          │  ┌─────────────┐ │
                            │  │ SECONDARY   │ │
                            │  │ :27018      │ │
                            │  └─────────────┘ │
                            │  ┌─────────────┐ │
                            │  │ SECONDARY   │ │
                            │  │ :27019      │ │
                            │  └─────────────┘ │
                            └──────────────────┘
```

### Répartition des responsabilités

| Base de données | Rôle | Justification |
|-----------------|------|---------------|
| **SQLite** | Recherche, statistiques, agrégations | - Requêtes `LIKE` optimisées avec indexes<br>- JOINs complexes efficaces<br>- Léger, pas de serveur requis<br>- ACID garantie |
| **MongoDB** | Stockage documents enrichis | - Documents structurés complexes<br>- Casting complet (30+ acteurs)<br>- Titres internationaux par région<br>- Haute disponibilité (replica set) |

---

## 🛠️ Technologies utilisées

### Backend

- **Django 6.0** - Framework web Python
- **Python 3.12** - Langage de programmation
- **PyMongo 4.15.5** - Driver MongoDB officiel

### Bases de données

- **SQLite 3** - Base relationnelle (291 238 films, 632 324 personnes)
- **MongoDB 7.0.28** - Base NoSQL avec Replica Set (3 nœuds)
  - PRIMARY: localhost:27017
  - SECONDARY: localhost:27018
  - SECONDARY: localhost:27019

### Frontend

- **Bootstrap 5** - Framework CSS responsive
- **Chart.js 4.4** - Graphiques interactifs
- **Font Awesome 6.4** - Icônes vectorielles

### Outils

- **WiredTiger** - Storage Engine MongoDB
- **Git** - Gestion de version

---

## 📁 Structure du projet

```
cineexplorer/
├── config/                      # Configuration Django
│   ├── settings.py             # Configuration dual-database
│   ├── urls.py                 # Routes principales
│   └── wsgi.py
│
├── movies/                      # Application principale
│   ├── views.py                # 15 vues (index, search, detail, stats, API)
│   ├── urls.py                 # 8 routes
│   ├── models.py               # Modèles Django (non utilisés)
│   │
│   ├── services/               # Couche d'accès aux données
│   │   ├── sqlite_service.py  # 17 fonctions (recherche, stats)
│   │   └── mongo_service.py   # 8 fonctions (détails films)
│   │
│   ├── templates/movies/       # Templates HTML
│   │   ├── base.html          # Template de base
│   │   ├── index.html         # Page d'accueil
│   │   ├── movies_list.html   # Catalogue films
│   │   ├── movie_detail.html  # Détails d'un film
│   │   ├── search.html        # Résultats de recherche
│   │   ├── stats.html         # Statistiques + graphiques
│   │   └── 404.html           # Page d'erreur
│   │
│   └── templatetags/           # Filtres Django custom
│       └── movie_extras.py    # Filtre get_item pour dicts
│
├── data/
│   ├── imdb.db                # SQLite database (291K films)
│   ├── csv/                   # Fichiers CSV sources
│   └── mongo/                 # Données MongoDB
│       ├── db-1/              # PRIMARY (27017)
│       ├── db-2/              # SECONDARY (27018)
│       └── db-3/              # SECONDARY (27019)
│
├── scripts/
│   ├── phase1_sqlite/         # Scripts SQLite
│   │   ├── create_schema.py
│   │   ├── import_data.py
│   │   ├── queries.py
│   │   └── benchmark.py
│   │
│   ├── phase2_mongodb/        # Scripts MongoDB
│   │   ├── migrate_flat.py
│   │   ├── migrate_structured.py
│   │   ├── migrate_fast.py
│   │   ├── normalize_keys.py  # Normalisation collections
│   │   └── queries_mongo.py
│   │
│   └── phase3_replica/        # Configuration replica set
│       ├── setup_replica.sh
│       └── test_failover.py
│
├── static/                    # Fichiers statiques
│   ├── css/
│   ├── js/
│   └── img/
│
├── test_homepage.py           # Tests unitaires page d'accueil
├── test_phase4.py            # Tests phase 4
├── manage.py                 # CLI Django
├── requirements.txt          # Dépendances Python
└── README.md                 # Ce fichier
```

---

## 🚀 Installation

### Prérequis

- Python 3.12+
- MongoDB 7.0+
- Git

### Étapes

1. **Cloner le repository**

```bash
git clone https://github.com/Batigoal13/BDD.git
cd BDD/cineexplorer
```

2. **Créer un environnement virtuel**

```bash
python3 -m venv venv
source venv/bin/activate 
```

3. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

4. **Vérifier la présence des données**

```bash
# SQLite database
ls -lh data/imdb.db

# MongoDB (doit être déjà importé)
ls data/mongo/db-1/
```

---

## ⚙️ Configuration

### 1. Configuration MongoDB Replica Set

**Démarrer les 3 nœuds MongoDB :**

```bash
# Nœud PRIMARY (27017)
mongod --replSet rs0 --port 27017 --dbpath data/mongo/db-1 \
  --bind_ip localhost --fork --logpath data/mongo/logs/mongod-27017.log

# Nœud SECONDARY (27018)
mongod --replSet rs0 --port 27018 --dbpath data/mongo/db-2 \
  --bind_ip localhost --fork --logpath data/mongo/logs/mongod-27018.log

# Nœud SECONDARY (27019)
mongod --replSet rs0 --port 27019 --dbpath data/mongo/db-3 \
  --bind_ip localhost --fork --logpath data/mongo/logs/mongod-27019.log
```

**Vérifier le statut du replica set :**

```bash
mongosh --port 27017 --eval "rs.status().members.forEach(m => print(m.name + ' - ' + m.stateStr))"
```

Résultat attendu :
```
localhost:27017 - PRIMARY
localhost:27018 - SECONDARY
localhost:27019 - SECONDARY
```

### 2. Configuration Django

Le fichier `config/settings.py` est déjà configuré :

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'data' / 'imdb.db',
    }
}

MONGODB_SETTINGS = {
    'URI': 'mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0',
    'DATABASE': 'IMDB_DB',
}
```

---

## 💻 Utilisation

### Démarrer le serveur Django

```bash
python3 manage.py runserver 8000
```

Accéder à l'application : **http://localhost:8000**

### Navigation

- **Page d'accueil** (`/`) : Statistiques, top 10 films, état des bases
- **Catalogue** (`/movies/`) : Liste des films avec filtres (genre, année, note)
- **Détail film** (`/movie/<id>/`) : Informations complètes depuis MongoDB
- **Recherche** (`/search/?q=<query>`) : Recherche films et personnes
- **Statistiques** (`/stats/`) : Graphiques interactifs (Chart.js)

### Arrêter les services

```bash
# Django
Ctrl+C

# MongoDB
pkill -f mongod
```

---

## ✨ Fonctionnalités

### 1. Page d'accueil

- **Statistiques globales** : Nombre de films, acteurs, réalisateurs
- **Top 10 films** : Films les mieux notés (depuis SQLite)
- **Films récents** : Sorties récentes
- **État des bases** : Statut SQLite et MongoDB
- **Replica Set** : État détaillé des 3 nœuds (PRIMARY/SECONDARY)

### 2. Catalogue de films

- **Liste paginée** : 20 films par page
- **Filtres** :
  - Genre (Action, Drama, Comedy, etc.)
  - Année (min/max)
  - Note minimale
- **Tri** : Par titre, année, note
- **Vue** : Grille ou liste

### 3. Détail d'un film (MongoDB)

Données complètes depuis MongoDB WiredTiger :

- **Informations** : Titre, année, type, durée
- **Note** : 9.3/10 (2 554 860 votes)
- **Genres** : Drama, Crime
- **Réalisateurs** : Frank Darabont
- **Scénaristes** : Stephen King, Frank Darabont
- **Distribution** : 30+ acteurs avec personnages
  - Tim Robbins → Andy Dufresne
  - Morgan Freeman → Ellis Boyd 'Red' Redding
- **Titres internationaux** : 10 régions
  - 🇫🇷 France : "Les Évadés"
  - 🇮🇹 Italie : "Le ali della libertà"
  - 🇨🇳 Chine : "肖申克的救赎"
- **Films similaires** : Même genre (depuis SQLite)

### 4. Recherche avancée

**Recherche par film :**
```
Query: "dark knight"
→ The Dark Knight (2008)
→ The Dark Knight Rises (2012)
```

**Recherche par personne :**
```
Query: "christopher nolan"
→ Christopher Nolan
   📽️ Films (20):
   • Tenet (2020) - Réalisateur 🎥
   • Dunkirk (2017) - Réalisateur 🎥
   • Interstellar (2014) - Réalisateur 🎥
   • Inception (2010) - Réalisateur 🎥
   • The Dark Knight (2008) - Réalisateur 🎥
   • Man of Steel (2013) - Scénariste ✏️
   ...
```

**Fonctionnalités :**
- Filtres : Tous / Films / Personnes
- Cards de personnes avec :
  - Nom, années de naissance/décès
  - Liste complète des films
  - Badges de rôle (Réalisateur 🎥 / Scénariste ✏️ / Acteur 👤)
  - Note de chaque film
  - Lien vers détail du film

### 5. Statistiques interactives

Graphiques Chart.js (données depuis SQLite) :

1. **Films par genre** (Bar Chart)
   - Action, Drama, Comedy, Thriller, etc.
   
2. **Films par décennie** (Line Chart)
   - Evolution 1910-2020

3. **Distribution des notes** (Bar Chart)
   - Notes de 1 à 10

---

## 🌐 API Endpoints

Endpoints JSON pour clients externes :

### 1. Recherche

```http
GET /api/search/?q=<query>
```

**Exemple :**
```bash
curl "http://localhost:8000/api/search/?q=inception"
```

**Réponse :**
```json
{
  "movies": [
    {
      "MID": "tt1375666",
      "primaryTitle": "Inception",
      "startYear": 2010,
      "titletype": "movie"
    }
  ],
  "people": [
    {
      "PID": "nm0634240",
      "primaryName": "Christopher Nolan",
      "birthYear": 1970
    }
  ]
}
```

### 2. Statistiques films

```http
GET /api/movie_stats/
```

**Réponse :**
```json
{
  "movies_by_genre": [...],
  "rating_distribution": [...],
  "total_movies": 291238,
  "total_people": 632324
}
```

### 3. Statut Replica Set

```http
GET /api/replica-status/
```

**Réponse :**
```json
{
  "ok": 1,
  "set": "rs0",
  "members": [
    {
      "name": "localhost:27017",
      "stateStr": "PRIMARY",
      "health": 1
    },
    {
      "name": "localhost:27018",
      "stateStr": "SECONDARY",
      "health": 1
    },
    {
      "name": "localhost:27019",
      "stateStr": "SECONDARY",
      "health": 1
    }
  ]
}
```

---

## 🧪 Tests

### Tests unitaires

```bash
# Test page d'accueil
python3 test_homepage.py

# Test phase 4
python3 test_phase4.py
```

### Tests manuels

**Recherche SQLite :**
```bash
python3 -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from movies.services import sqlite_service

# Rechercher un film
results = sqlite_service.search_movies('matrix', limit=5)
for film in results:
    print(f\"{film['primaryTitle']} ({film['startYear']})\")
"
```

**MongoDB détail film :**
```bash
python3 -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from movies.services import mongo_service

# Détails The Shawshank Redemption
movie = mongo_service.get_movie_detail('tt0111161')
print(f\"Titre: {movie['title']}\")
print(f\"Note: {movie['rating']}/10 ({movie['num_votes']} votes)\")
print(f\"Réalisateur: {movie['directors'][0]['name']}\")
print(f\"Cast: {len(movie['cast'])} acteurs\")
"
```

### Benchmark performances

**SQLite :**
```bash
cd scripts/phase1_sqlite
python3 benchmark.py
```

**MongoDB :**
```bash
cd scripts/phase2_mongodb
python3 queries_mongo.py
```

---

## 📊 Données

### SQLite (imdb.db)

| Table | Lignes | Description |
|-------|--------|-------------|
| Movies | 291 238 | Films principaux |
| Persons | 632 324 | Acteurs, réalisateurs, scénaristes |
| Ratings | 291 238 | Notes moyennes et votes |
| Genres | 649 433 | Genres par film |
| Directors | 419 861 | Réalisateurs par film |
| Writers | 900 485 | Scénaristes par film |
| Principals | 2 745 688 | Distribution complète |
| Characters | 1 425 813 | Noms de personnages |
| Professions | 2 013 792 | Professions des personnes |
| KnownForMovies | 1 898 862 | Films célèbres par personne |
| Titles | 1 908 072 | Titres alternatifs |
| Episodes | 4 756 895 | Épisodes de séries TV |

**Total : ~13 millions de lignes**

### MongoDB (IMDB_DB)

| Collection | Documents | Description |
|------------|-----------|-------------|
| Movies_normalized | 291 238 | Films avec tous les détails |
| Ratings_normalized | 291 238 | Notes et votes |
| Persons_normalized | 632 324 | Personnes complètes |
| Directors_normalized | 419 861 | Relations réalisateur-film |
| Writers_normalized | 900 485 | Relations scénariste-film |
| Principals_normalized | 2 745 688 | Distribution casting |
| Characters_normalized | 1 425 813 | Personnages joués |
| Genres_normalized | 649 433 | Genres par film |
| Titles_normalized | 1 908 072 | Titres internationaux |

**Total : ~9 millions de documents**

---

## 🔧 Dépannage

### MongoDB ne démarre pas

```bash
# Vérifier les processus
ps aux | grep mongod

# Vérifier les logs
tail -50 data/mongo/logs/mongod-27017.log

# Nettoyer et redémarrer
pkill -f mongod
rm data/mongo/db-1/mongod.lock
mongod --replSet rs0 --port 27017 --dbpath data/mongo/db-1 --bind_ip localhost --fork --logpath data/mongo/logs/mongod-27017.log
```

### Replica Set en RECOVERING

```bash
# Nettoyer le nœud problématique (exemple 27018)
pkill -f "mongod.*27018"
rm -rf data/mongo/db-2/*
mongod --replSet rs0 --port 27018 --dbpath data/mongo/db-2 --bind_ip localhost --fork --logpath data/mongo/logs/mongod-27018.log

# Forcer la synchronisation
mongosh --port 27018 --eval "rs.syncFrom('localhost:27017')"
```

### Django erreur de connexion MongoDB

```python
# Vérifier la connexion
python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0')
print(client.admin.command('ping'))
"
```

---

## 📈 Performances

### Temps de réponse moyens

| Opération             | SQLite | MongoDB |
|-----------------------|--------|---------|
| Recherche film (LIKE) | ~10ms  | N/A     |
| Détail complet film   | N/A    | ~50ms   |
| Agrégation genre      | ~100ms | ~200ms  |
| Top 10 films          | ~15ms  | ~150ms  |

### Espace disque

- **SQLite** : 450 MB (imdb.db)
- **MongoDB** : 2.8 GB (3 nœuds avec réplication)

---

## 🎓 Choix techniques justifiés

### Pourquoi SQLite pour les recherches ?

- ✅ Index B-Tree optimisés pour LIKE
- ✅ JOINs multi-tables très rapides
- ✅ Pas de latence réseau (embedded)
- ✅ ACID garanti pour lectures concurrentes

### Pourquoi MongoDB pour les détails ?

- ✅ Documents enrichis sans JOINs (1 seule requête)
- ✅ Flexibilité schema-less (titres internationaux variables)
- ✅ Haute disponibilité avec replica set
- ✅ Évolutivité horizontale

### Pourquoi Replica Set ?

- ✅ Tolérance aux pannes (RTO < 2 secondes)
- ✅ Lecture distribuée sur SECONDARY (load balancing)
- ✅ Backup automatique (2 copies)
- ✅ Maintenance sans downtime

---

## 👥 Auteurs

- **Batist AUREILLE** - Polytech 4A - [@Batigoal13](https://github.com/Batigoal13)

---

## 📝 Licence

Projet académique - Polytech 4A - Bases de Données

---

## 🔗 Liens utiles

- [Repository GitHub](https://github.com/Batigoal13/BDD)
- [Django Documentation](https://docs.djangoproject.com/)
- [MongoDB Replica Set](https://www.mongodb.com/docs/manual/replication/)
- [Bootstrap 5](https://getbootstrap.com/docs/5.0/)
- [Chart.js](https://www.chartjs.org/)

---

## 📅 Historique du projet

- **Phase 1** (Dec 2025) : SQLite + import CSV
- **Phase 2** (Dec 2025) : Migration MongoDB (3 modèles)
- **Phase 3** (Dec 2025) : Replica Set + failover
- **Phase 4** (Jan 2026) : Interface web Django + dual-database

---

**Version finale : 6 janvier 2026** 🎬
