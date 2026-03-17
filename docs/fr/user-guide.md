# SteamPulse — Guide utilisateur

🌐 [English version](../en/user-guide.md)

## Sommaire

1. [Installation](#1-installation)
2. [Démarrage rapide — Assistant de configuration](#2-démarrage-rapide--assistant-de-configuration)
3. [Fichier de configuration](#3-fichier-de-configuration)
4. [Obtenir les prérequis Steam](#4-obtenir-les-prérequis-steam)
5. [Prérequis Epic Games](#5-prérequis-epic-games)
6. [Tout-en-un — `steampulse.exe`](#6-tout-en-un--steampulseexe)
7. [Options complètes](#7-options-complètes)
8. [Naviguer dans l'interface](#8-naviguer-dans-linterface)
9. [Stratégie de cache et rafraîchissement](#9-stratégie-de-cache-et-rafraîchissement)
10. [Usage avancé — étapes séparées](#10-usage-avancé--étapes-séparées)
11. [FAQ](#11-faq)

---

## 1. Installation

### Option A — Exécutable standalone (recommandé, Windows uniquement)

Télécharge `steampulse.exe` depuis la [dernière release GitHub](https://github.com/davidp57/SteamPulse/releases/latest).  
Aucun Python requis. Place le fichier où tu le souhaites et lance-le depuis un terminal.

### Option B — Depuis les sources (Python 3.11+)

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux / macOS
pip install -e .
```

Dans ce cas, remplace `steampulse.exe` par `steampulse` dans tous les exemples qui suivent.

---

---

## 2. Démarrage rapide — Assistant de configuration

La façon la plus simple de commencer est l'assistant de configuration interactif. Il te guide étape par étape à travers tous les credentials et paramètres, puis écrit un fichier de config pour que tu n'aies plus jamais à passer de flags en ligne de commande.

### Lancer l'assistant

```
steam-setup
```

Ou, si tu utilises l'exécutable standalone, lance-le simplement sans flags la première fois — l'assistant démarrera automatiquement quand aucun identifiant n'est trouvé :

```
steampulse.exe
```

Tu peux aussi forcer l'assistant à tout moment avec `--setup` :

```
steampulse.exe --setup
```

### Ce que couvre l'assistant

1. **Steam** — clé API et SteamID64
2. **Epic Games** (optionnel) — flux OAuth2 complet : l'assistant affiche l'URL d'auth, ouvre éventuellement ton navigateur, demande le code d'autorisation, et l'échange automatiquement contre un refresh token persistant. Pas de navigation JSON manuelle.
3. **Twitch/IGDB** (optionnel) — client ID et secret pour une meilleure résolution Epic→Steam AppID
4. **Paramètres** (optionnel) — chemin de la base, threads de travail, âge des news, langue

À la fin, l'assistant affiche un résumé et demande confirmation avant d'écrire le fichier.

### Emplacement du fichier de config

| Plateforme | Chemin |
|---|---|
| Windows | `%APPDATA%\steampulse\config.toml` |
| Linux / macOS | `$XDG_CONFIG_HOME/steampulse/config.toml` (défaut : `~/.config/steampulse/config.toml`) |

Un message est affiché à chaque chargement ou écriture du fichier :
```
  ✔ Config loaded from C:\Users\toi\AppData\Roaming\steampulse\config.toml
```

---

## 3. Fichier de configuration

SteamPulse charge automatiquement `config.toml` à chaque lancement. Les flags CLI ont toujours la priorité sur les valeurs du fichier, et les nouveaux credentials passés en ligne de commande sont automatiquement sauvegardés dans le fichier.

### Format du fichier

```toml
[steam]
key      = "TA_CLE_API_STEAM"
steamid  = "76561198000000000"

[epic]
refresh_token = "..."
account_id    = "..."

[twitch]
client_id     = "..."
client_secret = "..."

[settings]
db        = "steam_library.db"
workers   = 4
news_age  = 24
lang      = "fr"
```

Toutes les sections et clés sont optionnelles — celles absentes utilisent les valeurs par défaut CLI.

### Chemin de config personnalisé

Tu peux pointer vers un autre fichier de config avec `--config` :

```
steampulse.exe --config /chemin/vers/maconfig.toml
```

---

## 4. Obtenir les prérequis Steam

### Clé API Steam

1. Connecte-toi sur <https://steamcommunity.com/dev/apikey>
2. Entre un nom de domaine quelconque (ex. `localhost`)
3. Copie la clé affichée (32 caractères hexadécimaux)

> ⚠️ La clé donne accès en lecture à ton compte. Ne la partage pas et ne la commite pas dans un dépôt.

### Ton SteamID64

Rends-toi sur <https://steamid.io>, entre ton pseudo Steam ou l'URL de ton profil.  
Le SteamID64 est un nombre à 17 chiffres commençant par `765`.

---

## 5. Prérequis Epic Games

L'intégration Epic est **optionnelle**. Passe cette section si tu utilises uniquement Steam.

SteamPulse peut importer ta bibliothèque Epic Games et tenter de résoudre chaque jeu vers un AppID Steam (pour récupérer les détails du store et les news). Les jeux non résolus apparaissent quand même dans le dashboard, tagués Epic, sans enrichissement Steam.

### Authentification — premier lancement (code d'autorisation)

1. Ouvre un navigateur et va sur :  
   `https://www.epicgames.com/id/login?redirectUrl=https%3A%2F%2Fwww.epicgames.com%2Fid%2Fapi%2Fredirect%3FclientId%3D34a02cf8f4414e29b15921876da36f9a%26responseType%3Dcode`
2. Connecte-toi avec ton compte Epic.
3. Tu seras redirigé vers une page JSON — copie la valeur de `authorizationCode`.
4. Passe-la avec `--epic-auth-code <CODE>`. C'est un code **à usage unique**.

### Authentification — lancements suivants (refresh token)

Après la première connexion, l'assistant (ou le flux `--epic-auth-code`) sauvegarde automatiquement un **refresh token** dans le fichier de config. Lors des lancements suivants, SteamPulse le réutilise de façon transparente. Le token est valide 30 jours et se renouvelle automatiquement à chaque utilisation — il n'expire donc jamais en pratique avec un usage régulier.

Tu peux aussi le passer explicitement en ligne de commande :

```
steampulse.exe --key <API_KEY> --steamid <STEAMID64> \
  --epic-refresh-token <TOKEN> \
  --epic-account-id <ACCOUNT_ID>
```

### Optionnel — résolveur IGDB

Pour une meilleure résolution des AppIDs Steam, fournis des credentials Twitch (utilisés pour interroger IGDB) :

1. Crée une app sur <https://dev.twitch.tv/console/apps>
2. Passe `--twitch-client-id` et `--twitch-client-secret`

Sans IGDB, SteamPulse utilise la correspondance floue via l'API de recherche Steam Store.

---

## 6. Tout-en-un — `steampulse.exe`

```
steampulse.exe --key <API_KEY> --steamid <STEAMID64>
```

Cette commande unique :
1. Récupère ta bibliothèque, ta wishlist et les news de chaque jeu via l'API Steam
2. Sauvegarde tout dans une base SQLite locale
3. Génère les pages HTML directement

À la fin, ouvre `steam_library.html` dans un navigateur — **aucun serveur requis**.

**Avec Epic Games :**
```
steampulse.exe --key <API_KEY> --steamid <STEAMID64> --epic-auth-code <CODE>
```

### Ce qui est récupéré

Pour chaque jeu Steam (possédé, wishlist ou suivi) :
- **App details** : nom, type, description, développeurs, éditeurs, genres, catégories, plateformes, prix, score Metacritic, achievements, date de sortie
- **News** : les 5 dernières actualités officielles (titre, date, URL, auteur, tags)

Pour chaque jeu **Epic** : le jeu est résolu vers un AppID Steam si possible — si trouvé, le même enrichissement s'applique. Les jeux non résolus apparaissent dans le dashboard sans détails store ni news.

### Exemple de sortie

```
📦 Récupération de la bibliothèque Steam...
   ✅ 2190 jeu(x) possédé(s)
🎁 Récupération de la wishlist...
   ✅ 54 jeu(x) en wishlist · 54 nouveau(x)
   12 jeu(x) à récupérer · 387 news à rafraîchir (1845 déjà à jour)
[  1/399] Elden Ring
[  2/399] Cyberpunk 2077
...
✅ Fetch terminé — 399 entrée(s) mise(s) à jour dans steam_library.db
🖥  Génération des pages HTML...
✅ 2244 jeux · bibliothèque → C:\...\steam_library.html
   11220 news → C:\...\steam_news.html
```

---

## 7. Options complètes

| Option | Défaut | Description |
|---|---|---|
| `--key` | *(config ou requis)* | Clé Steam Web API |
| `--steamid` | *(config ou requis)* | SteamID64 du profil |
| `--db` | `steam_library.db` | Chemin vers la base SQLite |
| `--output` | `steam_library.html` | Chemin de la page bibliothèque générée |
| `--workers` | `4` | Nombre de threads parallèles |
| `--max N` | *(aucun)* | Limiter le fetch à N jeux (tests) |
| `--refresh` | désactivé | Ignorer le cache, tout re-fetcher |
| `--news-age HOURS` | `24` | Rafraîchir les news des jeux dont le cache dépasse N heures |
| `--no-wishlist` | désactivé | Ne pas récupérer la wishlist |
| `--followed` | désactivé | Récupérer les jeux suivis (opt-in, voir note) |
| `--lang` | *(système)* | Forcer la langue de l'interface (`en`, `fr`, …). Par défaut la locale système, repli sur `en`. |
| `--config` | *(défaut plateforme)* | Chemin vers un fichier de config TOML personnalisé |
| `--setup` | désactivé | Lancer l'assistant de configuration interactif |
| `-v` / `--verbose` | désactivé | Afficher les logs DEBUG |

**Options Epic Games :**

| Option | Défaut | Description |
|---|---|---|
| `--epic-auth-code` | *(aucun)* | Code d'autorisation Epic à usage unique (premier login) |
| `--epic-refresh-token` | *(aucun)* | Refresh token Epic (auth persistante, sauvegardé automatiquement après le premier login) |
| `--epic-account-id` | *(aucun)* | Account ID Epic (requis avec `--epic-refresh-token`) |
| `--twitch-client-id` | *(aucun)* | Client ID Twitch/IGDB (meilleure résolution AppID) |
| `--twitch-client-secret` | *(aucun)* | Client secret Twitch/IGDB |

> **Note `--followed`** : l'API Steam Web ne retourne plus les jeux suivis avec une clé standard. Cette option est disponible mais retournera généralement une liste vide.

---

## 8. Naviguer dans l'interface

### Page bibliothèque (`steam_library.html`)

**Barre d'outils — ligne principale (toujours visible) :**
- **Recherche** — filtre les jeux par nom en temps réel (`/` ou `Ctrl+K`)
- **Tri** — par nom, score Metacritic, temps de jeu, date de sortie, dernière mise à jour, date dernière news
- **⚙ Filtres** — affiche / masque le panneau de filtres ; un badge indique le nombre de filtres actifs
- **Reset** — réinitialise tous les filtres et la recherche (apparaît uniquement si quelque chose est actif)
- **☰ Liste / ⊞ Grille** — bascule entre vue grille et vue tableau liste
- **🗞 News** — ouvre la page de flux de news (transporte les filtres compatibles via le hash URL)

**Panneau de filtres (repliable) :**

| Groupe | Options | Comportement |
|---|---|---|
| **Statut** | Tous · Early Access · Sortis · À venir | Sélection unique |
| **Store** | 🎮 Steam · ⚡ Epic | Multi-sélection (OU) — les deux actifs par défaut ; impossible de désactiver le dernier store actif |
| **Bibliothèque** | Tous · Possédés · 🎁 Wishlist · 👁 Suivi | Sélection unique |
| **Type news** | Tous types · 📋 Patch notes · 📰 News | Sélection unique |
| **Temps de jeu** | Tous · Jamais joué · < 1 h · 1–10 h · > 10 h | Sélection unique |
| **Metacritic** | Tous · Sans score · < 50 · 50–75 · > 75 | Sélection unique |
| **Màj récente** | Tous · 2 jours · 5 jours · 15 jours · 30 jours (basé sur la date du dernier patch note) | Sélection unique |

> Les filtres **Store** et **Bibliothèque** sont combinés avec ET : seuls les jeux correspondant à un store actif **et** au statut de collection sélectionné sont affichés.

Tout l'état du filtre et du tri est persisté dans le hash URL, ce qui permet de sauvegarder ou partager une vue filtrée.

**Cartes :**

Chaque carte affiche :
- Image d'en-tête du jeu
- Nom + badge statut (Early Access, Sorti 1.0, À venir)
- Score Metacritic coloré (vert ≥ 75 · orange ≥ 50 · rouge < 50)
- Icônes plateformes (Windows / Mac / Linux)
- Genres
- 📅 Date de sortie · 📰 Date de la dernière news · 🕹 Temps de jeu _(ou 🎁 Wishlist / 👁 Suivi / 🎮 Epic)_
- `#appid` cliquable → page Steam (ou survoler la carte pour voir l'indice du store)

Un clic sur la carte ouvre la fiche Steam dans un nouvel onglet.

### Page news (`steam_news.html`)

- Toutes les news de tous les jeux, triées par date décroissante
- Même barre d'outils à deux niveaux : recherche dans la ligne principale, filtres Statut, Store, Bibliothèque et Type news dans le panneau repliable
- Badge de type sur chaque ligne (vert pour `patchnotes`, gris pour les autres)
- Compteur de résultats en temps réel
- Un clic sur une ligne ouvre la news sur Steam

---

## 9. Stratégie de cache et rafraîchissement

| Scénario | Comportement |
|---|---|
| Nouveau jeu (jamais vu) | App details + news fetchées |
| Jeu en cache, news < `--news-age` heures | Ignoré complètement |
| Jeu en cache, news ≥ `--news-age` heures | News re-fetchées, app details conservées |
| `--refresh` activé | Tout re-fetché, cache ignoré |

**Conseil :** lance `steampulse.exe` quotidiennement sans options supplémentaires pour maintenir les news à jour. Utilise `--refresh` uniquement si les métadonnées d'un jeu ont changé (changement de prix, sortie de Early Access…).

---

## 10. Usage avancé — étapes séparées

Si tu as installé SteamPulse depuis les sources, deux commandes séparées sont disponibles pour exécuter le fetch et le rendu indépendamment :

### `steam-fetch` — uniquement le fetch

```
steam-fetch --key <API_KEY> --steamid <STEAMID64>
```

Mêmes options que `steampulse.exe`, sauf `--output`. Les options Epic (`--epic-auth-code`, etc.) sont également acceptées. Enregistre les données dans la base SQLite sans générer de HTML.

### `steam-render` — uniquement le rendu

```
steam-render --steamid <STEAMID64>
```

| Option | Défaut | Description |
|---|---|---|
| `--db` | `steam_library.db` | Base SQLite source |
| `--steamid` | *(requis)* | SteamID64 (affiché dans l'en-tête) |
| `--output` | `steam_library.html` | Chemin de la page bibliothèque |
| `--lang` | *(système)* | Forcer la langue de l'interface (`en`, `fr`, …) |

Lit uniquement la base SQLite et régénère le HTML à partir des données existantes. Utile pour relancer le rendu après une mise à jour de SteamPulse sans refaire le fetch.

---

## 11. FAQ

**J'ai des jeux Epic qui n'apparaissent pas avec les détails du store — pourquoi ?**  
SteamPulse essaie de faire correspondre chaque jeu Epic à un AppID Steam via la correspondance floue de noms (et IGDB si tu fournis des credentials Twitch). Si aucune correspondance n'est trouvée, le jeu apparaît quand même dans le dashboard avec le badge 🎮 Epic, mais sans détails ni news.

**Mon profil Steam est privé, est-ce que ça marche ?**  
La clé API contourne la restriction de confidentialité pour les requêtes portant sur ton propre compte.

**Les données sont-elles envoyées quelque part ?**  
Non. Tout reste local : base SQLite sur ton disque, pages HTML générées localement. Seules des requêtes en lecture sont faites vers l'API publique Steam.

**Combien de temps prend le premier fetch ?**  
Avec 2000 jeux et 4 workers, comptez ~15–20 minutes (limite de débit ~200 req/5 min sur l'API Store).

**Puis-je relancer `steampulse.exe` sans tout re-fetcher ?**  
Oui. Le cache intelligent évite de re-fetcher les jeux déjà à jour. Seuls les nouveaux jeux et ceux dont les news sont périmées sont rafraîchis.

**Comment interrompre un fetch en cours ?**  
`Ctrl+C` — les tâches en cours sont annulées proprement et les données déjà collectées sont sauvegardées.

---

## 12. Déploiement Docker

SteamPulse publie une image préconstruite à chaque release — aucune compilation locale requise :

```
ghcr.io/davidp57/steampulse:latest
```

Le conteneur démarre une boucle de fetch périodique et sert les dashboards HTML sur le port 80 via nginx :

```
Conteneur
├── nginx           → http://hôte:PORT  →  steam_library.html / steam_news.html
└── boucle scheduler  → steampulse fetch (toutes les INTERVAL_HOURS)

/data  (volume persistant)
├── steam_library.db    ← base SQLite
├── steam_library.html  ← dashboard bibliothèque
└── steam_news.html     ← flux d'actualités
```

### Prérequis

- Docker Engine 20.10+
- Une clé API Steam et ton SteamID64 (voir [section 4](#4-prérequis-steam))
- *(optionnel)* Credentials Epic / Twitch pour le multi-store (voir [section 5](#5-prérequis-epic-games))

### Démarrage rapide — tu utilises déjà `steampulse.exe` sur Windows ?

Si tu utilises SteamPulse sur Windows, l'assistant a créé ton `config.toml` au premier lancement. Il se trouve à :

```
%APPDATA%\steampulse\config.toml
```

Ce fichier contient tous tes credentials (clé Steam, SteamID, tokens Epic, Twitch…). Monte-le dans le conteneur — rien à ressaisir :

```cmd
REM 1. Copie le config à côté de ta commande docker run
copy "%APPDATA%\steampulse\config.toml" config.toml
```

```bash
# 2. Lance le conteneur
docker run -d \
  --name steampulse \
  --restart unless-stopped \
  -p 8080:80 \
  -v steampulse_data:/data \
  -v "$(pwd)/config.toml:/config/config.toml:ro" \
  ghcr.io/davidp57/steampulse:latest
```

Puis ouvre `http://localhost:8080` (ou `http://<ip-serveur>:8080`) dans ton navigateur. Les dashboards sont régénérés toutes les 4 heures par défaut.

> **Sur Windows PowerShell**, remplace `$(pwd)` par `${PWD}` :
> ```powershell
> docker run -d --name steampulse --restart unless-stopped -p 8080:80 `
>   -v steampulse_data:/data `
>   -v "${PWD}/config.toml:/config/config.toml:ro" `
>   ghcr.io/davidp57/steampulse:latest
> ```

Si tu n'as pas encore lancé `steampulse.exe`, fais-le une fois — l'assistant démarre automatiquement, sauvegarde le config et quitte. Ton `config.toml` est ensuite prêt à être monté.

### Sans fichier config — Steam uniquement (variables d'environnement)

Si tu n'utilises que Steam et que tu n'as pas de `config.toml`, tu peux passer tes credentials directement en variables d'environnement. Le conteneur génère un `config.toml` au démarrage.

```bash
docker run -d \
  --name steampulse \
  --restart unless-stopped \
  -p 8080:80 \
  -v steampulse_data:/data \
  -e STEAM_API_KEY=ta_cle_32_chars \
  -e STEAM_ID=76561198xxxxxxxxx \
  -e INTERVAL_HOURS=4 \
  ghcr.io/davidp57/steampulse:latest
```

Consulte le [tableau des variables d'environnement](#variables-denvironnement) ci-dessous pour toutes les options disponibles.

> **Les credentials Epic / Twitch ne peuvent pas être passés en variables d'environnement** pour la configuration initiale OAuth2 — l'assistant a besoin d'un navigateur. Lance `steampulse.exe` une fois sur ta machine pour terminer le login Epic, puis monte le `config.toml` résultant comme indiqué dans le démarrage rapide. Une fois le refresh token dans le `config.toml`, la ré-authentification Epic est entièrement automatique.

### `docker-compose.yml` — pour les déploiements permanents / NAS

`docker compose` est pratique pour les NAS, les redémarrages automatiques et pour garder tous les paramètres dans un fichier.

```yaml
services:
  steampulse:
    image: ghcr.io/davidp57/steampulse:latest
    restart: unless-stopped
    ports:
      - "8080:80"
    volumes:
      - steampulse_data:/data
      - ./config.toml:/config/config.toml:ro   # monte ton config ici
    environment:
      - INTERVAL_HOURS=4
      - SP_LANG=fr

volumes:
  steampulse_data:
```

Démarre avec :

```bash
docker compose up -d
```

Si tu préfères passer les variables d'environnement au lieu d'un fichier config (Steam uniquement), remplace la ligne du volume `config.toml` par `env_file: .env` et remplis un fichier `.env` basé sur `.env.example`.

### Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `STEAM_API_KEY` | *(requis — option A)* | Ta clé API Steam (32 caractères hexadécimaux) |
| `STEAM_ID` | *(requis — option A)* | Ton SteamID64 |
| `EPIC_AUTH_CODE` | *(option A uniquement)* | Code d'autorisation Epic à usage unique (premier login) |
| `EPIC_REFRESH_TOKEN` | *(option A uniquement)* | Refresh token Epic (auth persistante) |
| `TWITCH_CLIENT_ID` | *(option A uniquement)* | Client ID Twitch/IGDB |
| `TWITCH_CLIENT_SECRET` | *(option A uniquement)* | Client secret Twitch/IGDB |
| `INTERVAL_HOURS` | `4` | Fréquence de la boucle de fetch (en heures) |
| `REFRESH` | `false` | Mettre à `true` pour forcer un re-fetch complet à chaque run |
| `SP_LANG` | *(système)* | Forcer la langue du dashboard (`en`, `fr`) |
| `WORKERS` | `4` | Nombre de workers HTTP parallèles |
| `NEWS_AGE` | `24` | Âge maximum des news (heures) avant re-fetch |

Toutes les variables de credentials sont ignorées quand un fichier config est monté dans `/config/config.toml`.

### Volume de données

Toutes les données persistantes se trouvent dans le volume nommé `steampulse_data` (monté sur `/data`). La base de données survit aux mises à jour du conteneur.

Pour tout effacer et repartir de zéro :

```bash
docker compose down -v   # ⚠ supprime toutes les données y compris la base
docker compose up -d
```

### Commandes utiles

```bash
# Afficher les logs (scheduler + nginx)
docker compose logs -f

# Forcer un fetch immédiat en dehors du planning
docker compose exec steampulse \
  steampulse --config /run/steampulse/config.toml \
             --db /data/steam_library.db \
             --output /data/steam_library.html \
             --refresh

# Ouvrir un shell dans le conteneur
docker compose exec steampulse bash

# Mettre à jour vers la dernière image
docker compose pull
docker compose up -d
```

### Déploiement sur NAS ou serveur permanent

N'importe quel hôte avec Docker fonctionne. Les exemples ci-dessous utilisent un NAS Synology, mais la démarche est identique sur tout autre serveur.

**Synology — Container Manager (DSM 7.2+) :**

1. Ouvre **Container Manager** → **Projets** → **Créer**
2. Donne un nom au projet (ex. `steampulse`) et choisis un dossier sur le NAS (ex. `/volume1/docker/steampulse`)
3. Importe ou colle le contenu de `docker-compose.yml` dans l'éditeur
4. Crée un fichier `.env` dans le même dossier avec tes credentials
5. Clique sur **Construire** — l'image est tirée de GHCR automatiquement
6. Une fois démarré, ouvre `http://<IP-du-NAS>:8080` dans un navigateur

**Synology — Portainer :**

1. Va dans **Stacks** → **Add stack**
2. Colle le contenu de `docker-compose.yml`
3. Dans **Environment variables**, ajoute `STEAM_API_KEY`, `STEAM_ID` et les variables optionnelles
4. Clique sur **Deploy the stack**

Le conteneur redémarre automatiquement après un reboot du NAS grâce à `restart: unless-stopped`.
