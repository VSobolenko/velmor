from __future__ import annotations

from pathlib import Path

import pytest
import typer

from packages.api.tests.unit.configs.test_settings import TestCommerceSettings
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from velmor.curate import CurateCommand

MODEL = 'openai:gpt-4o-mini'


def build_loader(tmp_path: Path) -> SettingsLoader:
    """A loader over a complete, fictional .env, so no bootstrap failure hides the guard."""
    values = {**TestCommerceSettings.BASELINE_VALUES, **TestCommerceSettings.COMMERCE_VALUES}
    env_file = tmp_path / '.env.test'
    env_file.write_text('\n'.join(f'{key}={value}' for key, value in values.items()))
    return SettingsLoader(env_file)


class TestCurateRefusal:
    """A run that would write copy needs --apply.

    The guard is checked before the run opens a store, which is what lets it be
    tested here without a database, a model or a network.
    """

    def test_without_apply_the_run_refuses_with_a_non_zero_exit(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        command = CurateCommand(build_loader(tmp_path))

        with pytest.raises(typer.Exit) as refusal:
            command.run(MODEL, 10, apply=False)

        assert refusal.value.exit_code == 1
        assert '--apply' in capsys.readouterr().err
