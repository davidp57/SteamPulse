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

Sans IGDB, SteamPulse utilise une correspondance multi-stratégie via l'API de recherche Steam Store (similarité floue, préfixe mot-à-mot, contenance, suppression de suffixe d'édition, normalisation d'année).

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
   42 alertes → C:\...\steam_alerts.html
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
- **🔔 Alertes** — ouvre le tableau de bord d’alertes ; reporte les filtres compatibles (store, bibliothèque) via le hash URL

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

> Survol d'un bouton de filtre pour afficher une infobulle expliquant ce qu'il filtre.

> Les filtres **Store** et **Bibliothèque** sont combinés avec ET : seuls les jeux correspondant à un store actif **et** au statut de collection sélectionné sont affichés.

> Sur mobile (petit écran), le panneau de filtres s'ouvre en plein écran avec un bouton de fermeture en haut.

> **Optimisations mobile :** La barre d'outils se masque automatiquement lors du défilement vers le bas pour maximiser la visibilité du contenu, et réapparaît instantanément en défilant vers le haut. L'en-tête est compact (logo masqué, statistiques réduites) et tous les contrôles sont réduits pour une utilisation tactile.

Tout l'état du filtre et du tri est persisté dans le hash URL, ce qui permet de sauvegarder ou partager une vue filtrée.

**Cartes :**

Chaque carte affiche :
- Image d'en-tête du jeu (ratio natif 460×215 — jamais étirée ni écrasée ; peut être légèrement rognée si l'image source a un ratio différent)
- Nom + badge statut (Early Access, Sorti 1.0, À venir)
- Score Metacritic coloré (vert ≥ 75 · orange ≥ 50 · rouge < 50) — survol pour voir le score/100 et le label de qualité en infobulle
- Icônes plateformes (Windows / Mac / Linux)
- Développeur · Genres
- 📅 Date de sortie · 📰 Date de la dernière news · 🕹 Temps de jeu _(ou 🎁 Wishlist / 👁 Suivi / 🎮 Epic)_

Un clic sur la carte ouvre la fiche Steam dans un nouvel onglet.

Si un jeu a des news, une barre **▼ N mises à jour** apparaît en bas de la carte. Un clic dessus déploie la liste des news en **overlay flottant** au-dessus des tuiles inférieures — le reste de la grille s'assombrit et se floute pour focaliser l'attention. Une seule carte peut être ouverte à la fois ; cliquer ailleurs pour fermer.

### Page alertes (`steam_alerts.html`)

**Barre d’outils — ligne principale (toujours visible) :**
- **Recherche** — filtre les alertes par nom de jeu en temps réel, avec dropdown d’autocomplétion (suggestions filtrées aux jeux visibles uniquement) et bouton × pour effacer
- **Tri** — par date (récentes/anciennes), nom (A–Z / Z–A), temps de jeu, score Metacritic
- **Mode d'affichage** — quatre vues commutables :
  - **Combiné** — toutes les cartes dans une liste unique
  - **Par règle** — cartes groupées sous des en-têtes de section repliables (un par règle d’alerte)
  - **Par jeu** — cartes groupées par nom de jeu (vignette du jeu dans l’en-tête de section)
  - **Règle / Jeu** — double regroupement : d’abord par règle, puis par jeu dans chaque règle, les deux niveaux étant repliables
- **Contrôles de groupes** (visibles uniquement en vue groupée) :
  - **Recherche de groupe** — filtre les en-têtes de section par nom en temps réel (avec bouton × pour effacer)
  - **Tout ouvrir / Tout fermer** — bouton pour ouvrir ou fermer toutes les sections d’un coup
- **⚙ Filtres** — affiche / masque le panneau de filtres ; un badge indique le nombre de filtres actifs
- **Reset** — réinitialise tous les filtres, la recherche et le tri
- **Tout marquer comme lu** — marque toutes les alertes visibles comme lues
- **Taille du texte** — boutons A− / A+ pour réduire/agrandir la taille de police (persistant entre les sessions)

**Panneau de filtres (repliable) :**

| Groupe | Options | Comportement |
|---|---|---|
| **Statut** | Tous · Early Access · Sortis · À venir | Sélection unique |
| **Store** | 🎮 Steam · ⚡ Epic | Multi-sélection (OU) — les deux actifs par défaut |
| **Bibliothèque** | Tous · Possédés · 🎁 Wishlist · 👁 Suivi | Sélection unique |
| **Type news** | Tous types · 📋 Patch notes · 📰 News | Sélection unique |
| **Temps de jeu** | Tous · Jamais joué · < 1 h · 1–10 h · > 10 h | Sélection unique |
| **Metacritic** | Tous · Sans score · < 50 · 50–75 · > 75 | Sélection unique |
| **Màj récente** | Tous · 2 jours · 5 jours · 15 jours · 30 jours | Sélection unique |

> Le panneau de filtres est partagé entre la bibliothèque et la page alertes. Les filtres **Store** et **Bibliothèque** sélectionnés sur une page sont reportés automatiquement lors de la navigation vers l’autre.

**Sections accordéon (vues groupées) :**

Dans les vues « Par règle » et « Par jeu », les alertes sont regroupées sous des sections repliables :
- Clique sur un en-tête de section (ou son chevron ❯) pour le déplier ou le replier
- Toutes les sections sont repliées par défaut
- Utilise le bouton **Tout ouvrir / Tout fermer** pour basculer toutes les sections d’un coup
- Le champ **recherche de groupe** filtre les sections par nom d’en-tête — les sections non correspondantes sont masquées

**Cartes d’alerte :**

Chaque carte affiche :
- Icône de règle + nom de la règle
- Image d’en-tête du jeu (120×56, cliquable → ouvre la fiche Steam ; masquée dans les vues groupées par jeu)
- Nom du jeu (cliquable → ouvre la fiche Steam ; masqué dans les vues groupées par jeu)
- Date de l’alerte
- Extrait de news (titre + détails) — un clic sur le titre ou les détails ouvre l’URL de la news
- Badge Build ID quand pertinent (ex. `build 12345` pour la détection de mises à jour silencieuses)
- Bouton ✓ — seule manière de marquer la carte comme lue

**Zones de clic :**
- **Image du jeu ou nom du jeu** → ouvre la fiche Steam dans un nouvel onglet
- **Titre ou texte de la news** → ouvre l’article de la news
- **Bouton ✓** → marque l’alerte comme lue

**Suivi lu/non lu :**
- L’état est stocké localement dans `localStorage` — aucun serveur nécessaire
- Clique sur le bouton ✓ pour marquer une carte individuellement
- Utilise « Tout marquer comme lu » pour tout marquer d’un coup

Les règles d’alerte sont configurées dans `config.toml` sous les sections `[[alerts]]`. Lance `steam-setup` pour voir et éditer les règles par défaut.
### Page diagnostic (`steam_diagnostic.html`)

Page technique générée en même temps que la bibliothèque et les alertes. Elle fournit :

- **Résumé de la base de données** — nombre total de jeux, enrichis/non enrichis, alertes et news
- **Répartition par source** — nombre de jeux par source (Steam, Epic)
- **Table des mappings AppID** — toutes les résolutions externe→Steam AppID avec statut (résolu, non résolu, manuel) ; champ de recherche inclus ; les cartes de statistiques sont cliquables pour filtrer la table par statut
- **Statistiques de découverte Epic** — éléments API totaux, acceptés, résolus, non résolus et ignorés (affiché uniquement quand la source Epic a été utilisée lors du fetch)
- **Table des éléments ignorés** — éléments filtrés pendant la découverte Epic, avec la raison (pas de titre, ID hexadécimal, label sandbox, doublon)

Cette page est utile pour diagnostiquer les problèmes de qualité de données, vérifier quels jeux Epic ont été résolus vers des AppID Steam, et identifier les éléments filtrés.
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

> **En bref** — Copie ton `config.toml`, télécharge `docker-compose.yml` depuis
> la page de release, place-les dans le même dossier, lance
> `docker compose up -d`, ouvre `http://<hôte>:8080`.

SteamPulse publie une image Docker prête à l'emploi à chaque release :

```
ghcr.io/davidp57/steampulse:latest
```

Le conteneur récupère les données de ta bibliothèque selon un planning et sert
les dashboards sur le port 80 via nginx. Aucune compilation requise.

---

### Étape 1 — Récupère ton `config.toml`

Le fichier `config.toml` est la seule chose dont le conteneur a besoin. Il
contient tous tes credentials (clé API Steam, SteamID, tokens Epic, Twitch…).

**Tu utilises déjà `steampulse.exe` sur Windows ?**
L'assistant l'a créé automatiquement au premier lancement. Il se trouve ici :

```
%APPDATA%\steampulse\config.toml
```

Copie-le dans le dossier où tu vas lancer Docker (ton NAS, un serveur, ou ta
machine locale). C'est tout — passe à l'étape 2.

**Tu n'as jamais lancé `steampulse.exe` ?**
Lance-le une fois — l'assistant démarre automatiquement, enregistre le fichier
et quitte. Ton `config.toml` est ensuite prêt.

> **Epic Games / Twitch :** le flux de connexion OAuth2 nécessite un vrai
> navigateur et ne peut pas se dérouler dans un conteneur. Tu dois compléter
> l'assistant au moins une fois sur une machine locale. Ensuite, le refresh
> token stocké dans `config.toml` gère la ré-authentification automatiquement —
> aucune intervention supplémentaire nécessaire.

---

### Étape 2 — Télécharge `docker-compose.yml` et lance le conteneur

Le `docker-compose.yml` de SteamPulse est inclus dans chaque release GitHub.
Télécharge le fichier pour ta version :

```
https://github.com/davidp57/SteamPulse/releases/latest/download/docker-compose.yml
```

Place-le dans le même dossier que ton `config.toml` :

```
ton-dossier/
├── docker-compose.yml   ← téléchargé depuis la release
├── config.toml          ← copié depuis %APPDATA%\steampulse\
└── data/                ← créé automatiquement par Docker
    ├── steam_library.db
    ├── steam_library.html
    └── steam_alerts.html
```

Crée le dossier de données puis lance le conteneur :

```bash
mkdir data
docker compose up -d
```

Docker télécharge l'image automatiquement au premier lancement.

---

### Étape 3 — Ouvre tes dashboards

Va sur `http://localhost:8080` (ou `http://<ip-serveur>:8080` depuis un autre
appareil).

Le conteneur régénère les dashboards toutes les `INTERVAL_HOURS` heures. Ta
base SQLite et les pages HTML sont dans le dossier `./data/` à côté de
`docker-compose.yml` — directement accessibles depuis le NAS. Ce dossier
survit aux redémarrages et mises à jour du conteneur.

---

### Gérer ton conteneur

```bash
# Afficher les logs
docker compose logs -f

# Forcer un fetch immédiat maintenant (en dehors du planning)
docker compose exec steampulse steampulse \
  --config /run/steampulse/config.toml \
  --db /data/steam_library.db \
  --output /data/steam_library.html \
  --refresh

# Mettre à jour vers la dernière image
docker compose pull && docker compose up -d

# Tout effacer et repartir de zéro  ⚠ supprime la base
rm -rf ./data && docker compose up -d
```

---

### Déploiement sur NAS (Synology, QNAP…)

Les étapes sont identiques à celles ci-dessus — le NAS joue simplement le rôle
d'hôte Docker.

**Synology — Container Manager (DSM 7.2+) :**

1. Utilise **File Station** pour créer un dossier (ex.
   `/volume1/docker/steampulse`)
2. Dépose `docker-compose.yml` et `config.toml` dans ce dossier
3. Dans ce dossier, crée un sous-dossier `data` (via File Station)
4. Ouvre **Container Manager** → **Projets** → **Créer**
5. Sélectionne le dossier créé — il détecte `docker-compose.yml` automatiquement
6. Clique sur **Construire** — l'image est téléchargée depuis GHCR, aucune
   compilation locale
7. Ouvre `http://<IP-du-NAS>:8080`

**Portainer :**

> **Limitation connue :** quand tu colles un fichier Compose dans l’éditeur de
> stack Portainer, les chemins relatifs comme `./config.toml` sont résolus par
> rapport au répertoire interne de Portainer (ex. `/data/compose/3/`), **pas**
> ton dossier. Cela génère une erreur `Bind mount failed`.

L’approche recommandée est de **ne pas** utiliser l’éditeur de paste de
Portainer pour SteamPulse. À la place, connecte-toi en SSH sur l’hôte Docker,
place les fichiers, et lance Compose directement :

```bash
mkdir -p /opt/steampulse/data
# copie config.toml dans /opt/steampulse/config.toml via scp ou File Station
cd /opt/steampulse
curl -LO https://github.com/davidp57/SteamPulse/releases/latest/download/docker-compose.yml
docker compose up -d
```

Si tu veux quand même passer par l’UI Portainer, utilise des **chemins absolus**
dans le fichier compose. Modifie la section `volumes:` avant de coller :

```yaml
volumes:
  - /opt/steampulse/data:/data
  - /opt/steampulse/config.toml:/config/config.toml:ro
```

Assure-toi que `/opt/steampulse/config.toml` existe sur l’hôte **avant** de
cliquer sur **Deploy the stack**, sinon le bind mount échouera.

Le conteneur redémarre automatiquement après un reboot grâce à
`restart: unless-stopped`.

---

### Mettre à jour l'image

Une nouvelle image est publiée à chaque release. Tes données dans `./data/`
ne sont jamais touchées par une mise à jour.

**Tags d'image :**

| Tag | Source | Usage |
|---|---|---|
| `latest` | branche `main` / releases | **Production — utilise ce tag** |
| `develop` | branche `develop` | Tests pré-release uniquement |
| `v1.2.3` | Tag de version | Fixer une version précise |

**Terminal / SSH (n'importe quel hôte) :**

```bash
cd /chemin/vers/ton-dossier
docker compose pull
docker compose up -d
```

**Synology — Container Manager :**

1. Ouvre **Container Manager** → **Projets**
2. Sélectionne le projet `steampulse`
3. Clique sur **Action** → **Construire** — Container Manager télécharge la
   nouvelle image et recrée le conteneur automatiquement

> **Note :** certaines versions de DSM redémarrent uniquement le conteneur sans
> re-télécharger l'image. Si les commandes ci-dessous affichent une ancienne
> date, ouvre une session SSH sur le NAS et exécute
> `docker compose pull && docker compose up -d` depuis le dossier du projet.

**Portainer :**

1. Va dans **Stacks** → sélectionne `steampulse`
2. Clique sur **Editor**
3. Clique sur **Update the stack**
4. Coche **Re-pull image and redeploy**

**Vérifier que la nouvelle image tourne bien :**

```bash
# Date de construction de l'image locale (comparer avec la date de la release)
docker image inspect ghcr.io/davidp57/steampulse:latest --format='{{.Created}}'

# Lister les images locales avec leur date
docker images ghcr.io/davidp57/steampulse
```

Si la date affichée est antérieure à la release, l'ancienne image est toujours
en cache. Lance `docker compose pull && docker compose up -d` pour forcer la
mise à jour.

**Tester le build `develop` avant une release :**

Le tag `develop` n'est pas un alias de `latest` — c'est une image distincte.
Pour la tester sur ton NAS, pull et retague-la localement :

```bash
docker pull ghcr.io/davidp57/steampulse:develop
docker tag ghcr.io/davidp57/steampulse:develop ghcr.io/davidp57/steampulse:latest
docker compose up -d
```

Reviens à l'image officielle à tout moment avec `docker compose pull && docker compose up -d`.
