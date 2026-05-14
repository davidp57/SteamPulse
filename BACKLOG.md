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

### BIZ-007 — Intégration Playnite : bouton "Ouvrir dans Playnite"

Ajouter sur chaque carte de la bibliothèque un bouton optionnel pour ouvrir le jeu directement dans Playnite via son protocole URI. Le bouton utilise systématiquement `playnite://playnite/search/<nom encodé>` pour tous les jeux et toutes les stores (Steam, Epic, GOG, Xbox…).

**Activation :**
- Config TOML : `[playnite] enabled = true`.
- CLI : `--playnite` flag.
- Sans activation, aucun bouton n'est rendu.

**URI utilisée :** `playnite://playnite/search/<nom encodé>` — ouvre Playnite et lance une recherche. Universel, fonctionne sans configuration côté serveur.

**Note :** Le mode enrichi (import CSV → UUID → `showgame` URI) a été abandonné car l'approche était fragile (dépendance au chemin exact de la DB, jointure complexe pour Epic). La recherche par nom couvre 100 % des jeux sans import.

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
