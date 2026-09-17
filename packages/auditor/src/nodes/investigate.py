from __future__ import annotations

import httpx

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

    The quote counts as source evidence only when the page actually contains it.
    The model chooses which sentence to quote, so without that check an invented
    sentence would be recorded as though the page had stated it, and the gate -
    which accepts a licence file as evidence from the source - would publish on
    the model's word alone. A quote the page does not contain leaves the reading
    as the only evidence, which the gate refuses.
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
        try:
            page_text = await self._fetcher.fetch_text(candidate.landing_url)
        except httpx.HTTPError as error:
            # httpx reports both a 4xx/5xx answer (HTTPStatusError, raised by
            # raise_for_status) and a transport failure (RequestError) as
            # HTTPError subclasses. A landing page whose target has been deleted
            # is a routine answer from a third party - Openverse stores URLs that
            # outlive the item - so the attempt is spent and the reason carried
            # in the state, rather than aborting the batch on one dead link.
            return {
                'investigation_attempts': state['investigation_attempts'] + 1,
                'investigation_failures': [
                    *state['investigation_failures'],
                    f'fetch failed for {candidate.landing_url}: {error}',
                ],
            }

        interpretation = await self._interpreter.interpret(page_text, candidate.title)

        now = self._clock.now()
        evidence: list[Evidence] = []

        quote = self._verified_quote(page_text, interpretation.quoted_text)
        if quote is not None:
            evidence.append(
                Evidence(
                    kind=EvidenceKind.LICENSE_FILE,
                    locator=candidate.landing_url,
                    excerpt=quote,
                    retrieved_at=now,
                    extractor_version=self.EXTRACTOR_VERSION,
                )
            )

        evidence.append(
            Evidence(
                kind=EvidenceKind.LLM_EXTRACTION,
                locator=candidate.landing_url,
                excerpt=interpretation.license_claim or '(no licence stated)',
                retrieved_at=now,
                extractor_version=self._model_name,
            )
        )
        return {
            'interpretation': interpretation,
            'investigation_attempts': state['investigation_attempts'] + 1,
            'evidence': [*state['evidence'], *evidence],
        }

    @staticmethod
    def _verified_quote(page_text: str, quoted_text: str) -> str | None:
        """The quote, or ``None`` when the page does not contain it.

        Whitespace is collapsed on the quote before the comparison because the
        fetcher collapses it in the page text as well; a reflowed line break is
        not a difference in what the page says. Nothing else is normalised: case,
        punctuation and wording have to match, so a paraphrase is not a quote and
        an empty quote is not evidence.
        """
        collapsed = ' '.join(quoted_text.split())
        if not collapsed:
            return None
        if collapsed not in page_text:
            return None
        return collapsed
