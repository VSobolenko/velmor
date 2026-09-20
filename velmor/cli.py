"""Velmor CLI.

Only the composition root knows which agents exist and where each one keeps its
``.env`` profile. The packages stay unaware of the command line, so an agent can
also be driven from a test or from the API without going through here.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from packages.core.src.bootstrap.environment import Environment
from packages.core.src.bootstrap.platform_settings import PlatformSettings
from packages.core.src.bootstrap.project_root import PROJECT_ROOT
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.core.src.errors import VelmorError
from velmor.agents.base import AgentCommand
from velmor.container import Container

app = typer.Typer(
    help='Velmor - rights-verified marketplace platform',
    no_args_is_help=True,
    add_completion=False,
)


class Agent(StrEnum):
    """The agents this CLI can run."""

    SCOUT = 'scout'
    AUDITOR = 'auditor'


class EnvFileResolver:
    """Map an agent and a profile onto the ``.env.<profile>`` file to load."""

    ROOTS: dict[Agent, Path] = {
        Agent.SCOUT: PROJECT_ROOT / 'packages' / 'scout',
        Agent.AUDITOR: PROJECT_ROOT / 'packages' / 'auditor',
    }

    API_ROOT: Path = PROJECT_ROOT / 'packages' / 'api'

    @classmethod
    def resolve(cls, agent: Agent, environment: Environment) -> Path:
        return cls._profile_file(cls.ROOTS[agent], environment)

    @classmethod
    def resolve_api(cls, environment: Environment) -> Path:
        """The storefront is not an agent, so it has its own profile root."""
        return cls._profile_file(cls.API_ROOT, environment)

    @classmethod
    def _profile_file(cls, root: Path, environment: Environment) -> Path:
        env_file = root / f'.env.{environment.value}'
        if not env_file.exists():
            raise FileNotFoundError(
                f'Environment file not found: {env_file}. '
                f'Copy .env.example to .env.{environment.value} in {root}'
            )
        return env_file


class AgentDispatcher:
    """Turn a CLI invocation into one agent subcommand.

    Agent modules are imported inside the dispatch, not at module scope, so
    ``--help`` and the source listing do not pay to import the whole agent stack.
    """

    def dispatch(self, agent: Agent, environment: Environment, command: str) -> None:
        loader = SettingsLoader(EnvFileResolver.resolve(agent, environment))
        asyncio.run(self._command_for(agent, loader).execute(command))

    @staticmethod
    def _command_for(agent: Agent, loader: SettingsLoader) -> AgentCommand:
        match agent:
            case Agent.SCOUT:
                from velmor.agents.scout import ScoutAgent

                return ScoutAgent(loader)
            case Agent.AUDITOR:
                from velmor.agents.auditor import AuditorAgent

                return AuditorAgent(loader)


class SourceListing:
    """Print every registered source and whether it is crawlable right now."""

    def show(self, environment: Environment) -> None:
        loader = SettingsLoader(EnvFileResolver.resolve(Agent.SCOUT, environment))
        container = Container(PlatformSettings(loader), service_name='velmor')
        for spec in container.registry.all_specs():
            state = 'enabled' if spec.enabled else 'disabled'
            typer.echo(f'{spec.id:<20} tier {spec.tier.value.upper()}  {state:<9} {spec.name}')


@app.command('run')
def run(
    agent: Annotated[Agent, typer.Argument(help='Which agent to run')],
    environment: Annotated[
        Environment,
        typer.Option('--env', '-e', help='Deployment profile to load'),
    ] = Environment.DEV,
    command: Annotated[
        str,
        typer.Option('--command', '-c', help='Which subcommand of that agent to run'),
    ] = 'once',
) -> None:
    """Run one agent against one profile."""
    try:
        AgentDispatcher().dispatch(agent, environment, command)
    except (VelmorError, FileNotFoundError, ValueError) as error:
        typer.secho(f'error: {error}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error


@app.command('sources')
def sources(
    environment: Annotated[
        Environment,
        typer.Option('--env', '-e', help='Deployment profile to inspect'),
    ] = Environment.DEV,
) -> None:
    """List every registered source and whether it is crawlable right now."""
    try:
        SourceListing().show(environment)
    except (VelmorError, FileNotFoundError) as error:
        typer.secho(f'error: {error}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error


@app.command('serve')
def serve(
    environment: Annotated[
        Environment,
        typer.Option('--env', '-e', help='Deployment profile to load'),
    ] = Environment.DEV,
    host: Annotated[
        str,
        typer.Option('--host', help='Interface to bind (127.0.0.1 unless exposed on purpose)'),
    ] = '127.0.0.1',
    port: Annotated[int, typer.Option('--port', help='Port to bind')] = 8080,
) -> None:
    """Serve the storefront over HTTP."""
    # Imported here for the same reason the agent modules are: it pulls in the ASGI
    # stack, which `--help` and `sources` should not pay for.
    from velmor.api_server import ApiServer

    try:
        loader = SettingsLoader(EnvFileResolver.resolve_api(environment))
        ApiServer(loader).run(host, port)
    except (VelmorError, FileNotFoundError, ValueError) as error:
        typer.secho(f'error: {error}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error


@app.command('publish')
def publish(
    environment: Annotated[
        Environment,
        typer.Option('--env', '-e', help='Deployment profile to load'),
    ] = Environment.DEV,
    limit: Annotated[
        int,
        typer.Option('--limit', help='Max gate-publishable goods to process'),
    ] = 200,
) -> None:
    """Publish gate-approved goods into Saleor and the paid catalogue."""
    # Imported here so `--help` and `sources` do not pay for the commerce stack.
    from velmor.publish import PublishCommand

    try:
        loader = SettingsLoader(EnvFileResolver.resolve_api(environment))
        PublishCommand(loader).run(limit)
    except (VelmorError, FileNotFoundError, ValueError) as error:
        typer.secho(f'error: {error}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error


def main() -> None:
    app()
