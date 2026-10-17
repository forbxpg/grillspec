"""Plugin manifests and hook configs parse and agree on the version."""

from __future__ import annotations

import json
from pathlib import Path

import grillspec

REPO = Path(__file__).resolve().parents[2]
PLUGINS = (
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".antigravity-plugin/plugin.json",
)
HOOK_CONFIGS = (
    "hooks/hooks.json",
    "hooks/hooks-cursor.json",
    "hooks/hooks-codex.json",
    "hooks.json",
)


def load(relative: str) -> dict[str, object]:
    return json.loads((REPO / relative).read_text(encoding="utf-8"))


def test_manifests_parse_and_share_version():
    for relative in PLUGINS:
        data = load(relative)
        assert data["name"] == "grillspec", relative
        assert data["version"] == grillspec.__version__, relative
    market = load(".claude-plugin/marketplace.json")
    plugins = market["plugins"]
    assert isinstance(plugins, list)
    assert plugins[0]["version"] == grillspec.__version__
    load(".agents/plugins/marketplace.json")


def test_hook_configs_call_the_runner_per_harness():
    expected = {
        "hooks/hooks.json": "session-start claude",
        "hooks/hooks-cursor.json": "session-start cursor",
        "hooks/hooks-codex.json": "session-start codex",
        "hooks.json": "session-start antigravity",
    }
    for relative, needle in expected.items():
        text = (REPO / relative).read_text(encoding="utf-8")
        json.loads(text)
        assert "run-hook.cmd" in text, relative
        assert needle in text, relative


def test_codex_points_at_its_own_hooks():
    assert load(".codex-plugin/plugin.json")["hooks"] == "./hooks/hooks-codex.json"
