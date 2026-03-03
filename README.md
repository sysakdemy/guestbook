# Guestbook — Démonstration Docker multi-services

Application pédagogique développée en fin de formation Docker.  
Elle illustre l'orchestration de **4 services** avec Docker Compose :
un backend Flask, une base de données PostgreSQL, un cache Redis et
une interface d'administration Adminer.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  docker-compose                 │
│                                                 │
│  ┌──────────┐     SQL      ┌─────────────────┐  │
│  │          │◄────────────►│  db             │  │
│  │   web    │              │  PostgreSQL 16  │  │
│  │  Flask   │   REDIS      └────────┬────────┘  │
│  │ Gunicorn │◄────────────►┌─────────────────┐  │
│  │  :5000   │              │  adminer        |  │
│  └──────────┘              │  Adminer :8080  │  │
│                            └─────────────────┘  │
│  ┌──────────┐                                   │
│  │  cache   │                                   │
│  │  Redis 7 │                                   │
│  └──────────┘                                   │
└─────────────────────────────────────────────────┘
```

| Service    | Image                 | Port exposé | Rôle                              |
|------------|-----------------------|-------------|-----------------------------------|
| `web`      | build local (Flask)   | **5000**    | Application web / API             |
| `db`       | `postgres:16-alpine`  | —           | Stockage persistant des messages  |
| `cache`    | `redis:7-alpine`      | —           | Compteur de visites en mémoire    |
| `adminer`  | `adminer:latest`      | **8080**    | Interface web d'admin PostgreSQL  |

Les services `db` et `cache` ne sont **pas exposés sur le réseau hôte** :
seul le service `web` (et `adminer`) peut leur parler, via le réseau interne `guestbook_net`.

---

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ou Docker Engine ≥ 24
- Docker Compose ≥ 2 (plugin intégré : `docker compose`)

---

## Structure du projet

```
guestbook/
├── Dockerfile            # Build de l'image web (multi-stage)
├── docker-compose.yml    # Orchestration des 4 services
├── app.py                # Application Flask
├── requirements.txt      # Dépendances Python
├── README.md             # Ce fichier
└── templates/
    └── index.html        # Interface utilisateur (Bootstrap 5)
```

---

## Démarrage rapide

```bash
# 1. Se placer dans le dossier
cd app

# 2. Construire et démarrer tous les services
docker compose up --build

# 3. En arrière-plan (mode détaché)
docker compose up --build -d
```

| URL                          | Description                     |
|------------------------------|---------------------------------|
| http://localhost:5000        | Application Guestbook           |
| http://localhost:8080        | Adminer (interface BDD)         |

---

## Accès à Adminer

Ouvrir http://localhost:8080 et renseigner :

| Champ        | Valeur       |
|--------------|--------------|
| Système      | PostgreSQL   |
| Serveur      | `db`         |
| Utilisateur  | `postgres`   |
| Mot de passe | `secret`     |
| Base         | `guestbook`  |

---

## Variables d'environnement (service `web`)

| Variable      | Valeur par défaut | Description                     |
|---------------|-------------------|---------------------------------|
| `DB_HOST`     | `db`              | Hostname PostgreSQL             |
| `DB_NAME`     | `guestbook`       | Nom de la base de données       |
| `DB_USER`     | `postgres`        | Utilisateur PostgreSQL          |
| `DB_PASSWORD` | `secret`          | Mot de passe PostgreSQL         |
| `REDIS_HOST`  | `cache`           | Hostname Redis                  |

---

## Commandes utiles

```bash
# Voir l'état des conteneurs
docker compose ps

# Suivre les logs en temps réel
docker compose logs -f

# Logs d'un seul service
docker compose logs -f web

# Arrêter les services (les volumes sont conservés)
docker compose stop

# Arrêter ET supprimer les conteneurs
docker compose down

# Tout supprimer, y compris les volumes (⚠️ perd les données)
docker compose down -v

# Rebuilder uniquement le service web
docker compose build web
docker compose up -d --no-deps web
```

---

## Concepts Docker illustrés

### Build multi-stage (Dockerfile)

```
Stage builder  →  installe les dépendances Python dans un venv
Stage final    →  copie uniquement le venv + le code
                  → image finale plus petite, sans outils de build
```

### Healthcheck + depends_on

Le service `web` ne démarre pas tant que `db` et `cache` ne répondent pas :

```yaml
depends_on:
  db:
    condition: service_healthy
  cache:
    condition: service_healthy
```

Chaque service déclare son propre `healthcheck` (pg_isready, redis-cli ping).

### Réseau isolé

Tous les services partagent un réseau `bridge` privé (`guestbook_net`).  
Les services se joignent par leur **nom de service** (`db`, `cache`) sans
avoir besoin d'IP fixe.

### Volume nommé

```yaml
volumes:
  postgres_data:
```

Les données PostgreSQL survivent aux redémarrages et à `docker compose down`.  
Seul `docker compose down -v` les supprime.

### Sécurité minimale

- L'application Flask tourne sous un utilisateur non-root (`appuser`) dans le conteneur.
- Les ports de la BDD et de Redis ne sont **jamais** publiés sur l'hôte.

---

## Schéma de démarrage

```
docker compose up --build
        │
        ├─► db     (postgres) ──healthcheck──► ready
        ├─► cache  (redis)    ──healthcheck──► ready
        │
        ├─► adminer ──depends_on db ──► démarre
        └─► web     ──depends_on db + cache ──► démarre
                           │
                     init_db() crée la table si absente
                           │
                     Gunicorn écoute sur :5000
```

---

## CI/CD — GitHub Actions

Le fichier [.github/workflows/docker-image.yml](.github/workflows/docker-image.yml)
automatise le **build et le push** de l'image Docker vers un registry Harbor à chaque
modification du code.

### Déclencheurs

| Événement     | Branches / cibles          | Effet                        |
|---------------|----------------------------|------------------------------|
| `push`        | `main`, `dev`              | Build + push                 |
| `push`        | tag (`v1.0`, `v2.3.1`…)   | Build + push avec ce tag     |
| `pull_request`| `main`, `dev`              | Build + push (review)        |

Le workflow ne se déclenche que si au moins l'un de ces fichiers a changé :
`Dockerfile`, `app.py`, `requirements.txt`, `index.html` ou le fichier workflow lui-même.  
Modifier uniquement le `README.md` ne lance donc pas de build inutile.

### Stratégie de tags

| Condition                        | Tag produit              |
|----------------------------------|--------------------------|
| Push sur `main`                  | `latest`                 |
| Push sur `dev`                   | `dev`                    |
| Push d'un tag Git (`v1.2.3`)     | `v1.2.3`                 |

### Étapes du workflow

```
Checkout du code
      │
      ▼
Setup Docker Buildx        ← active le builder multi-plateforme
      │
      ▼
Login Harbor registry      ← utilise les secrets HARBOR_USERNAME / HARBOR_PASSWORD
      │
      ▼
Extract metadata           ← calcule les tags et labels à partir du contexte Git
      │
      ▼
Build & Push               ← construit l'image et la pousse vers le registry
      │                       utilise le cache GitHub Actions (cache-from/to: gha)
      ▼
Output digest              ← affiche le digest de l'image poussée
```

### Secrets et variables requis

À configurer dans **Settings → Secrets and variables → Actions** du dépôt :

| Nom                  | Type     | Description                              |
|----------------------|----------|------------------------------------------|
| `HARBOR_USERNAME`    | Secret   | Identifiant du compte Harbor             |
| `HARBOR_PASSWORD`    | Secret   | Mot de passe / token Harbor              |
| `REGISTRY`           | Variable | URL du registry (ex. `harbor.example.com/projet`) |

### Cache de build

Le workflow active le **cache GitHub Actions** (`cache-from/to: type=gha`) :
les layers Docker déjà construits sont réutilisés d'un run à l'autre,
ce qui réduit significativement le temps de build.
