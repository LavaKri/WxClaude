"""The list *Variable* of the form of a provider: lines, values, explanations. No window."""

import pytest

from wxclaude.core.config.provider_variables import PROVIDER_VARIABLES
from wxclaude.core.config.providers import MODEL_MAX, Provider
from wxclaude.presenters.provider_variables_editor import (
    VARIABLE_VALUE_MAX,
    ProviderVariablesEditor,
)

pytestmark = pytest.mark.unit


def provider(**changes: object) -> Provider:
    made = Provider(
        id="p",
        name="P",
        base_url="http://x",
        tiers=["flash", "flash", "pro", "pro"],
        env={"API_TIMEOUT_MS": "600000"},
    )
    for name, value in changes.items():
        setattr(made, name, value)
    return made


def test_the_list_holds_the_four_models_then_the_variables() -> None:
    editor = ProviderVariablesEditor(provider())
    assert len(editor) == 8
    assert editor.lines == [
        "Small model = flash",
        "Medium model = flash",
        "Large model = pro",
        "Largest model = pro",
        "API_TIMEOUT_MS = 600000",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS = (not set)",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW = (not set)",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS = (not set)",
    ]


def test_an_empty_model_says_that_it_takes_the_weakest_one() -> None:
    editor = ProviderVariablesEditor(provider())
    editor.set_value(1, "  ")
    assert editor.line(1) == "Medium model = (as the weakest model given)"


def test_a_new_provider_starts_with_nothing_set() -> None:
    editor = ProviderVariablesEditor(Provider(id="", name=""))
    assert editor.tiers == ["", "", "", ""]
    assert editor.env == dict.fromkeys(PROVIDER_VARIABLES, "")
    assert editor.line(0) == "Small model = (as the weakest model given)"


def test_a_value_is_edited_and_its_line_follows() -> None:
    editor = ProviderVariablesEditor(provider())
    editor.set_value(5, " 65536 ")
    assert editor.value(5) == " 65536 "  # as typed: the provider strips it
    assert editor.line(5) == "CLAUDE_CODE_MAX_CONTEXT_TOKENS = 65536"
    assert editor.line(0) == "Small model = flash"  # the other lines are untouched


def test_the_values_make_the_provider_the_way_the_four_fields_did() -> None:
    editor = ProviderVariablesEditor(provider(tiers=[]))
    editor.set_value(1, " b ")
    editor.set_value(3, "big")
    editor.set_value(4, "")
    made = Provider(id="p", name="P", base_url="http://x", tiers=editor.tiers, env=editor.env)
    assert made.tiers == ["b", "b", "b", "big"]  # the weakest given fills the empty ones
    assert made.env == {}


def test_the_variables_come_out_as_a_provider_env() -> None:
    editor = ProviderVariablesEditor(provider())
    editor.set_value(5, "65536")
    made = Provider(id="p", name="P", base_url="http://x", tiers=editor.tiers, env=editor.env)
    assert made.env == {"API_TIMEOUT_MS": "600000", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "65536"}
    assert made.problem() is None


def test_each_line_is_explained_and_the_models_name_their_alias() -> None:
    editor = ProviderVariablesEditor(provider())
    assert "haiku" in editor.explanation(0)
    assert "sonnet" in editor.explanation(1)
    assert "opus" in editor.explanation(2)
    assert "no alias" in editor.explanation(3)
    assert "waits for the response headers" in editor.explanation(4)
    assert editor.explanation(5).endswith("Empty: not set.")


def test_the_length_of_a_value_is_limited_to_what_it_can_be() -> None:
    editor = ProviderVariablesEditor(provider())
    lengths = [editor.max_length(i) for i in range(len(editor))]
    assert lengths == [MODEL_MAX] * 4 + [VARIABLE_VALUE_MAX] * len(PROVIDER_VARIABLES)


def test_every_variable_of_the_list_is_described_by_the_list_of_claude_code() -> None:
    editor = ProviderVariablesEditor(provider())
    for index in range(4, len(editor)):
        assert "not described" not in editor.explanation(index)


def test_the_label_names_the_variable_for_the_text_field() -> None:
    editor = ProviderVariablesEditor(provider())
    assert [editor.label(i) for i in (0, 3, 4)] == [
        "Small model",
        "Largest model",
        "API_TIMEOUT_MS",
    ]
