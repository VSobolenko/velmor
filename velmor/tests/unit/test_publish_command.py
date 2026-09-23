from __future__ import annotations

from pathlib import Path

import pytest

from packages.api.tests.unit.configs.test_settings import TestCommerceSettings
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.services.src.commerce.image_payload import ImagePayload
from packages.services.src.domain.publication import PublicationAction
from velmor.publish import PublishCommand

CANDIDATE_ID = 'openverse:ce7c97e3-e1dc-4576-874c-c981cb49d04e'
ORIGIN_URL = 'https://upload.wikimedia.org/wikipedia/commons/7/77/Larch.svg'


def build_loader(tmp_path: Path) -> SettingsLoader:
    """A loader over a complete, fictional .env, so no bootstrap failure hides the report."""
    values = {**TestCommerceSettings.BASELINE_VALUES, **TestCommerceSettings.COMMERCE_VALUES}
    env_file = tmp_path / '.env.test'
    env_file.write_text('\n'.join(f'{key}={value}' for key, value in values.items()))
    return SettingsLoader(env_file)


class TestPublishOutcomeReport:
    """What the operator reads for a withdrawal, printed by the publish loop."""

    def test_a_withdrawal_prints_the_candidate_the_action_and_the_reason(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        command = PublishCommand(build_loader(tmp_path))

        command._log_outcome(
            CANDIDATE_ID,
            PublicationAction.WITHDRAWN,
            (ImagePayload.NOT_RENDERABLE_REASON,),
        )

        out = capsys.readouterr().out

        assert CANDIDATE_ID in out
        assert PublicationAction.WITHDRAWN.value in out
        assert ImagePayload.NOT_RENDERABLE_REASON in out

    def test_the_reported_line_names_no_origin(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        command = PublishCommand(build_loader(tmp_path))

        command._log_outcome(
            CANDIDATE_ID,
            PublicationAction.WITHDRAWN,
            (ImagePayload.NOT_RENDERABLE_REASON,),
        )

        out = capsys.readouterr().out

        assert ORIGIN_URL not in out
        assert 'http://' not in out
        assert 'https://' not in out
