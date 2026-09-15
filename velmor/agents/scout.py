from __future__ import annotations

from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.scout.src.configs.settings import ScoutSettings
from packages.scout.src.ingest import ScoutJob
from packages.scout.src.runner import ScoutRunner
from packages.services.src.connectors.factory import ConnectorFactory
from velmor.agents.base import AgentCommand
from velmor.container import Container


class ScoutAgent(AgentCommand):
    """Discovery: crawl every enabled source and store whatever it exposes.

    Two commands. ``once`` performs a single pass and reports what it found.
    ``loop`` performs a pass on the configured interval until interrupted, which
    is how the crawler is meant to run in production.
    """

    COMMANDS: tuple[str, ...] = ('once', 'loop')

    def __init__(self, loader: SettingsLoader) -> None:
        self._settings = ScoutSettings(loader)

    async def execute(self, command: str) -> None:
        self._reject_unknown(command, self.COMMANDS)

        async with Container(self._settings, service_name='velmor-scout') as container:
            runner = ScoutRunner(
                ScoutJob(
                    registry=container.registry,
                    factory=ConnectorFactory(container.http),
                    repository=await container.candidate_repository(),
                ),
                queries=self._settings.scout_queries,
                page_limit=self._settings.scout_page_limit,
                interval_seconds=self._settings.scout_interval_seconds,
            )
            match command:
                case 'once':
                    await self._report(await runner.run_once())
                case 'loop':
                    print(
                        f'[scout] looping every {self._settings.scout_interval_seconds}s '
                        f'over {len(self._settings.scout_queries)} queries'
                    )
                    await runner.run()

    async def _report(self, runs: tuple) -> None:
        for run in runs:
            print(
                f'[scout] query={run.query!r} discovered={run.discovered} '
                f'stored={run.persisted} failures={len(run.failures)}'
            )
            for failure in run.failures:
                print(f'[scout]   {failure.source_id}: {failure.reason}')
