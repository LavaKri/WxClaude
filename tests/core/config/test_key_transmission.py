"""The ways the key of a provider can reach the CLI."""

import pytest

from wxclaude.core.config import key_transmission as kt

pytestmark = pytest.mark.unit


def test_masked_is_the_default_and_comes_first() -> None:
    assert kt.DEFAULT == kt.MASKED
    assert kt.CHOICES == (kt.MASKED, kt.SHARED, kt.RELAYED)


def test_the_old_yes_or_no_stands_for_masked_or_shared() -> None:
    assert kt.from_legacy_scrub(True) == kt.MASKED
    assert kt.from_legacy_scrub(False) == kt.SHARED


def test_every_choice_has_a_label_and_an_explanation() -> None:
    for choice in kt.CHOICES:
        assert kt.LABELS[choice]
        assert len(kt.EXPLANATIONS[choice]) > 80


def test_the_explanations_say_what_the_user_gives_up() -> None:
    assert "forces the permission mode to manual" in kt.EXPLANATIONS[kt.MASKED]
    assert "visible to all the models and tools" in kt.EXPLANATIONS[kt.SHARED]
    assert "rather meant for tests" in kt.EXPLANATIONS[kt.SHARED]
    assert "throw-away token" in kt.EXPLANATIONS[kt.RELAYED]
    assert "keeps no trace" in kt.EXPLANATIONS[kt.RELAYED]
