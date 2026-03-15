# SteamPulse — Guide développeur

🌐 [English version](../en/developer-guide.md)

## Sommaire

1. [Structure du projet](#1-structure-du-projet)
2. [Vue d'ensemble de l'architecture](#2-vue-densemble-de-larchitecture)
3. [Modèles de données](#3-modèles-de-données)
4. [Schéma de la base de données](#4-schéma-de-la-base-de-données)
5. [Référence des modules](#5-référence-des-modules)
6. [Lancer les tests](#6-lancer-les-tests)
7. [Lint et vérification de types](#7-lint-et-vérification-de-types)
8. [Ajouter une traduction](#8-ajouter-une-traduction)
9. [Ajouter une source de données](#9-ajouter-une-source-de-données)
10. [Contribuer](#10-contribuer)

---

## 1. Structure du projet

```
steam_tracker/
├── __init__.py
├── models.py      # Modèles Pydantic v2
├── api.py         # Wrappers HTTP typés vers l'API Steam
├── db.py          # Couche de persistance SQLite
├── fetcher.py     # Fetcher multi-threadé + RateLimiter
├── renderer.py    # Générateur HTML statique
├── cli.py         # Points d'entrée steam-fetch / steam-render
└── i18n/
    ├── __init__.py  # Translator, get_translator(), detect_lang()
    ├── en.py        # Chaînes anglaises
    └── fr.py        # Chaînes françaises
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_db.py
│   ├── test_fetcher.py
│   └── test_renderer.py
├── docs/
│   ├── en/            # Documentation anglaise
│   └── fr/            # Documentation française
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

---

## 2. Vue d'ensemble de l'architecture

```
Steam Web API ──┐
Steam Store API ─┤  api.py  ──►  fetcher.py  ──►  db.py  ──►  renderer.py  ──►  HTML
                │  (wrappers HTTP)  (ThreadPool)  (SQLite)   (sans Jinja)
Wishlist API ───┘
```

**Flux de données :**

1. `cli.py:cmd_fetch` appelle `api.py` pour récupérer les jeux possédés, la wishlist et les jeux suivis
2. Chaque `OwnedGame` est upsertée dans la table `games` immédiatement
3. `fetcher.py:SteamFetcher.fetch_all()` dispatche des requêtes concurrentes pour les app details et les news
   - Les jeux dont les app details sont en cache sont ignorés (`skip_appids`)
   - Les jeux dont les news sont périmées (> `--news-age` heures) reçoivent uniquement un re-fetch des news (`refresh_news_appids`)
4. Les résultats sont persistés via `db.py:upsert_app_details` et `db.py:upsert_news`
5. `cli.py:cmd_render` lit tous les enregistrements via `db.py:get_all_game_records` et les passe à `renderer.py`

---

## 3. Modèles de données

Tous les modèles se trouvent dans `steam_tracker/models.py` et utilisent **Pydantic v2**.

### `OwnedGame`

Représente un jeu provenant de n'importe quelle source.

| Champ | Type | Description |
|---|---|---|
| `appid` | `int` | Steam App ID |
| `name` | `str` | Nom d'affichage |
| `playtime_forever` | `int` | Total de minutes jouées |
| `playtime_2weeks` | `int` | Minutes jouées ces 2 dernières semaines |
| `rtime_last_played` | `int` | Timestamp Unix de la dernière session |
| `img_icon_url` | `str` | Fragment d'URL de l'icône |
| `img_logo_url` | `str` | Fragment d'URL du logo |
| `source` | `str` | `"owned"` \| `"wishlist"` \| `"followed"` |

### `AppDetails`

Métadonnées enrichies depuis l'API Steam Store.

| Champ | Type | Description |
|---|---|---|
| `appid` | `int` | Steam App ID |
| `name` | `str` | Nom Store |
| `app_type` | `str` | `"game"`, `"dlc"`, `"demo"`, … |
| `short_description` | `str` | Description courte Store |
| `early_access` | `bool` | En Early Access |
| `coming_soon` | `bool` | Pas encore sorti |
| `release_date_str` | `str` | Date de sortie lisible |
| `developers` / `publishers` | `list[str]` | Noms de studio |
| `genres` / `categories` | `list[str]` | Tags de taxonomie |
| `is_free` | `bool` | Free-to-play |
| `price_initial` / `price_final` | `int` | Centimes dans la devise du Store |
| `price_discount_pct` | `int` | Pourcentage de réduction |
| `price_currency` | `str` | Code devise ISO |
| `platform_windows/mac/linux` | `bool` | Disponibilité par plateforme |
| `metacritic_score` | `int` | 0–100 |
| `metacritic_url` | `str` | URL page Metacritic |
| `achievement_count` | `int` | Nombre d'achievements |
| `recommendation_count` | `int` | Nombre d'avis Steam |
| `header_image` / `background_image` | `str` | URLs CDN des images |
| `supported_languages` | `str` | Chaîne HTML brute Steam |
| `website` | `str` | URL du site officiel |
| `fetched_at` | `datetime` | Timestamp UTC du dernier fetch |

### `NewsItem`

Un article de news.

| Champ | Type | Description |
|---|---|---|
| `appid` | `int` | App ID du jeu parent |
| `gid` | `str` | GID Steam de la news |
| `title` | `str` | Titre de l'article |
| `date` | `datetime` | Date de publication (UTC) |
| `url` | `str` | URL complète de l'article |
| `author` | `str` | Nom de l'auteur |
| `feedname` / `feedlabel` | `str` | Identifiant / nom d'affichage du feed |
| `tags` | `list[str]` | Liste de tags |
| `fetched_at` | `datetime` | Timestamp UTC du dernier fetch |

### `GameRecord`

Agrégat dénormalisé passé au renderer.

```python
@dataclass
class GameRecord:
    game: OwnedGame
    details: AppDetails | None
    news: list[NewsItem]
    status: GameStatus
```

### `GameStatus`

```python
@dataclass
class GameStatus:
    label: str    # Lisible ("Sorti (1.0)", "Early Access", …)
    badge: str    # Classe CSS ("released", "earlyaccess", "unreleased", "unknown")
    release_date: str
```

---

## 4. Schéma de la base de données

Trois tables ; clés étrangères activées ; mode journal WAL.

```sql
-- Une ligne par appid suivi
CREATE TABLE games (
    appid             INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL,
    playtime_forever  INTEGER NOT NULL DEFAULT 0,
    playtime_2weeks   INTEGER NOT NULL DEFAULT 0,
    rtime_last_played INTEGER NOT NULL DEFAULT 0,
    img_icon_url      TEXT    NOT NULL DEFAULT '',
    img_logo_url      TEXT    NOT NULL DEFAULT '',
    last_seen_at      TEXT    NOT NULL,
    source            TEXT    NOT NULL DEFAULT 'owned'
);

-- Une ligne par appid (métadonnées Store)
CREATE TABLE app_details (
    appid                INTEGER PRIMARY KEY REFERENCES games(appid) ON DELETE CASCADE,
    name                 TEXT    NOT NULL DEFAULT '',
    -- ... (tous les champs AppDetails)
    fetched_at           TEXT    NOT NULL
);

-- Plusieurs lignes par appid (articles de news)
CREATE TABLE news (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    appid      INTEGER NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    gid        TEXT    NOT NULL DEFAULT '',
    title      TEXT    NOT NULL,
    date       TEXT    NOT NULL,
    url        TEXT    NOT NULL,
    author     TEXT    NOT NULL DEFAULT '',
    feedname   TEXT    NOT NULL DEFAULT '',
    feedlabel  TEXT    NOT NULL DEFAULT '',
    tags       TEXT    NOT NULL DEFAULT '[]',
    fetched_at TEXT    NOT NULL,
    UNIQUE (appid, url)
);
```

### Migrations additives

Les nouvelles colonnes sont ajoutées via `_MIGRATIONS` dans `db.py` — une liste de tuples `(table, colonne, définition)` appliqués via `ALTER TABLE … ADD COLUMN` si la colonne n'existe pas encore. Cela assure la compatibilité ascendante des bases existantes sans framework de migration.

### Priorité de source dans les upserts

Quand un même jeu apparaît dans plusieurs sources, `upsert_game` utilise une expression SQL `CASE WHEN` pour appliquer la priorité : **owned > wishlist > followed**. Le temps de jeu et les timestamps ne sont mis à jour que pour les jeux `source = 'owned'`.

---

## 5. Référence des modules

### `api.py`

| Fonction | Endpoint | Description |
|---|---|---|
| `get_owned_games(key, steamid)` | `IPlayerService/GetOwnedGames/v1` | Retourne `list[OwnedGame]` |
| `get_wishlist(key, steamid)` | `IWishlistService/GetWishlist/v1` | Retourne `list[OwnedGame]` avec `source="wishlist"` |
| `get_followed_games(key, steamid)` | `IPlayerService/GetFollowedGames/v1` | Retourne `list[OwnedGame]` avec `source="followed"` (généralement vide) |
| `get_app_details(appid)` | `store.steampowered.com/api/appdetails` | Retourne `AppDetails \| None` |
| `get_app_news(appid, count)` | `ISteamNews/GetNewsForApp/v2` | Retourne `list[NewsItem]` |

Les erreurs HTTP 403/404 sur les endpoints news/details sont loguées en DEBUG (pas en WARNING — Steam retourne régulièrement ces codes pour les DLC et les apps non-jeu).

### `db.py — Database`

| Méthode | Description |
|---|---|
| `upsert_game(game)` | Insère ou met à jour une ligne dans `games` (priorité source appliquée) |
| `upsert_app_details(details)` | Insère ou remplace dans `app_details` ; renseigne le nom vide dans `games` |
| `upsert_news(appid, items)` | Insère des news (INSERT OR IGNORE sur URL dupliquée) |
| `get_cached_appids()` | Ensemble des appids déjà dans `app_details` |
| `get_stale_news_appids(max_age_s)` | Ensemble des appids sans news ou dont les news ont plus de `max_age_s` secondes |
| `get_all_game_records()` | Liste dénormalisée complète pour le renderer |

### `fetcher.py — SteamFetcher`

```python
SteamFetcher(
    rate_limit: float = 1.5,   # secondes entre les requêtes app_details (partagé entre threads)
    max_workers: int = 4,
    news_per_game: int = 5,
    on_progress: Callable[[int, int, str], None] | None = None,
)
```

`fetch_all(games, skip_appids, refresh_news_appids)` retourne `dict[int, tuple[AppDetails | None, list[NewsItem]]]`.

- `skip_appids` — jeux à ignorer entièrement
- `refresh_news_appids` — sous-ensemble des jeux skippés dont les news doivent être re-fetchées (sans rate limiting — l'endpoint news n'est pas limité)

### `renderer.py`

Deux fonctions publiques : `write_html` et `write_news_html`. Elles acceptent une `list[GameRecord]`, un `steam_id` pour l'en-tête, un `Path` de sortie, optionnellement un href de lien croisé, et un code `lang` optionnel.

Le HTML est construit par interpolation de chaînes dans les raw strings `_HTML_TEMPLATE` et `_NEWS_TEMPLATE`. Aucune bibliothèque de templating externe n'est utilisée. Les libellés visibles utilisent des placeholders `__T_key__` remplacés au moment du rendu via `_apply_html_t()` ; les chaînes JavaScript sont injectées sous forme d'un bloc `const I18N = {...}` via `_build_i18n_js()`.

### `i18n/__init__.py`

| Symbole | Description |
|---|---|
| `detect_lang()` | Lit les variables d'env `LANGUAGE` / `LC_ALL` / `LC_MESSAGES` / `LANG` puis `locale.getdefaultlocale()`, retourne un code à 2 lettres, défaut `"en"` |
| `Translator` | Classe appelable ; `t("key")` retourne la chaîne traduite, `t("key", param=val)` effectue une substitution `str.format` ; repli sur l'anglais si la clé manque |
| `get_translator(lang)` | Retourne un `Translator` pour le code lang donné (ou auto-détecté) ; les codes inconnus replient sur `"en"` |

---

## 6. Lancer les tests

```bash
# Tous les tests avec couverture
pytest

# Rapide (sans couverture)
pytest -q --no-cov

# Module unique
pytest tests/test_api.py -v
```

Les tests utilisent `responses` pour mocker les appels HTTP et les fixtures `pytest` définies dans `conftest.py`.

Rapport de couverture HTML :

```bash
pytest --cov-report=html
# puis ouvrir htmlcov/index.html
```

---

## 7. Lint et vérification de types

```bash
# Lint (ruff)
ruff check steam_tracker

# Auto-correction
ruff check steam_tracker --fix

# Vérification de types (mypy strict)
mypy steam_tracker
```

La configuration se trouve dans `pyproject.toml` sous `[tool.ruff]` et `[tool.mypy]`.

Points notables :
- Longueur de ligne : **100** (E501 ignoré dans `renderer.py` pour les longues lignes CSS/JS inline)
- mypy : `strict = true`
- Règles ruff : `E F W I UP N B A C4 SIM`

---

## 8. Ajouter une traduction

1. Créer `steam_tracker/i18n/<code>.py` (ex. `de.py` pour l'allemand) avec un unique `STRINGS: dict[str, str]` qui reprend les clés de `en.py`. Seules les clés à traduire sont nécessaires — les clés manquantes replient automatiquement sur l'anglais.

2. Enregistrer le module dans `steam_tracker/i18n/__init__.py` :
   ```python
   _SUPPORTED = {"en": en, "fr": fr, "de": de}   # ajouter l'import et l'entrée
   ```

3. Les utilisateurs pourront alors passer `--lang de` ou utiliser une locale système allemande.

---

## 9. Ajouter une source de données

Pour ajouter une nouvelle source de jeux (ex. Epic Games, GOG) :

1. **`models.py`** — ajouter la nouvelle valeur dans le commentaire/docstring du champ `source` (le champ est une `str` simple, pas un enum).

2. **`api.py`** — écrire une nouvelle fonction `get_<source>_games(...)` retournant `list[OwnedGame]` avec `source="<source>"`.

3. **`db.py`** — mettre à jour l'expression `CASE WHEN` de priorité des sources dans `upsert_game` si la nouvelle source nécessite une priorité spécifique.

4. **`cli.py`** — ajouter un flag `--<source>` / `--no-<source>` dans `cmd_fetch`, appeler la nouvelle fonction API, upsert les résultats, et ajouter les nouveaux jeux à la liste `games`.

5. **`renderer.py`** — ajouter optionnellement un bouton de filtre dans `_HTML_TEMPLATE` (div `#sourceBtns`) et un label d'affichage dans `make_card()`.

6. **Tests** — ajouter des tests unitaires dans `tests/test_api.py` et des tests d'intégration dans `tests/test_db.py`.

---

## 10. Contribuer

```bash
# 1. Créer une branche
git checkout -b feat/ma-fonctionnalite

# 2. Faire les changements, ajouter des tests
# 3. Vérifier que tout passe
ruff check steam_tracker
mypy steam_tracker
pytest

# 4. Commiter (conventional commits recommandé)
git commit -m "feat: ajouter source Epic Games"

# 5. Ouvrir une pull request vers main
```

**Style de commit :** `feat:` · `fix:` · `refactor:` · `docs:` · `test:` · `chore:`

**Avant d'ouvrir une PR :**
- Toutes les vérifications ruff passent
- mypy ne rapporte aucune erreur
- Tous les tests existants passent ; le nouveau comportement est couvert par des tests
- `CHANGELOG.md` est mis à jour dans la section `[Unreleased]`
