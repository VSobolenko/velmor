from __future__ import annotations

from packages.core.src.bootstrap.platform_settings import PlatformSettings
from packages.core.src.bootstrap.settings_loader import SettingsLoader


class AuditorSettings(PlatformSettings):
    """Everything the rights-verification agent needs beyond the platform baseline.

    ``auditor_escalation_confidence`` is the threshold below which an interpreted
    rights statement is not trusted enough to decide automatically: the graph
    pauses and asks a human instead of guessing.
    """

    def __init__(self, loader: SettingsLoader) -> None:
        super().__init__(loader)
        self.auditor_model: str = loader.required_str('AUDITOR_MODEL')
        self.auditor_max_investigation_attempts: int = loader.required_int(
            'AUDITOR_MAX_INVESTIGATION_ATTEMPTS'
        )
        self.auditor_escalation_confidence: float = float(
            loader.required_str('AUDITOR_ESCALATION_CONFIDENCE')
        )
        self.auditor_batch_size: int = loader.required_int('AUDITOR_BATCH_SIZE')
        self.auditor_interval_seconds: int = loader.required_int('AUDITOR_INTERVAL_SECONDS')
        self.openai_api_key: str = loader.required_secret('OPENAI_API_KEY').get_secret_value()
