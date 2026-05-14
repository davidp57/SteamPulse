# Backlog — SteamPulse

Single source of truth for all tracked work items.
When work starts on a topic, create a `feature/` or `fix/` branch from `develop`.
When a ticket is completed, update the status and move it to "Lots terminés".

---

## Calibration estimations

Facteur de marge actuel : **1,15** (15 %) — valeur initiale, à ajuster après les premiers lots mesurés.

| Lot | Estimé Copilot | Réel Copilot | Ratio | Estimé gestion | Réel gestion | Ajustement |
| --- | --- | --- | --- | --- | --- | --- |
| *(aucun lot mesuré pour l'instant)* | | | | | | |

---

## Lots actifs

Aucun lot actif en cours de livraison.

---

## Hors lots

| ID | Titre | Prio | Est. | Créé | Démarré | Terminé |
| --- | --- | --- | --- | --- | --- | --- |
| BIZ-001 | CLI : gestion des mappings AppID manuels | P2 | ~35 min | 2026-05-14 | | |
| BIZ-002 | Source : Amazon Prime Gaming | P3 | ~2h | 2026-05-14 | | |
| BIZ-003 | Collections de jeux | P2 | ~3h | 2026-05-14 | | |
| BIZ-004 | Historique de prix (séries temporelles) | P3 | ~2h | 2026-05-14 | | |
| BIZ-005 | Export CSV / JSON | P3 | ~1h | 2026-05-14 | | |
| BIZ-006 | Timeline de news par jeu | P3 | ~1h30 | 2026-05-14 | | |
| BIZ-007 | Intégration Playnite : bouton "Ouvrir dans Playnite" + import bibliothèque | P2 | ~140 min | 2026-05-14 | ✅ terminé | 2026-05-14 |

---

## Détails

### BIZ-001 — CLI : gestion des mappings AppID manuels

Interface pour ajouter ou modifier des entrées manuelles dans la table `appid_mappings` (e.g. `steam-fetch --add-mapping epic:Flier 1234567`). Les entrées `manual=True` sont déjà protégées dans la DB — il manque uniquement la surface CLI. Priorité P2 : utile pour les jeux Epic exclusifs sans page Steam qui échouent à la résolution automatique.

### BIZ-002 — Source : Amazon Prime Gaming

Plugin `sources/amazon.py` implémentant le protocole `GameSource` pour découvrir la bibliothèque Amazon Prime Gaming. Aucune API publique identifiée à ce stade — nécessite une phase d'investigation. L'architecture plugin est déjà en place ; ajouter un store = nouveau fichier `sources/<store>.py`.

### BIZ-003 — Collections de jeux

Groupes définis par l'utilisateur pour organiser ses jeux (ex. "À finir", "Co-op avec amis", "Abandonné"). Tables `collections` et `collection_games` (migration additive). Surface CLI : `steam-fetch --add-to <collection> <appid|name>`, `--remove-from`, `--list-collections`. Dashboard HTML : groupe de filtre Collection aux côtés de Store / Status ; un jeu peut appartenir à plusieurs collections (multi-select, logique OR). Collections exportées dans le HTML généré (pas de serveur requis).

### BIZ-004 — Historique de prix (séries temporelles)

Stocker les prix comme série temporelle dans une nouvelle table `price_history`. Permettre l'affichage d'un graphique d'évolution du prix sur les cartes ou dans une vue dédiée. Utile pour détecter les baisses de prix récurrentes.

### BIZ-005 — Export CSV / JSON

Commande `steam-render --export-csv` ou `--export-json` pour exporter la bibliothèque entière (avec filtres optionnels) vers un fichier plat. Utile pour l'intégration avec d'autres outils.

### BIZ-006 — Timeline de news par jeu

Vue dédiée (ou panneau expansible sur la carte) affichant l'historique complet des mises à jour d'un jeu : liste chronologique des patch notes et news, chaque entrée avec date, titre, tag de type (patch note / news), et lien direct vers l'article. Utile pour évaluer rapidement l'activité de maintenance d'un jeu.

### BIZ-007 — Intégration Playnite : bouton "Ouvrir dans Playnite" + import bibliothèque

Ajouter sur chaque carte de la bibliothèque un bouton optionnel pour ouvrir le jeu directement dans Playnite via son protocole URI. Mode basique sans configuration (search URI) ; mode enrichi optionnel via upload de la bibliothèque Playnite (showgame URI avec UUID précis).

**Contexte de déploiement :**
SteamPulse tourne dans un container Docker sur un NAS. Playnite est installé sur un PC de jeu. Les liens `playnite://` sont des **protocoles custom gérés côté navigateur** : quand le navigateur du PC de jeu clique sur `playnite://playnite/...`, c'est l'OS du PC qui intercepte et lance Playnite — le serveur NAS n'intervient pas. Les URIs fonctionnent donc correctement depuis un HTML servi par le NAS, à condition que le navigateur soit sur le PC.

---

#### Mode basique (toujours disponible)

**Activation :**
- Config TOML : `[playnite] enabled = true`.
- CLI : `--playnite` flag.
- Sans activation, aucun bouton n'est rendu.

**URI utilisée :** `playnite://playnite/search/<nom encodé>` — ouvre Playnite et lance une recherche. Fallback universel, fonctionne sans aucune configuration côté serveur.

**HTML / JS :**
- `href` généré dynamiquement en JS depuis `data-name` sur la carte : `playnite://playnite/search/` + `encodeURIComponent(name)`.
- Si un UUID est disponible dans les données injectées (voir mode enrichi), JS préfère `playnite://playnite/showgame/<uuid>` à la place.
- Bouton conditionné à un flag `__PLAYNITE_ENABLED__` dans le template.

---

#### Mode enrichi (optionnel) — import de la bibliothèque Playnite

Permet de résoudre les AppIDs → UUIDs Playnite pour ouvrir la fiche précise du jeu (`showgame`) au lieu d'une recherche approximative.

**Workflow utilisateur :**
1. Dans Playnite : `Tools > Export Library` → exporte un fichier JSON (tableau de jeux).
2. Sur la page `/config` de SteamPulse : section *Playnite — Import de bibliothèque* avec :
   - Un `<input type="file" accept=".json">` pour sélectionner le fichier.
   - Un hint textuel sous le champ : `Emplacement par défaut : %APPDATA%\Playnite\library\` (note: les navigateurs ne peuvent pas pré-remplir le chemin pour des raisons de sécurité).
   - Un bouton **Importer**.
3. Le navigateur upload le fichier vers `POST /api/playnite/import` (sidecar server).
4. Le serveur parse le JSON, extrait les mappings, les persiste en DB.
5. Un re-render automatique (ou bouton dédié) met à jour le dashboard.

**Format JSON Playnite (export) :**
```json
[
  {
    "Id": "550e8400-e29b-41d4-a716-446655440000",
    "Name": "Portal 2",
    "GameId": "620",
    "PluginId": "cb91dfc9-b977-43bf-8e70-55f46e410fab"
  }
]
```
- `PluginId` Steam : `cb91dfc9-b977-43bf-8e70-55f46e410fab` — seuls ces jeux sont mappés (les autres sont ignorés ou mappés par nom).
- `GameId` pour Steam = AppID (chaîne).

**DB — nouvelle table `playnite_mappings` :**
```sql
CREATE TABLE IF NOT EXISTS playnite_mappings (
    game_key   TEXT PRIMARY KEY,  -- steam AppID ou "epic:<catalogItemId>"
    playnite_uuid TEXT NOT NULL,
    name       TEXT,
    updated_at INTEGER NOT NULL
);
```
- Ajoutée via le mécanisme `_MIGRATIONS` existant.
- L'import écrase les entrées existantes (upsert).

**Endpoint `POST /api/playnite/import` (server.py) :**
- Accepte `multipart/form-data` avec un champ `file`.
- Parse le JSON, valide la structure minimale (`Id`, `GameId`, `PluginId`).
- Filtre sur `PluginId` Steam, insère dans `playnite_mappings`.
- Retourne `{"imported": N, "skipped": M}` en JSON.
- Taille max du fichier : 10 MB (garde-fou).

**Renderer :**
- Charge les mappings depuis la DB → dict `{appid: uuid, ...}`.
- Injecte en JSON dans le template HTML (comme `__PLAYNITE_MAPPINGS_JSON__`).
- JS utilise l'UUID si disponible dans ce dict, sinon repli sur le nom.

---

**i18n :**
- `btn_open_playnite` (EN: "Open in Playnite" / FR: "Ouvrir dans Playnite")
- `tt_playnite` (EN: "Show in Playnite" / FR: "Afficher dans Playnite")
- `lbl_playnite_import` (EN: "Import Playnite Library" / FR: "Importer la bibliothèque Playnite")
- `lbl_playnite_hint` (EN: "Default location: %APPDATA%\\Playnite\\library\\" / FR: "Emplacement par défaut : %APPDATA%\\Playnite\\library\\")
- `lbl_playnite_imported` (EN: "{n} games imported" / FR: "{n} jeux importés")

**Tests :**
- `test_renderer.py` : flag activé → bouton présent ; flag désactivé → absent ; mappings injectés → UUID utilisé dans le href.
- `test_server.py` : `POST /api/playnite/import` avec JSON valide → 200 + count ; JSON malformé → 400 ; fichier trop gros → 413.
- `test_db.py` : upsert dans `playnite_mappings` fonctionne.

**Ce qui n'est PAS dans le scope :**
- Support des autres plugins Playnite (GOG, Xbox…) — extension future.
- Synchronisation automatique / polling.
- Upload de fichiers JSON individuels du dossier `games/` (export via `Tools > Export Library` suffit).

**Estimation :**
- Mode basique : config flag + renderer + JS + i18n de base + tests = ~55 min
- Mode enrichi : endpoint upload + DB table + parsing + renderer mappings + UI /config + i18n + tests = ~75 min
- Total brut : ~130 min × 1,15 ≈ **~150 min** (table arrondie à **~140 min** — certaines parties se chevauchent)

---

## Lots terminés

| Lot | Nom | Version | Tickets | Terminé |
| --- | --- | --- | --- | --- |
| v2.1.1 | Playnite integration | v2.1.1 | BIZ-007 | 2026-05-14 |
| v2.1 | New stores + web configuration | v2.1.0 | GOG, Game Pass, /config, multiselect, fetch bandeau | 2026-04-07 |
| v2.0 | Sidecar server + self-hosted mode | v2.0.0 | steam-serve, auth, SSE refetch, /api/rerender | 2026-04-04 |
| v1.6 | Epic data quality + diagnostic page | v1.6.x | Cleanup rules, diagnostic HTML, resolver improvements | 2026-03 |
| v1.5 | Alerts UX + Epic title fix | v1.5.0 | Alerts redesign, DB cleanup, Epic title fallback chain | 2026-02 |
| v1.4 | SteamCMD + Alerts engine | v1.4.0 | steamcmd_api.py, alerts.py, field_history, 6 default rules | 2026-01 |
| v1.3 | Config file + wizard + UI polish | v1.3.0 | config.toml, steam-setup wizard, news overlay, tooltips | 2025-12 |
| v1.2 | Multi-store (Epic Games) | v1.2.0 | GameSource protocol, EpicSource, resolver chain, appid_mappings | 2025-11 |
| v1.1 | UI & i18n | v1.1.0 | Two-layer toolbar, recent-patch filter, EN/FR, URL hash | 2025-10 |
| v1.0 | Core | v1.0.0 | CLI, standalone EXE, GitHub Actions CI/CD | 2025-09 |

---

## Légende

### Types de tickets

| Préfixe | Type |
| --- | --- |
| `BIZ-NNN` | Fonctionnalité visible par l'utilisateur |
| `TEC-NNN` | Travail technique / refactoring |
| `CHR-NNN` | Chore / maintenance / dépendances |

### Priorités

| Priorité | Description |
| --- | --- |
| P1 | Critique — bloque les utilisateurs ou la production |
| P2 | Important — à planifier dans le prochain lot |
| P3 | Nice to have — planifié quand la capacité le permet |

### Formule d'estimation

- Par ticket : temps brut d'implémentation estimé × **1,15** (marge 15 %), arrondi aux 5 min.
- Par lot : somme des tickets + **15 min gestion projet** (relecture, approbation, merge).
