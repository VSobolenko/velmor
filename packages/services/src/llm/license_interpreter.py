from __future__ import annotations

from pydantic_ai import Agent

from packages.services.src.domain.interpretation import LicenseInterpretation


class LicenseInterpreter:
    """Read a rights statement out of page text as a validated object.

    The output is constrained to a schema, so a malformed or chatty answer cannot
    reach the rights engine: either the model returns a well-typed interpretation
    or the call fails loudly. Confidence is part of the schema because the graph
    uses it to decide whether a human must rule before publication.
    """

    SYSTEM_PROMPT = (
        'You read the licensing terms of a creative work from the text of its own page. '
        'Report only what the text actually states about reuse, resale and modification. '
        'If the text names a well-known license, return its identifier exactly as written. '
        'If the text does not state a license, set license_claim to null. '
        'Never infer a license from the platform, the file type, or the absence of a notice. '
        'Quote the exact sentence you relied on. '
        'Set confidence between 0 and 1: use a low value when the statement is ambiguous, '
        'partial, or contradicted elsewhere on the page.'
    )

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._agent: Agent[None, LicenseInterpretation] = Agent(
            model_name,
            output_type=LicenseInterpretation,
            system_prompt=self.SYSTEM_PROMPT,
        )

    async def interpret(self, page_text: str, title: str) -> LicenseInterpretation:
        result = await self._agent.run(
            f'Title: {title}\n\nPage text:\n{page_text}',
        )
        return result.output
