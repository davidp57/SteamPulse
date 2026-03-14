# SteamPulse — User guide / Guide utilisateur

> This file has been superseded by the language-specific guides below.  
> Ce fichier a été remplacé par les guides spécifiques par langue ci-dessous.

| 🇬🇧 English | 🇫🇷 Français |
|---|---|
| [docs/en/user-guide.md](en/user-guide.md) | [docs/fr/user-guide.md](fr/user-guide.md) |

---

## Sommaire

1. [Installation](#1-installation)
2. [Obtenir les prérequis Steam](#2-obtenir-les-prérequis-steam)
3. [Récupérer les données (`steam-fetch`)](#3-récupérer-les-données-steam-fetch)
4. [Générer les pages HTML (`steam-render`)](#4-générer-les-pages-html-steam-render)
5. [Naviguer dans l'interface](#5-naviguer-dans-linterface)
6. [Stratégie de cache et rafraîchissement](#6-stratégie-de-cache-et-rafraîchissement)
7. [FAQ](#7-faq)

---

## 1. Installation

**Prérequis :** Python 3.11 ou supérieur.

```bash
# Cloner ou télécharger le dépôt, puis :
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -e .
```

Pour disposer également des outils de développement (ruff, mypy, pytest) :

```bash
pip install -e ".[dev]"
```

---

## 2. Obtenir les prérequis Steam

### Clé API Steam

1. Connecte-toi sur <https://steamcommunity.com/dev/apikey>
2. Entre un nom de domaine quelconque (ex. `localhost`)
3. Copie la clé affichée (32 caractères hexadécimaux)

> ⚠️ La clé donne accès en lecture à ton compte. Ne la partage pas et ne la commite pas dans un dépôt.

### Ton SteamID64

Rends-toi sur <https://steamid.io>, entre ton pseudo Steam ou l'URL de ton profil.  
Le SteamID64 est un nombre à 17 chiffres commençant par `765`.

---

## 3. Récupérer les données (`steam-fetch`)

```bash
steam-fetch --key <API_KEY> --steamid <STEAMID64>
```

### Options complètes

| Option | Défaut | Description |
|---|---|---|
| `--key` | *(requis)* | Clé Steam Web API |
| `--steamid` | *(requis)* | SteamID64 du profil |
| `--db` | `steam_library.db` | Chemin vers la base SQLite |
| `--workers` | `4` | Nombre de threads parallèles pour les requêtes |
| `--max N` | *(aucun)* | Limiter le fetch à N jeux (utile pour tester) |
| `--refresh` | désactivé | Ignorer le cache, tout re-fetcher |
| `--news-age HOURS` | `24` | Rafraîchir les news des jeux dont le cache dépasse N heures |
| `--no-wishlist` | désactivé | Ne pas récupérer la wishlist |
| `--followed` | désactivé | Récupérer les jeux suivis (opt-in, voir note) |
| `-v` / `--verbose` | désactivé | Afficher les logs DEBUG |

> **Note `--followed`** : l'API Steam Web ne retourne plus les jeux suivis avec une clé standard.  
> Cette option est disponible mais retournera généralement une liste vide.

### Ce que le fetch récupère

Pour chaque jeu (possédé, wishlist, ou suivi) :
- **App details** : nom, type, description courte, développeurs, éditeurs, genres, catégories, plateformes, prix, score Metacritic, nombre d'achievements et de recommandations, date de sortie
- **News** : les 5 dernières actualités officielles (titre, date, URL, auteur)

Les jeux déjà en cache conservent leurs app_details et seules leurs news sont rafraîchies si elles ont plus de `--news-age` heures (voir [section 6](#6-stratégie-de-cache-et-rafraîchissement)).

### Exemple d'exécution

```
📦 Récupération de la bibliothèque Steam...
   ✅ 2190 jeu(x) possédé(s)
🎁 Récupération de la wishlist...
   ✅ 54 jeu(x) en wishlist · 54 nouveau(x)
   12 jeu(x) à récupérer · 387 news à rafraîchir (1845 déjà à jour)
[  1/399] Elden Ring
[  2/399] Cyberpunk 2077
...
✅ Done — 399 entrée(s) mise(s) à jour dans steam_library.db
```

---

## 4. Générer les pages HTML (`steam-render`)

```bash
steam-render --steamid <STEAMID64>
```

### Options complètes

| Option | Défaut | Description |
|---|---|---|
| `--db` | `steam_library.db` | Base SQLite source |
| `--steamid` | *(requis)* | SteamID64 (affiché dans l'en-tête) |
| `--output` | `steam_library.html` | Chemin de la page bibliothèque |

Deux fichiers sont générés :
- `steam_library.html` — vue bibliothèque en cartes
- `steam_news.html` — flux de toutes les news, triées par date

Ouvre l'un ou l'autre directement dans un navigateur. **Aucun serveur requis.**

---

## 5. Naviguer dans l'interface

### Page bibliothèque (`steam_library.html`)

**Barre d'outils :**
- **Recherche** — filtre les jeux par nom en temps réel
- **Tri** — par nom, score Metacritic, temps de jeu, date de sortie, date de dernière news, date de mise à jour de la fiche
- **Statut** — Tous / Early Access / Sortis / À venir
- **Source** — 🎮 Tout / Possédés / 🎁 Wishlist

**Cartes :**
Chaque carte affiche :
- Image d'en-tête du jeu
- Nom + badge statut (Early Access, Sorti, À venir)
- Score Metacritic (vert ≥ 75, orange ≥ 50, rouge < 50)
- Plateformes (Windows / Mac / Linux)
- Genres
- Date de sortie · Date de la dernière news · Temps de jeu (ou "🎁 Wishlist" / "👁 Suivi")
- ID Steam (cliquable → page Steam)

Un clic sur la carte ouvre la page Steam du jeu dans un nouvel onglet.

### Page news (`steam_news.html`)

- Toutes les news de tous les jeux, triées par date décroissante
- Recherche par nom de jeu
- Filtre par statut (Early Access / Sortis / À venir)
- Chaque ligne affiche l'image miniature, le nom du jeu, la date, le badge statut et le titre de la news
- Un clic ouvre la news sur Steam

---

## 6. Stratégie de cache et rafraîchissement

SteamPulse évite de refaire des milliers de requêtes à chaque exécution.

| Scénario | Comportement |
|---|---|
| Nouveau jeu (jamais vu) | App details + news fetchées |
| Jeu déjà en cache, news < `--news-age` h | Ignoré complètement |
| Jeu déjà en cache, news ≥ `--news-age` h | News re-fetchées, app details conservées |
| `--refresh` passé | Tout est re-fetché, cache ignoré |

**Conseil :** lance `steam-fetch` quotidiennement sans options pour maintenir les news à jour. Utilise `--refresh` uniquement si les métadonnées d'un jeu ont changé (changement de prix, sortie de Early Access…).

---

## 7. FAQ

**Q : Mon profil Steam est privé, est-ce que ça marche ?**  
La clé API contourne la restriction de confidentialité pour les requêtes portant sur ton propre compte. Les autres comptes privés restent inaccessibles.

**Q : Les données sont-elles envoyées quelque part ?**  
Non. Tout reste en local : la base SQLite sur ton disque, les pages HTML générées localement. Seules des requêtes en lecture sont faites vers l'API publique Steam.

**Q : Combien de temps prend le premier fetch ?**  
Avec 2000 jeux et 4 workers, comptez ~15-20 minutes (limite de débit de l'API Store ~200 req/5 min).

**Q : Puis-je lancer `steam-render` sans avoir relancé `steam-fetch` ?**  
Oui. `steam-render` lit uniquement la base SQLite et régénère le HTML à partir des données existantes.

**Q : Comment interrompre un fetch en cours ?**  
`Ctrl+C` — les tâches en cours sont annulées proprement et les données déjà collectées sont sauvegardées.
