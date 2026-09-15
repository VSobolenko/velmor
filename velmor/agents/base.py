from __future__ import annotations

from abc import ABC, abstractmethod


class AgentCommand(ABC):
    """A runnable agent, addressed by a subcommand string.

    The CLI knows agents only through this interface, so adding an agent means
    adding a class here and one entry in the dispatcher - it never means touching
    the argument parser.
    """

    @abstractmethod
    async def execute(self, command: str) -> None:
        """Run one subcommand of this agent."""

    def _reject_unknown(self, command: str, known: tuple[str, ...]) -> None:
        if command not in known:
            raise ValueError(
                f'{self.__class__.__name__} does not know command {command!r}. '
                f'Known commands: {", ".join(known)}'
            )
