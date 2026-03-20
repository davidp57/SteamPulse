"""French translation strings."""
STRINGS: dict[str, str] = {
    # ── CLI ──────────────────────────────────────────────────────────────────
    "cli_fetching_library":  "📦 Récupération de la bibliothèque Steam...",
    "cli_owned_count":       "   ✅ {count} jeu(x) possédé(s)",
    "cli_fetching_wishlist": "🎁 Récupération de la wishlist...",
    "cli_wishlist_count":    "   ✅ {total} jeu(x) en wishlist · {new} nouveau(x)",
    "cli_wishlist_error":    "   ⚠ Wishlist inaccessible ({error})",
    "cli_fetching_followed": "👁 Récupération des jeux suivis...",
    "cli_followed_count":    "   ✅ {total} jeu(x) suivi(s) · {new} nouveau(x)",
    "cli_followed_error":    "   ⚠ Jeux suivis inaccessibles ({error})",
    "cli_pending": (
        "   {details} jeu(x) à récupérer · {news} news à rafraîchir ({cached} déjà à jour)"
    ),
    "cli_interrupted":       "\nArrêt.",
    "cli_wizard_done":        (
        "\n✅ Config sauvegardée dans : {path}\n"
        "   Relance le programme pour générer ton dashboard."
    ),
    "cli_fetch_done":        "\n✅ Terminé — {count} entrée(s) mise(s) à jour dans {db}",
    "cli_rendering":         "🖥  Génération des pages HTML...",
    "cli_render_library":    "✅ {count} jeux · bibliothèque → {path}",
    "cli_render_news":       "   {count} news → {path}",

    # ── CLI – Epic ────────────────────────────────────────────────────────────
    "cli_epic_auth_error":    "   ⚠ Authentification Epic échouée ({error})",
    "cli_epic_authenticated": "   ✅ Epic authentifié",
    "cli_epic_library_count": "   ✅ {count} jeu(x) dans la bibliothèque Epic",
    "cli_epic_library_error": "   ⚠ Bibliothèque Epic inaccessible ({error})",
    "cli_epic_resolving":     "🎮 Résolution des jeux Epic vers des AppIDs Steam...",
    "cli_epic_resolved_done": "   ✅ {resolved}/{total} résolus vers un AppID Steam ({unresolved} non résolus)",  # noqa: E501

    # ── HTML – common ─────────────────────────────────────────────────────────
    "html_lang":             "fr",
    "generated_at":          "Généré le",
    "search_placeholder":    "Rechercher un jeu...",
    "btn_filters":           "Filtres",
    "btn_reset":             "Reset",
    "btn_list_view":         "Liste",
    "btn_grid_view":         "Grille",
    "title_btn_filters":     "Afficher / masquer les filtres",
    "title_btn_reset":       "Réinitialiser tous les filtres",
    "title_view_toggle":     "Basculer Grille / Liste",
    "title_scroll_top":      "Retour en haut",
    "title_theme":           "Changer de thème",
    "filter_status":         "Statut",
    "filter_store":          "Store",
    "filter_collection":     "Biblioth\u00e8que",
    "filter_news_type":      "Type news",
    "filter_playtime":       "Temps de jeu",
    "filter_metacritic":     "Metacritic",
    "filter_recent":         "Màj récente",
    "lbl_all":               "Tous",
    "lbl_released":          "Sortis",
    "lbl_upcoming":          "À venir",
    "lbl_owned":             "Possédés",
    "lbl_followed":          "Suivis",
    "lbl_all_types":         "Tous types",
    "lbl_never_played":      "Jamais joué",
    "lbl_no_score":          "Sans score",
    "lbl_2_days":            "2 jours",
    "lbl_5_days":            "5 jours",
    "lbl_15_days":           "15 jours",
    "lbl_30_days":           "30 jours",
    "footer": (
        "SteamPulse · Données via Steam Web API &amp; Store API · Non affilié à Valve"
    ),

    # ── HTML – library page ───────────────────────────────────────────────────
    "stat_total":            "Jeux total",
    "stat_released":         "Sortis 1.0",
    "stat_unreleased":       "Pas sortis",
    "stat_hours":            "Heures jouées",
    "sort_name_asc":         "Trier : Nom A→Z",
    "sort_name_desc":        "Trier : Nom Z→A",
    "sort_playtime":         "Trier : Temps de jeu ↓",
    "sort_release":          "Trier : Date de sortie ↓",
    "sort_lastupdate":       "Trier : Dernière MàJ ↓",
    "sort_metacritic":       "Trier : Metacritic ↓",
    "link_news":             "News",
    "col_game":              "Jeu",
    "col_dev_score":         "Développeur / Score",
    "col_playtime_date":     "Temps de jeu · Date",

    # ── HTML – news page ──────────────────────────────────────────────────────
    "link_library":          "Bibliothèque",

    # ── Badge labels (renderer) ───────────────────────────────────────────────
    "badge_earlyaccess":     "Early Access",
    "badge_released":        "Sorti (1.0)",
    "badge_unreleased":      "Pas encore sorti",
    "badge_unknown":         "Inconnu",

    # ── Card (Python-generated) ───────────────────────────────────────────────
    "price_free":            "Gratuit",
    "source_wishlist":       "🎁 Wishlist",
    "source_followed":       "👁 Suivi",
    "source_epic":           "🎮 Epic",
    "card_no_news_html":     "Aucune news disponible",
    "card_news_toggle_0":    "Aucune news",
    "card_news_toggle_1":    "1 mise à jour",
    "card_news_toggle_n":    "{count} mises à jour",

    # ── JS i18n (injected as window.I18N) ────────────────────────────────────
    "js_news_0":             "Aucune news",
    "js_news_1":             "1 mise à jour",
    "js_news_n":             "{n} mises à jour",
    "js_no_match_games":     "Aucun jeu ne correspond à ta recherche.",
    "js_count_game_1":       "1 jeu",
    "js_count_game_n":       "{n} jeux",
    "js_no_match_news":      "Aucune news ne correspond.",
    "js_count_news":         "{n} news",

    # ── Infobulles des filtres ──────────────────────────────────────────────────────────────
    "tt_filter_earlyaccess": "Jeux actuellement en Early Access (pas v1.0)",
    "tt_filter_released":    "Jeux avec une sortie officielle v1.0",
    "tt_filter_unreleased":  "Jeux pas encore sortis",
    "tt_filter_lib_owned":   "Jeux que tu possèdes (Steam + Epic)",
    "tt_filter_lib_wishlist":"Jeux dans ta wishlist",
    "tt_filter_lib_followed":"Jeux que tu suis sans les posséder",
    "tt_filter_tag_patch":   "Afficher uniquement les patch notes",
    "tt_filter_tag_news":    "Afficher uniquement les articles de news",
    "tt_filter_pt_0":        "Jeux jamais lancés (0 minutes)",
    "tt_filter_pt_60":       "Jeux joués moins d\u2019une heure",
    "tt_filter_pt_600":      "Jeux joués entre 1 et 10 heures",
    "tt_filter_pt_601":      "Jeux joués plus de 10 heures",
    "tt_filter_mc_none":     "Jeux sans score Metacritic",
    "tt_filter_mc_bad":      "Score < 50 : critiques négatives",
    "tt_filter_mc_mid":      "Score 50–75 : critiques mitigées",
    "tt_filter_mc_good":     "Score > 75 : critiques favorables",
    "tt_filter_recent_2":    "Jeux avec une news dans les 2 derniers jours",
    "tt_filter_recent_5":    "Jeux avec une news dans les 5 derniers jours",
    "tt_filter_recent_15":   "Jeux avec une news dans les 15 derniers jours",
    "tt_filter_recent_30":   "Jeux avec une news dans les 30 derniers jours",

    # ── Infobulles des éléments de tuile ───────────────────────────────────────
    "tt_badge_earlyaccess":  "En accès anticipé — pas encore v1.0",
    "tt_badge_released":     "Version finale (v1.0 ou ultérieure)",
    "tt_badge_unreleased":   "Pas encore sorti",
    "tt_badge_unknown":      "Statut de sortie inconnu",
    "tt_developer":          "Développeur",
    "tt_price":              "Prix actuel sur Steam",
    "tt_release_date":       "Date de sortie",
    "tt_last_news":          "Date de la dernière actualité ou mise à jour",
    "tt_playtime":           "Temps de jeu total (depuis toujours)",
}
