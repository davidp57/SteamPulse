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
8. [CI/CD](#8-cicd)
9. [Ajouter une traduction](#9-ajouter-une-traduction)
10. [Ajouter un plugin source](#10-ajouter-un-plugin-source)
11. [Contribuer](#11-contribuer)

---

## 1. Structure du projet

```
steam_tracker/
├── __init__.py
├── models.py      # Modèles Pydantic v2
├── api.py         # Wrappers HTTP typés vers l'API Steam (enrichissement uniquement : details + news)
├── epic_api.py    # Wrappers OAuth2 + API bibliothèque Epic Games
├── resolver.py    # Chaîne de résolution Steam AppID (IGDB, Steam Store Search)
├── db.py          # Couche de persistance SQLite
├── fetcher.py     # Fetcher multi-threadé + RateLimiter
├── renderer.py    # Générateur HTML statique
├── cli.py         # Points d'entrée steam-fetch / steam-render / steampulse
├── sources/
│   ├── __init__.py  # Protocole GameSource + registre get_all_sources()
│   ├── steam.py     # SteamSource : bibliothèque possédée, wishlist, jeux suivis
│   └── epic.py      # EpicSource : bibliothèque Epic Games Store
└── i18n/
    ├── __init__.py  # Translator, get_translator(), detect_lang()
    ├── en.py        # Chaînes anglaises
    └── fr.py        # Chaînes françaises
tests/
├── conftest.py
├── test_api.py
├── test_db.py
├── test_epic.py
├── test_fetcher.py
├── test_renderer.py
├── test_resolver.py
└── test_sources.py
docs/
├── en/            # Documentation anglaise
└── fr/            # Documentation française
pyproject.toml
README.md
CHANGELOG.md
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

1. `cli.py:cmd_fetch` itère sur `get_all_sources()` et appelle `discover_games(args)` sur chaque plugin actif pour récupérer la liste des jeux
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
| `source` | `str` | `"owned"` \| `"wishlist"` \| `"followed"` \| `"epic"` |
| `external_id` | `str` | Identifiant externe (ex. `"epic:<catalogItemId>"`) — vide pour les jeux Steam natifs |

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

Trois tables principales plus un cache de mapping AppID ; clés étrangères activées ; mode journal WAL.

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
    source            TEXT    NOT NULL DEFAULT 'owned',
    external_id       TEXT    NOT NULL DEFAULT ''
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

-- Correspondance IDs de jeux externes vers Steam AppIDs
CREATE TABLE appid_mappings (
    external_source TEXT NOT NULL,   -- "epic", "gog", ...
    external_id     TEXT NOT NULL,   -- ID catalogue spécifique au store
    external_name   TEXT NOT NULL,   -- nom du jeu sur le store externe
    steam_appid     INTEGER,         -- NULL si non résolu
    resolved_at     TEXT NOT NULL,
    manual          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (external_source, external_id)
);
```

### Migrations additives

Les nouvelles colonnes sont ajoutées via `_MIGRATIONS` dans `db.py` — une liste de tuples `(table, colonne, définition)` appliqués via `ALTER TABLE … ADD COLUMN` si la colonne n'existe pas encore. Cela assure la compatibilité ascendante des bases existantes sans framework de migration.

### Priorité de source dans les upserts

Quand un même jeu apparaît dans plusieurs sources, `upsert_game` utilise une expression SQL `CASE WHEN` pour appliquer la priorité : **owned = epic > wishlist > followed**. Le temps de jeu et les timestamps ne sont mis à jour que pour les jeux `source = 'owned'`.

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
| `get_appid_mapping(source, external_id)` | AppID Steam en cache pour un jeu externe, ou `None` |
| `upsert_appid_mapping(source, external_id, name, steam_appid, manual)` | Insère/met à jour un mapping AppID ; les mappings manuels sont protégés contre l'écrasement automatique |
| `run_cleanup()` | Exécute toutes les règles de nettoyage enregistrées ; retourne le nombre total de lignes affectées |

#### Système de nettoyage de données

`Database.run_cleanup()` exécute une liste de règles de nettoyage stockées dans l'attribut de classe `_CLEANUP_RULES`. Chaque règle est une méthode `_cleanup_*(self) -> int` qui corrige ou supprime les données obsolètes ou cassées issues de précédentes exécutions. La méthode retourne le nombre total de lignes affectées, toutes règles confondues.

Le nettoyage s'exécute **automatiquement** au début de chaque invocation `cmd_fetch` / `cmd_run`, avant la découverte des jeux. Si des lignes sont nettoyées, un message est affiché à l'utilisateur.

**Ajouter une nouvelle règle de nettoyage :**

1. Ajouter une méthode privée `_cleanup_<description>(self) -> int` à la classe `Database`
2. La méthode doit corriger ou supprimer les données problématiques et retourner le nombre de lignes affectées
3. Ajouter la référence de la méthode à `_CLEANUP_RULES`

**Règles actuelles :**

| Règle | Objectif |
|---|---|
| `_cleanup_epic_live_name` | Supprime les jeux Epic nommés `"Live"` (causé par un bug qui utilisait le champ `sandboxName` — le label d'environnement de déploiement — au lieu du vrai titre du jeu). Supprime aussi les entrées `appid_mappings` correspondantes pour que le resolver re-tente une découverte propre au prochain fetch. |

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

Fonctions publiques : `write_html` (page bibliothèque) et `write_alerts_html` (page alertes). Les deux acceptent un `steam_id` pour l'en-tête, un `Path` de sortie, optionnellement un href de lien croisé, et un code `lang` optionnel. `write_html` prend une `list[GameRecord]`, tandis que `write_alerts_html` prend une `list[Alert]` et un `dict[int, GameRecord]`.

Le HTML est construit par interpolation de chaînes dans les raw strings `_HTML_TEMPLATE` et `_ALERTS_TEMPLATE`. Aucune bibliothèque de templating externe n'est utilisée. Les libellés visibles utilisent des placeholders `__T_key__` remplacés au moment du rendu via `_apply_html_t()` ; les chaînes JavaScript sont injectées sous forme d'un bloc `const I18N = {...}` via `_build_i18n_js()`.

### `sources/__init__.py — GameSource`

| Symbole | Description |
|---|---|
| `GameSource` | Protocole `runtime_checkable` — toute classe avec `name`, `add_arguments()`, `is_enabled()`, `discover_games()` le satisfait |
| `get_all_sources()` | Retourne une nouvelle liste de toutes les instances `GameSource` enregistrées |

### `sources/steam.py — SteamSource`

`SteamSource` implémente `GameSource` pour Steam. Il enregistre `--key`, `--steamid`, `--no-wishlist` et `--followed` comme arguments CLI et délègue aux trois fonctions de découverte de `api.py`.

`discover_games(args)` retourne **tous** les jeux de chaque sous-source (possédés, puis wishlist, puis suivis) — potentiellement avec le même `appid` sous différents labels `source`. Le CLI les upsert tous en base (qui applique la priorité `owned > wishlist > followed`) puis construit une liste dédupliquée pour le fetcher.

### `sources/epic.py — EpicSource`

`EpicSource` implémente `GameSource` pour l'Epic Games Store. Il enregistre `--epic-auth-code`, `--epic-device-id`, `--epic-account-id`, `--epic-device-secret`, `--twitch-client-id` et `--twitch-client-secret` comme arguments CLI.

`is_enabled(args)` retourne `True` si un code d'auth ou des credentials device complets sont fournis.

`discover_games(args)` s'authentifie auprès d'Epic, récupère la bibliothèque, et pour chaque jeu :
- Résout l'AppID Steam via `resolve_steam_appid()` (fallback Steam Store Search)
- Si résolu : définit `appid = steam_appid` pour enrichissement complet
- Si non résolu : génère un appid déterministe basé sur un hash (≥ 2 000 000 000)
- Tous les jeux reçoivent `source="epic"` et `external_id="epic:<catalogItemId>"`

### `resolver.py`

| Symbole | Description |
|---|---|
| `AppIdResolver` | Protocole — toute classe avec `resolve(name, session) → int \| None` le satisfait |
| `SteamStoreResolver` | Résolution via l'API Steam Store Search avec correspondance floue (SequenceMatcher ≥ 0.8) |
| `IGDBResolver(twitch_client_id, twitch_client_secret)` | Résolution via IGDB : OAuth Twitch → recherche de jeu → lookup external_games (category=Steam) |
| `resolve_steam_appid(name, resolvers, session)` | Itère les resolvers dans l'ordre ; le premier résultat l'emporte |

### `epic_api.py`

| Fonction | Description |
|---|---|
| `epic_auth_with_code(auth_code)` | Échange un code d'autorisation Epic contre un token d'accès |
| `epic_auth_with_device(device_id, account_id, secret)` | Authentification via credentials device persistants |
| `epic_get_library(access_token)` | Récupère la bibliothèque Epic de l'utilisateur avec pagination |

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

## 8. CI/CD

Deux workflows GitHub Actions se trouvent dans `.github/workflows/`.

### `ci.yml` — Quality gate

Déclenché sur chaque **push** ou **pull request** ciblant `main` ou `master`.

| Propriété | Valeur |
|---|---|
| Runner | `windows-latest` |
| Matrice Python | 3.11 · 3.12 · 3.13 |
| Commande d'installation | `pip install -e ".[dev]"` |

**Étapes (dans l'ordre) :**

1. `ruff check steam_tracker` — lint, zéro avertissement requis
2. `mypy steam_tracker` — vérification de types stricte, zéro erreur requise
3. `pytest -q --tb=short` — suite de tests complète

Les trois étapes doivent passer sur les trois versions de Python pour que le workflow réussisse. Ce workflow **ne publie aucun artefact**.

### `build.yml` — Release de l'EXE Windows

Déclenché sur :
- un **push de tag** correspondant à `v*.*.*` (ex. `v1.2.0`) → build complet + GitHub Release
- un **déclenchement manuel** (`workflow_dispatch`) → build + upload d'artefact uniquement (pas de release)

| Propriété | Valeur |
|---|---|
| Runner | `windows-latest` |
| Python | 3.11 (fixe) |
| Commande d'installation | `pip install -e ".[build]"` |
| Permissions | `contents: write` (nécessaire pour publier une GitHub Release) |

**Étapes (dans l'ordre) :**

1. **Build** — exécute `pyinstaller steampulse.spec` depuis le répertoire `build/` ; produit `dist/steampulse.exe`.
2. **Smoke test** — exécute `dist\steampulse.exe --help` pour vérifier que l'exécutable démarre correctement.
3. **Version** — lit la version du package via `importlib.metadata` et l'expose en tant qu'output `VERSION`.
4. **Archive** — compresse `steampulse.exe` dans `steampulse-v<VERSION>-windows-x64.zip`.
5. **Upload artefact** — téléverse toujours le zip comme artefact de workflow (téléchargeable depuis la page du run Actions).
6. **Notes de release** — extrait la section de la version courante dans `CHANGELOG.md` via une regex PowerShell ; replie sur un lien vers le changelog si la section est introuvable.
7. **Publication de release** *(tag uniquement)* — crée ou met à jour la GitHub Release pour le tag via `softprops/action-gh-release@v2`, en attachant le zip et les notes de release extraites.

### Déclencher une release

```bash
# Tagger le commit et pousser — build.yml se déclenche automatiquement
git tag v1.2.0
git push origin v1.2.0
```

Mettez à jour `CHANGELOG.md` avec une section `## [1.2.0]` **avant** de pousser le tag pour que les notes de release soient correctement extraites.

---

## 9. Ajouter une traduction

1. Créer `steam_tracker/i18n/<code>.py` (ex. `de.py` pour l'allemand) avec un unique `STRINGS: dict[str, str]` qui reprend les clés de `en.py`. Seules les clés à traduire sont nécessaires — les clés manquantes replient automatiquement sur l'anglais.

2. Enregistrer le module dans `steam_tracker/i18n/__init__.py` :
   ```python
   _SUPPORTED = {"en": en, "fr": fr, "de": de}   # ajouter l'import et l'entrée
   ```

3. Les utilisateurs pourront alors passer `--lang de` ou utiliser une locale système allemande.

---

## 10. Ajouter un plugin source

Pour ajouter un nouveau plugin source (ex. GOG, Epic Games) :

1. **Créer `steam_tracker/sources/<nom>.py`** avec une classe satisfaisant le protocole `GameSource` :

   ```python
   class GogSource:
       name = "gog"

       def add_arguments(self, parser: argparse.ArgumentParser) -> None:
           parser.add_argument("--gog-token", help="Token OAuth GOG")

       def is_enabled(self, args: argparse.Namespace) -> bool:
           return bool(getattr(args, "gog_token", None))

       def discover_games(self, args: argparse.Namespace) -> list[OwnedGame]:
           # récupérer depuis l'API GOG, mapper vers OwnedGame avec source="gog"
           ...
   ```

2. **Enregistrer la source** dans `steam_tracker/sources/__init__.py` :

   ```python
   def get_all_sources() -> list[GameSource]:
       from .steam import SteamSource
       from .gog import GogSource  # ajouter ceci
       return [SteamSource(), GogSource()]  # ajouter l'instance
   ```

3. **Correspondance avec les AppIDs Steam** — Le pipeline d'enrichissement (details, news) fonctionne via les AppIDs Steam. Utilisez le système de résolution dans `steam_tracker/resolver.py` (`SteamStoreResolver` pour la correspondance floue zéro-config, `IGDBResolver` si des credentials Twitch/IGDB sont disponibles) via `resolve_steam_appid(name, resolvers)`. Les AppIDs résolus peuvent être mis en cache dans la table `appid_mappings`. Si aucun AppID n'est trouvé, définissez un appid déterministe basé sur un hash (≥ 2 000 000 000) et un `external_id` non vide — le CLI exclura ces jeux du pipeline d'enrichissement Steam.

4. **Ajouter des tests** dans `tests/test_sources.py` — couvrir `add_arguments`, `is_enabled` et `discover_games` avec des appels HTTP mockés.

---

## 11. Contribuer

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
