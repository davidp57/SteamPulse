# SteamPulse — Guide utilisateur

🌐 [English version](../en/user-guide.md)

## Sommaire

1. [Installation](#1-installation)
2. [Obtenir les prérequis Steam](#2-obtenir-les-prérequis-steam)
3. [Prérequis Epic Games](#3-prérequis-epic-games)
4. [Tout-en-un — `steampulse.exe`](#4-tout-en-un--steampulseexe)
5. [Options complètes](#5-options-complètes)
6. [Naviguer dans l'interface](#6-naviguer-dans-linterface)
7. [Stratégie de cache et rafraîchissement](#7-stratégie-de-cache-et-rafraîchissement)
8. [Usage avancé — étapes séparées](#8-usage-avancé--étapes-séparées)
9. [FAQ](#9-faq)

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

## 3. Prérequis Epic Games

L'intégration Epic est **optionnelle**. Passe cette section si tu utilises uniquement Steam.

SteamPulse peut importer ta bibliothèque Epic Games et tenter de résoudre chaque jeu vers un AppID Steam (pour récupérer les détails du store et les news). Les jeux non résolus apparaissent quand même dans le dashboard, tagués Epic, sans enrichissement Steam.

### Authentification — premier lancement (code d'autorisation)

1. Ouvre un navigateur et va sur :  
   `https://www.epicgames.com/id/login?redirectUrl=https%3A%2F%2Fwww.epicgames.com%2Fid%2Fapi%2Fredirect%3FclientId%3D34a02cf8f4414e29b15921876da36f9%26responseType%3Dcode`
2. Connecte-toi avec ton compte Epic.
3. Tu seras redirigé vers une page JSON — copie la valeur de `authorizationCode`.
4. Passe-la avec `--epic-auth-code <CODE>`. C'est un code **à usage unique**.

### Authentification — lancements suivants (credentials device)

Pour les lancements headless ou automatisés, utilise les credentials device (obtenus lors de la première auth par l'API Epic) :

```
steampulse.exe --key <API_KEY> --steamid <STEAMID64> \
  --epic-device-id <DEVICE_ID> \
  --epic-account-id <ACCOUNT_ID> \
  --epic-device-secret <SECRET>
```

### Optionnel — résolveur IGDB

Pour une meilleure résolution des AppIDs Steam, fournis des credentials Twitch (utilisés pour interroger IGDB) :

1. Crée une app sur <https://dev.twitch.tv/console/apps>
2. Passe `--twitch-client-id` et `--twitch-client-secret`

Sans IGDB, SteamPulse utilise la correspondance floue via l'API de recherche Steam Store.

---

## 4. Tout-en-un — `steampulse.exe`

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

## 5. Options complètes

| Option | Défaut | Description |
|---|---|---|
| `--key` | *(requis)* | Clé Steam Web API |
| `--steamid` | *(requis)* | SteamID64 du profil |
| `--db` | `steam_library.db` | Chemin vers la base SQLite |
| `--output` | `steam_library.html` | Chemin de la page bibliothèque générée |
| `--workers` | `4` | Nombre de threads parallèles |
| `--max N` | *(aucun)* | Limiter le fetch à N jeux (tests) |
| `--refresh` | désactivé | Ignorer le cache, tout re-fetcher |
| `--news-age HOURS` | `24` | Rafraîchir les news des jeux dont le cache dépasse N heures |
| `--no-wishlist` | désactivé | Ne pas récupérer la wishlist |
| `--followed` | désactivé | Récupérer les jeux suivis (opt-in, voir note) |
| `--lang` | *(système)* | Forcer la langue de l'interface (`en`, `fr`, …). Par défaut la locale système, repli sur `en`. |
| `-v` / `--verbose` | désactivé | Afficher les logs DEBUG |

**Options Epic Games :**

| Option | Défaut | Description |
|---|---|---|
| `--epic-auth-code` | *(aucun)* | Code d'autorisation Epic à usage unique (premier login) |
| `--epic-device-id` | *(aucun)* | Device ID Epic (auth persistante) |
| `--epic-account-id` | *(aucun)* | Account ID Epic (auth persistante) |
| `--epic-device-secret` | *(aucun)* | Device secret Epic (auth persistante) |
| `--twitch-client-id` | *(aucun)* | Client ID Twitch/IGDB (meilleure résolution AppID) |
| `--twitch-client-secret` | *(aucun)* | Client secret Twitch/IGDB |

> **Note `--followed`** : l'API Steam Web ne retourne plus les jeux suivis avec une clé standard. Cette option est disponible mais retournera généralement une liste vide.

---

## 6. Naviguer dans l'interface

### Page bibliothèque (`steam_library.html`)

**Barre d'outils — ligne principale (toujours visible) :**
- **Recherche** — filtre les jeux par nom en temps réel (`/` ou `Ctrl+K`)
- **Tri** — par nom, score Metacritic, temps de jeu, date de sortie, dernière mise à jour, date dernière news
- **⚙ Filtres** — affiche / masque le panneau de filtres ; un badge indique le nombre de filtres actifs
- **Reset** — réinitialise tous les filtres et la recherche (apparaît uniquement si quelque chose est actif)
- **☰ Liste / ⊞ Grille** — bascule entre vue grille et vue tableau liste
- **🗞 News** — ouvre la page de flux de news (transporte les filtres compatibles via le hash URL)

**Panneau de filtres (repliable) :**

| Groupe | Options |
|---|---|
| **Statut** | Tous · Early Access · Sortis · À venir |
| **Source** | 🎮 Tout · Possédés · 🎁 Wishlist · 👁 Suivi · 🎮 Epic |
| **Type news** | Tous types · 📋 Patch notes · 📰 News |
| **Temps de jeu** | Tous · Jamais joué · < 1 h · 1–10 h · > 10 h |
| **Metacritic** | Tous · Sans score · < 50 · 50–75 · > 75 |
| **Màj récente** | Tous · 2 jours · 5 jours · 15 jours · 30 jours (basé sur la date du dernier patch note) |

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
- Même barre d'outils à deux niveaux : recherche + tri dans la ligne principale, filtres Statut et Type news dans le panneau repliable
- Badge de type sur chaque ligne (vert pour `patchnotes`, gris pour les autres)
- Compteur de résultats en temps réel
- Un clic sur une ligne ouvre la news sur Steam

---

## 7. Stratégie de cache et rafraîchissement

| Scénario | Comportement |
|---|---|
| Nouveau jeu (jamais vu) | App details + news fetchées |
| Jeu en cache, news < `--news-age` heures | Ignoré complètement |
| Jeu en cache, news ≥ `--news-age` heures | News re-fetchées, app details conservées |
| `--refresh` activé | Tout re-fetché, cache ignoré |

**Conseil :** lance `steampulse.exe` quotidiennement sans options supplémentaires pour maintenir les news à jour. Utilise `--refresh` uniquement si les métadonnées d'un jeu ont changé (changement de prix, sortie de Early Access…).

---

## 8. Usage avancé — étapes séparées

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

## 9. FAQ

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
