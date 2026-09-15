from __future__ import annotations

import asyncio

from packages.auditor.src.configs.settings import AuditorSettings
from packages.auditor.src.graph import AuditorGraph
from packages.auditor.src.runner import AuditorRunner
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.services.src.domain.verification_run import (
    CandidateOutcome,
    VerificationOutcome,
    VerificationRun,
)
from packages.services.src.http_service.page_fetcher import PageFetcher
from packages.services.src.llm.license_interpreter import LicenseInterpreter
from packages.services.src.rights.engine import RightsEngine
from velmor.agents.base import AgentCommand
from velmor.container import Container


class AuditorRunReport:
    """Write one verification pass to the console.

    Every outcome is named, including the ones that produced no decision at all.
    A candidate that disappears between discovery and the storefront is the
    failure this pipeline exists to prevent, so "screened out" and "paused" are
    printed as themselves and never folded into the rejection count.
    """

    LABELS: tuple[tuple[VerificationOutcome, str], ...] = (
        (VerificationOutcome.PUBLISHED, 'PUBLISH'),
        (VerificationOutcome.REFUSED, 'REJECT'),
        (VerificationOutcome.SCREENED_OUT, 'SCREENED OUT'),
        (VerificationOutcome.PAUSED, 'PAUSED'),
    )

    PUBLISHED_REASON = 'all conditions met'

    def show(self, run: VerificationRun) -> None:
        print(f'[auditor] run={run.run_id} candidates={len(run.outcomes)} {self._totals(run)}')
        for refusal in run.refusals_by_category:
            print(f'[auditor]   screened {refusal.category!r}: {refusal.count}')
        for outcome in run.outcomes:
            print(f'[auditor]   {self._line(outcome)}')

    def _totals(self, run: VerificationRun) -> str:
        return ' '.join(
            f'{self._label(outcome)}={self._count(run, outcome)}' for outcome, _ in self.LABELS
        )

    def _line(self, outcome: CandidateOutcome) -> str:
        label = self._label(outcome.outcome)
        reason = '; '.join(outcome.reasons) if outcome.reasons else self.PUBLISHED_REASON
        if outcome.decision is None:
            return f'{label} {outcome.candidate_id} {reason}'
        licence = outcome.decision.record.license_id or 'no licence'
        return f'{label} {outcome.candidate_id} [{licence}] {reason}'

    @staticmethod
    def _count(run: VerificationRun, outcome: VerificationOutcome) -> int:
        return sum(1 for item in run.outcomes if item.outcome is outcome)

    def _label(self, outcome: VerificationOutcome) -> str:
        return dict(self.LABELS)[outcome]


class AuditorAgent(AgentCommand):
    """Rights verification: decide what may be published, and prove why.

    Two commands. ``once`` verifies one batch of candidates that has no verdict
    yet. ``loop`` keeps taking batches on the configured interval.
    """

    COMMANDS: tuple[str, ...] = ('once', 'loop')

    def __init__(self, loader: SettingsLoader) -> None:
        self._settings = AuditorSettings(loader)
        self._report = AuditorRunReport()

    async def execute(self, command: str) -> None:
        self._reject_unknown(command, self.COMMANDS)

        async with Container(self._settings, service_name='velmor-auditor') as container:
            runner = AuditorRunner(
                compiled_graph=(await self._build_graph(container)).build(),
                registry=container.registry,
                screen=container.screen,
                candidates=await container.candidate_repository(),
                verdicts=await container.verdict_repository(),
                batch_size=self._settings.auditor_batch_size,
            )
            match command:
                case 'once':
                    self._report.show(await runner.run_once())
                case 'loop':
                    print(
                        f'[auditor] looping every {self._settings.auditor_interval_seconds}s '
                        f'in batches of {self._settings.auditor_batch_size}'
                    )
                    await self._loop(runner)

    async def _loop(self, runner: AuditorRunner) -> None:
        while True:
            self._report.show(await runner.run_once())
            await asyncio.sleep(self._settings.auditor_interval_seconds)

    async def _build_graph(self, container: Container) -> AuditorGraph:
        return AuditorGraph(
            engine=container.engine,
            fetcher=PageFetcher(container.http),
            interpreter=LicenseInterpreter(self._settings.auditor_model),
            clock=container.clock,
            model_name=self._settings.auditor_model,
            max_investigation_attempts=self._settings.auditor_max_investigation_attempts,
            escalation_confidence=self._settings.auditor_escalation_confidence,
            requested_actions=RightsEngine.STOREFRONT_ACTIONS,
            checkpointer=await container.checkpointer(),
        )
