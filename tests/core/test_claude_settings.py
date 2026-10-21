import json
from pathlib import Path

import pytest

from wxclaude.core.claude_settings import (
    Approval,
    Rule,
    SettingsFile,
    Source,
    ToolSettings,
    ToolState,
    allow_always,
    known_tools,
)
from wxclaude.core.errors import ClaudeSettingsError

pytestmark = pytest.mark.unit


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    workspace, config = tmp_path / "work", tmp_path / "config"
    return (
        workspace,
        config / "settings.json",
        workspace / ".claude" / "settings.json",
        (workspace / ".claude" / "settings.local.json"),
    )


def _load(tmp_path: Path) -> ToolSettings:
    workspace, _general, _shared, _local = _files(tmp_path)
    return ToolSettings.load(workspace, tmp_path / "config")


def test_a_rule_knows_its_tool_and_whether_it_covers_the_whole_tool() -> None:
    assert Rule(Approval.DENY, "Bash").tool == "Bash"
    assert Rule(Approval.DENY, "Bash(git *)").tool == "Bash"
    assert Rule(Approval.DENY, "Bash").is_bare
    assert Rule(Approval.DENY, "Bash(*)").is_bare
    assert not Rule(Approval.DENY, "Bash(git *)").is_bare
    assert Rule(Approval.ALLOW, "mcp__server__tool").is_bare


def test_a_rule_is_written_approval_then_pattern() -> None:
    assert Rule(Approval.DENY, "Bash(git *)").text() == "Deny, Bash(git *)"


def test_the_files_are_read_and_a_missing_one_is_empty(tmp_path: Path) -> None:
    workspace, general, shared, _local = _files(tmp_path)
    _write(general, {"permissions": {"deny": ["WebFetch"]}})
    _write(shared, {"permissions": {"allow": ["Bash(ls)", 3, "  "], "ask": ["Edit"]}})
    settings = _load(tmp_path)
    assert settings.rules(Source.GENERAL) == [Rule(Approval.DENY, "WebFetch")]
    assert settings.rules(Source.SETTINGS) == [
        Rule(Approval.ALLOW, "Bash(ls)"),
        Rule(Approval.ASK, "Edit"),
    ]
    assert settings.rules(Source.LOCAL) == []
    assert settings.files[Source.LOCAL].error == ""
    assert workspace  # the folder itself is not created by reading


def test_rules_are_sorted_by_tool_then_approval(tmp_path: Path) -> None:
    _workspace, _general, shared, _local = _files(tmp_path)
    _write(
        shared,
        {
            "permissions": {
                "allow": ["Bash(ls)", "Edit"],
                "deny": ["Bash(rm *)", "Agent"],
                "ask": ["Bash(git push *)"],
            }
        },
    )
    texts = [rule.text() for rule in _load(tmp_path).rules(Source.SETTINGS)]
    assert texts == [
        "Deny, Agent",
        "Deny, Bash(rm *)",
        "Ask, Bash(git push *)",
        "Allow, Bash(ls)",
        "Allow, Edit",
    ]


def test_a_damaged_file_is_reported_and_never_modified(tmp_path: Path) -> None:
    _workspace, _general, _shared, local = _files(tmp_path)
    local.parent.mkdir(parents=True)
    local.write_text("{ not json", encoding="utf-8")
    settings = _load(tmp_path)
    assert "Cannot read" in settings.files[Source.LOCAL].error
    with pytest.raises(ClaudeSettingsError):
        settings.add_rule(Source.LOCAL, Rule(Approval.ALLOW, "Bash"))
    assert settings.save() == []
    assert local.read_text(encoding="utf-8") == "{ not json"


def test_the_general_file_is_never_modified(tmp_path: Path) -> None:
    settings = _load(tmp_path)
    with pytest.raises(ClaudeSettingsError):
        settings.set_approval(Source.GENERAL, "Bash", Approval.DENY)
    assert not settings.files[Source.GENERAL].writable


def test_permissions_that_are_not_an_object_make_the_file_read_only(tmp_path: Path) -> None:
    _workspace, _general, shared, _local = _files(tmp_path)
    _write(shared, {"permissions": ["oops"]})
    assert _load(tmp_path).files[Source.SETTINGS].error


def test_the_state_of_a_tool_across_the_three_files(tmp_path: Path) -> None:
    """Claude denies, Settings asks, SettingsLocal asks: with Settings as target, it is denied."""
    _workspace, general, shared, local = _files(tmp_path)
    _write(general, {"permissions": {"deny": ["Bash"]}})
    _write(shared, {"permissions": {"ask": ["Bash"]}})
    _write(local, {"permissions": {"ask": ["Bash(git *)"]}})
    settings = _load(tmp_path)
    state = settings.state("Bash", Source.SETTINGS)
    assert state == ToolState(Approval.ASK, Approval.DENY, Source.GENERAL, True)
    assert state.text("Bash") == "Bash Ask, Deny by general, with rules"
    assert settings.state("Bash", Source.LOCAL).target is None
    assert settings.state("Bash", Source.LOCAL).text("Bash") == "Bash Deny by general, with rules"


def test_the_text_of_a_tool_leaves_out_what_has_no_value(tmp_path: Path) -> None:
    _workspace, _general, shared, _local = _files(tmp_path)
    _write(shared, {"permissions": {"allow": ["Edit"], "deny": ["Write(*)"]}})
    settings = _load(tmp_path)
    assert settings.state("Read", Source.SETTINGS).text("Read") == "Read"
    assert settings.state("Edit", Source.SETTINGS).text("Edit") == "Edit Allow"
    assert settings.state("Write", Source.SETTINGS).text("Write") == "Write Deny"
    # Another target: the shared file's value now comes "by Settings".
    assert settings.state("Edit", Source.LOCAL).text("Edit") == "Edit Allow by Settings"


def test_deny_beats_ask_beats_allow_whatever_the_file(tmp_path: Path) -> None:
    _workspace, _general, shared, local = _files(tmp_path)
    _write(shared, {"permissions": {"deny": ["Bash"]}})
    _write(local, {"permissions": {"allow": ["Bash"]}})
    state = _load(tmp_path).state("Bash", Source.LOCAL)
    assert (state.target, state.prevailing, state.origin) == (
        Approval.ALLOW,
        Approval.DENY,
        Source.SETTINGS,
    )


def test_tools_are_the_known_ones_plus_those_the_files_name(tmp_path: Path) -> None:
    _workspace, _general, shared, _local = _files(tmp_path)
    _write(shared, {"permissions": {"allow": ["mcp__server__tool", "Bash(ls)"]}})
    tools = _load(tmp_path).tools()
    assert "PowerShell" in tools
    assert "mcp__server__tool" in tools
    assert tools.count("Bash") == 1
    assert tools == sorted(tools, key=str.casefold)
    assert "PowerShell" in known_tools()


def test_set_approval_replaces_the_rules_without_specifier_of_the_tool(tmp_path: Path) -> None:
    _workspace, _general, shared, _local = _files(tmp_path)
    _write(shared, {"permissions": {"allow": ["Bash", "Bash(ls)"], "deny": ["Bash(*)"]}})
    settings = _load(tmp_path)
    settings.set_approval(Source.SETTINGS, "Bash", Approval.ASK)
    texts = [rule.text() for rule in settings.rules(Source.SETTINGS)]
    assert texts == ["Ask, Bash", "Allow, Bash(ls)"]  # the rule with a specifier stays


def test_add_and_remove_rules_without_any_check(tmp_path: Path) -> None:
    settings = _load(tmp_path)
    settings.add_rule(Source.LOCAL, Rule(Approval.ALLOW, "Bash"))
    settings.add_rule(Source.LOCAL, Rule(Approval.DENY, "Bash"))  # contradictory: allowed
    settings.add_rule(Source.LOCAL, Rule(Approval.ALLOW, "Bash"))  # twice: kept once
    assert [rule.text() for rule in settings.rules(Source.LOCAL)] == ["Deny, Bash", "Allow, Bash"]
    settings.remove_rule(Source.LOCAL, Rule(Approval.DENY, "Bash"))
    assert [rule.text() for rule in settings.rules(Source.LOCAL)] == ["Allow, Bash"]
    settings.remove_rule(Source.LOCAL, Rule(Approval.DENY, "Nothing"))


def test_save_writes_only_the_changed_files_keeps_other_keys_and_leaves_no_backup(
    tmp_path: Path,
) -> None:
    _workspace, _general, shared, local = _files(tmp_path)
    _write(shared, {"model": "opus", "permissions": {"allow": ["Edit"]}})
    settings = _load(tmp_path)
    assert settings.save() == []  # nothing changed
    settings.add_rule(Source.SETTINGS, Rule(Approval.DENY, "PowerShell"))
    assert settings.save() == [shared]
    saved = json.loads(shared.read_text(encoding="utf-8"))
    assert saved == {"model": "opus", "permissions": {"allow": ["Edit"], "deny": ["PowerShell"]}}
    assert not local.exists()
    assert sorted(path.name for path in shared.parent.iterdir()) == ["settings.json"]
    assert settings.save() == []  # written once


def test_save_creates_the_claude_folder(tmp_path: Path) -> None:
    settings = _load(tmp_path)
    settings.add_rule(Source.LOCAL, Rule(Approval.ASK, "Bash"))
    (path,) = settings.save()
    assert path.parent.name == ".claude"
    assert json.loads(path.read_text(encoding="utf-8")) == {"permissions": {"ask": ["Bash"]}}


def test_allow_always_adds_an_allow_rule_to_the_personal_file(tmp_path: Path) -> None:
    workspace, _general, _shared, local = _files(tmp_path)
    allow_always(workspace, "Bash(touch x)", tmp_path / "config")
    allow_always(workspace, "Bash(touch x)", tmp_path / "config")
    assert json.loads(local.read_text(encoding="utf-8")) == {
        "permissions": {"allow": ["Bash(touch x)"]}
    }


def test_allow_always_refuses_a_damaged_file(tmp_path: Path) -> None:
    workspace, _general, _shared, local = _files(tmp_path)
    local.parent.mkdir(parents=True)
    local.write_text("[]", encoding="utf-8")
    with pytest.raises(ClaudeSettingsError):
        allow_always(workspace, "Bash", tmp_path / "config")
    assert local.read_text(encoding="utf-8") == "[]"


def test_a_settings_file_that_is_a_directory_is_reported(tmp_path: Path) -> None:
    folder = tmp_path / "settings.json"
    folder.mkdir()
    assert SettingsFile.load(Source.SETTINGS, folder).error
