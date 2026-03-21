"""Alert engine: evaluates AlertRules against news items and field changes."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from steam_tracker.db import Database
from steam_tracker.models import Alert, AlertRule, FieldChange, NewsItem

ALL_NEWS_RULE = AlertRule(
    name="All News",
    rule_type="news_keyword",
    icon="📰",
    enabled=True,
    keywords=[],
    match="any",
    builtin=True,
)

DEFAULT_ALERT_RULES: list[AlertRule] = [
    AlertRule(
        name="1.0 Release",
        rule_type="news_keyword",
        icon="🎉",
        keywords=["1.0", "full release", "out of early access", "leaves early access"],
        match="title",
    ),
    AlertRule(
        name="Version Update",
        rule_type="news_keyword",
        icon="🔄",
        keywords=["patch notes", "update", "hotfix", "changelog"],
        match="title",
    ),
    AlertRule(
        name="New DLC",
        rule_type="state_change",
        icon="🧩",
        field="dlc_appids",
        condition="changed",
    ),
    AlertRule(
        name="Price Drop",
        rule_type="state_change",
        icon="💰",
        field="price_final",
        condition="decreased",
    ),
    AlertRule(
        name="New Metacritic Score",
        rule_type="state_change",
        icon="⭐",
        field="metacritic_score",
        condition="appeared",
    ),
    AlertRule(
        name="Silent Update",
        rule_type="state_change",
        icon="🔧",
        field="buildid",
        condition="changed",
    ),
]


class AlertEngine:
    """Evaluates configured AlertRules against news items and field changes.

    Args:
        rules: Alert rules to evaluate. The caller is responsible for including
            the builtin "All News" rule if desired (use ``ALL_NEWS_RULE``).
        db: Database instance used for backfill operations.
    """

    def __init__(self, rules: list[AlertRule], db: Database) -> None:
        self._rules = rules
        self._db = db

    # ── public API ────────────────────────────────────────────────────────────

    def evaluate_news(
        self, appid: int, game_name: str, news: list[NewsItem]
    ) -> list[Alert]:
        """Evaluate all enabled news_keyword rules against a list of news items.

        Args:
            appid: Steam AppID of the game.
            game_name: Display name of the game.
            news: News items to evaluate.

        Returns:
            A list of Alert objects (one per matching rule/item pair).
        """
        alerts: list[Alert] = []
        for rule in self._rules:
            if not rule.enabled or rule.rule_type != "news_keyword":
                continue
            for item in news:
                if self._news_matches(rule, item):
                    alerts.append(self._make_news_alert(rule, appid, game_name, item))
        return alerts

    def evaluate_field_changes(
        self, appid: int, game_name: str, changes: list[FieldChange]
    ) -> list[Alert]:
        """Evaluate all enabled state_change rules against a list of field changes.

        Args:
            appid: Steam AppID of the game.
            game_name: Display name of the game.
            changes: Field changes to evaluate.

        Returns:
            A list of Alert objects (one per matching rule/change pair).
        """
        alerts: list[Alert] = []
        for rule in self._rules:
            if not rule.enabled or rule.rule_type != "state_change":
                continue
            for change in changes:
                if change.field_name != rule.field:
                    continue
                if self._change_matches(rule, change):
                    alerts.append(self._make_field_alert(rule, appid, game_name, change))
        return alerts

    def backfill(self, appid: int | None = None) -> int:
        """Re-evaluate all state_change rules against stored field_history.

        This is useful after adding new rules — it creates alerts for historical
        changes that happened before the rule was configured.

        Args:
            appid: If set, only backfill for this specific AppID.

        Returns:
            The number of new alerts inserted.
        """
        history = self._db.get_field_history(appid=appid)
        count = 0
        for change in history:
            game_name = self._resolve_game_name(change.appid)
            for rule in self._rules:
                if not rule.enabled or rule.rule_type != "state_change":
                    continue
                if change.field_name != rule.field:
                    continue
                if self._change_matches(rule, change):
                    alert = self._make_field_alert(rule, change.appid, game_name, change)
                    self._db.upsert_alert(alert)
                    count += 1
        return count

    # ── private helpers ───────────────────────────────────────────────────────

    def _resolve_game_name(self, appid: int) -> str:
        """Look up the game name from the database."""
        records = self._db.get_all_game_records()
        for r in records:
            if r.game.appid == appid:
                return r.game.name
        return str(appid)

    @staticmethod
    def _news_matches(rule: AlertRule, item: NewsItem) -> bool:
        """Return True if the news item satisfies the rule's keyword filter."""
        keywords = rule.keywords
        # Empty keyword list means "match everything" (the "All News" builtin).
        if not keywords:
            return True
        title = item.title.lower()
        content = item.contents.lower()
        for kw in keywords:
            kw_lower = kw.lower()
            if rule.match == "title" and kw_lower in title:
                return True
            if rule.match == "content" and kw_lower in content:
                return True
            if rule.match == "any" and (kw_lower in title or kw_lower in content):
                return True
        return False

    @staticmethod
    def _change_matches(rule: AlertRule, change: FieldChange) -> bool:
        """Return True if the field change satisfies the rule's condition."""
        old = change.old_value
        new = change.new_value
        condition = rule.condition
        if condition == "changed":
            return True
        if condition == "appeared":
            return old is None or old in ("", "0", "[]")
        if condition == "decreased":
            if old is None:
                return False
            try:
                return int(new) < int(old)
            except ValueError:
                return False
        if condition == "increased":
            if old is None:
                return False
            try:
                return int(new) > int(old)
            except ValueError:
                return False
        return False

    @staticmethod
    def _make_news_alert(
        rule: AlertRule, appid: int, game_name: str, item: NewsItem
    ) -> Alert:
        """Build a deterministic Alert from a matching news item."""
        raw = f"{rule.name}:{appid}:{item.gid}"
        alert_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return Alert(
            id=alert_id,
            rule_name=rule.name,
            rule_icon=rule.icon,
            appid=appid,
            game_name=game_name,
            timestamp=item.date,
            title=item.title,
            details=item.contents[:500] if item.contents else "",
            url=item.url,
            source_type="news",
            source_id=str(item.gid),
        )

    @staticmethod
    def _make_field_alert(
        rule: AlertRule, appid: int, game_name: str, change: FieldChange
    ) -> Alert:
        """Build a deterministic Alert from a matching field change."""
        ts = change.timestamp
        ts_str = ts.isoformat() if ts else ""
        raw = f"{rule.name}:{appid}:{change.field_name}:{ts_str}"
        alert_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        title = f"{change.field_name}: {change.old_value} → {change.new_value}"
        details = (
            f"Field '{change.field_name}' changed from"
            f" '{change.old_value}' to '{change.new_value}'"
        )
        return Alert(
            id=alert_id,
            rule_name=rule.name,
            rule_icon=rule.icon,
            appid=appid,
            game_name=game_name,
            timestamp=ts if ts else datetime.now(UTC),
            title=title,
            details=details,
            url="",
            source_type="field_change",
            source_id=f"{change.field_name}:{ts_str}",
        )
