from __future__ import annotations

from packages.auditor.src.state import AuditorState
from packages.services.src.clock import Clock
from packages.services.src.domain.rights import Evidence, EvidenceKind
from packages.services.src.http_service.page_fetcher import PageFetcher
from packages.services.src.llm.license_interpreter import LicenseInterpreter


class InvestigateNode:
    """Read the item's own page and ask the model what it says about reuse.

    This is the only node that costs money and the only one that can be wrong
    about content, so it records both the sentence it relied on and the claim it
    derived. The gate treats the derived claim as inferential and will not publish
    on it alone.
    """

    EXTRACTOR_VERSION = '1.0.0'

    def __init__(
        self,
        fetcher: PageFetcher,
        interpreter: LicenseInterpreter,
        clock: Clock,
        model_name: str,
    ) -> None:
        self._fetcher = fetcher
        self._interpreter = interpreter
        self._clock = clock
        self._model_name = model_name

    async def __call__(self, state: AuditorState) -> dict:
        candidate = state['candidate']
        page_text = await self._fetcher.fetch_text(candidate.landing_url)
        interpretation = await self._interpreter.interpret(page_text, candidate.title)

        now = self._clock.now()
        evidence = (
            Evidence(
                kind=EvidenceKind.LICENSE_FILE,
                locator=candidate.landing_url,
                excerpt=interpretation.quoted_text,
                retrieved_at=now,
                extractor_version=self.EXTRACTOR_VERSION,
            ),
            Evidence(
                kind=EvidenceKind.LLM_EXTRACTION,
                locator=candidate.landing_url,
                excerpt=interpretation.license_claim or '(no licence stated)',
                retrieved_at=now,
                extractor_version=self._model_name,
            ),
        )
        return {
            'interpretation': interpretation,
            'investigation_attempts': state['investigation_attempts'] + 1,
            'evidence': [*state['evidence'], *evidence],
        }
