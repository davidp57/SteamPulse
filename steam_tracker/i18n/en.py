"""English translation strings."""
STRINGS: dict[str, str] = {
    # ── CLI ──────────────────────────────────────────────────────────────────
    "cli_fetching_library":  "📦 Fetching Steam library...",
    "cli_owned_count":       "   ✅ {count} game(s) owned",
    "cli_fetching_wishlist": "🎁 Fetching wishlist...",
    "cli_wishlist_count":    "   ✅ {total} game(s) in wishlist · {new} new",
    "cli_wishlist_error":    "   ⚠ Wishlist unavailable ({error})",
    "cli_fetching_followed": "👁 Fetching followed games...",
    "cli_followed_count":    "   ✅ {total} followed game(s) · {new} new",
    "cli_followed_error":    "   ⚠ Followed games unavailable ({error})",
    "cli_pending":           (
        "   {details} game(s) to fetch · {news} news to refresh ({cached} up to date)"
    ),
    "cli_interrupted":       "\nInterrupted.",
    "cli_wizard_done":        (
        "\n\u2705 Config saved to: {path}\n"
        "   Run the program again to generate your dashboard."
    ),
    "cli_fetch_done":        "\n✅ Done — {count} entry/entries updated in {db}",
    "cli_rendering":         "🖥  Rendering HTML pages...",
    "cli_render_library":    "✅ {count} games · library → {path}",
    "cli_render_news":       "   {count} news → {path}",

    # ── CLI – Epic –––––––––––––––––––––––––––––––––––––––––––––––––
    "cli_epic_auth_error":    "   ⚠ Epic authentication failed ({error})",
    "cli_epic_authenticated": "   ✅ Epic authenticated",
    "cli_epic_library_count": "   ✅ {count} game(s) in Epic library",
    "cli_epic_library_error": "   ⚠ Epic library unavailable ({error})",
    "cli_epic_resolving":     "🎮 Resolving Epic games to Steam AppIDs...",
    "cli_epic_resolved_done": "   ✅ {resolved}/{total} resolved to a Steam AppID ({unresolved} unresolved)",  # noqa: E501

    # ── HTML – common ─────────────────────────────────────────────────────────
    "html_lang":             "en",
    "generated_at":          "Generated on",
    "search_placeholder":    "Search for a game...",
    "btn_filters":           "Filters",
    "btn_reset":             "Reset",
    "btn_list_view":         "List",
    "btn_grid_view":         "Grid",
    "title_btn_filters":     "Show / hide filters",
    "title_btn_reset":       "Reset all filters",
    "title_view_toggle":     "Toggle Grid / List",
    "title_scroll_top":      "Back to top",
    "title_theme":           "Toggle theme",
    "filter_status":         "Status",
    "filter_store":          "Store",
    "filter_collection":     "Collection",
    "filter_news_type":      "News type",
    "filter_playtime":       "Playtime",
    "filter_metacritic":     "Metacritic",
    "filter_recent":         "Recent update",
    "lbl_all":               "All",
    "lbl_released":          "Released",
    "lbl_upcoming":          "Upcoming",
    "lbl_owned":             "Owned",
    "lbl_followed":          "Followed",
    "lbl_all_types":         "All types",
    "lbl_never_played":      "Never played",
    "lbl_no_score":          "No score",
    "lbl_2_days":            "2 days",
    "lbl_5_days":            "5 days",
    "lbl_15_days":           "15 days",
    "lbl_30_days":           "30 days",
    "footer":                (
        "SteamPulse · Data via Steam Web API &amp; Store API · Not affiliated with Valve"
    ),

    # ── HTML – library page ───────────────────────────────────────────────────
    "stat_total":            "Total games",
    "stat_released":         "Released 1.0",
    "stat_unreleased":       "Unreleased",
    "stat_hours":            "Hours played",
    "sort_name_asc":         "Sort: Name A→Z",
    "sort_name_desc":        "Sort: Name Z→A",
    "sort_playtime":         "Sort: Playtime ↓",
    "sort_release":          "Sort: Release date ↓",
    "sort_lastupdate":       "Sort: Last update ↓",
    "sort_metacritic":       "Sort: Metacritic ↓",
    "link_news":             "News",
    "col_game":              "Game",
    "col_dev_score":         "Developer / Score",
    "col_playtime_date":     "Playtime · Date",

    # ── HTML – news page ──────────────────────────────────────────────────────
    "link_library":          "Library",

    # ── Badge labels (renderer) ───────────────────────────────────────────────
    "badge_earlyaccess":     "Early Access",
    "badge_released":        "Released (1.0)",
    "badge_unreleased":      "Not yet released",
    "badge_unknown":         "Unknown",

    # ── Card (Python-generated) ───────────────────────────────────────────────
    "price_free":            "Free",
    "source_wishlist":       "🎁 Wishlist",
    "source_followed":       "👁 Followed",
    "source_epic":           "🎮 Epic",
    "card_no_news_html":     "No news available",
    "card_news_toggle_0":    "No news",
    "card_news_toggle_1":    "1 update",
    "card_news_toggle_n":    "{count} updates",

    # ── JS i18n (injected as window.I18N) ────────────────────────────────────
    "js_news_0":             "No news",
    "js_news_1":             "1 update",
    "js_news_n":             "{n} updates",
    "js_no_match_games":     "No games match your search.",
    "js_count_game_1":       "1 game",
    "js_count_game_n":       "{n} games",
    "js_no_match_news":      "No news match your search.",
    "js_count_news":         "{n} news",

    # ── Filter button tooltips ──────────────────────────────────────────────────────
    "tt_filter_earlyaccess": "Games currently in Early Access (not v1.0)",
    "tt_filter_released":    "Games with a full 1.0 release",
    "tt_filter_unreleased":  "Games not yet released",
    "tt_filter_lib_owned":   "Games you own (Steam + Epic)",
    "tt_filter_lib_wishlist":"Games on your wishlist",
    "tt_filter_lib_followed":"Games you follow without owning",
    "tt_filter_tag_patch":   "Show only patch note updates",
    "tt_filter_tag_news":    "Show only general news articles",
    "tt_filter_pt_0":        "Games launched for 0 minutes",
    "tt_filter_pt_60":       "Games played for less than 1 hour",
    "tt_filter_pt_600":      "Games played between 1 and 10 hours",
    "tt_filter_pt_601":      "Games played for more than 10 hours",
    "tt_filter_mc_none":     "Games with no Metacritic score",
    "tt_filter_mc_bad":      "Score < 50: negative or mixed reviews",
    "tt_filter_mc_mid":      "Score 50–75: generally mixed reviews",
    "tt_filter_mc_good":     "Score > 75: favorable reviews",
    "tt_filter_recent_2":    "Games with news in the last 2 days",
    "tt_filter_recent_5":    "Games with news in the last 5 days",
    "tt_filter_recent_15":   "Games with news in the last 15 days",
    "tt_filter_recent_30":   "Games with news in the last 30 days",

    # ── Card element tooltips ───────────────────────────────────────────────────
    "tt_badge_earlyaccess":  "Currently in Early Access — not yet v1.0",
    "tt_badge_released":     "Full release (v1.0 or later)",
    "tt_badge_unreleased":   "Not yet released",
    "tt_badge_unknown":      "Release status unknown",
    "tt_developer":          "Developer",
    "tt_price":              "Current price on Steam",
    "tt_release_date":       "Release date",
    "tt_last_news":          "Date of the latest news or update",
    "tt_playtime":           "Total playtime (all time)",
}
