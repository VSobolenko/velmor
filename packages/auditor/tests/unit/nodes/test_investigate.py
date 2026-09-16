from __future__ import annotations

from packages.auditor.src.nodes.investigate import InvestigateNode
from packages.auditor.tests.conftest import (
    FakeInterpreter,
    FakePageFetcher,
    FixedClock,
    build_state,
)
from packages.services.src.domain.interpretation import LicenseInterpretation
from packages.services.src.domain.rights import EvidenceKind
from packages.services.tests.conftest import build_candidate, build_spec

PAGE_TEXT = 'All images on this page are licensed under CC BY 4.0.'

INTERPRETED = LicenseInterpretation(
    license_claim='CC-BY-4.0',
    confidence=0.6,
    quoted_text='All images on this page are licensed under CC BY 4.0.',
    reasoning='the page states a Creative Commons attribution licence',
)


class InvestigateCase:
    """The node under test, wired to a fetcher and an interpreter that record calls."""

    def build_node(
        self, clock: FixedClock, interpretation: LicenseInterpretation
    ) -> tuple[InvestigateNode, FakePageFetcher]:
        fetcher = FakePageFetcher(PAGE_TEXT)
        interpreter = FakeInterpreter(interpretation)
        node = InvestigateNode(fetcher, interpreter, clock, model_name='test-model')
        return node, fetcher


class TestInvestigateNode(InvestigateCase):
    async def test_the_page_text_is_read_and_the_reading_is_recorded(
        self, clock: FixedClock
    ) -> None:
        node, fetcher = self.build_node(clock, INTERPRETED)
        state = build_state(build_candidate(license_id=None), build_spec())

        result = await node(state)

        assert fetcher.fetched == ['https://openverse.test/items/openverse:1']
        assert result['interpretation'] == INTERPRETED

    async def test_the_quote_and_the_claim_are_recorded_as_separate_kinds(
        self, clock: FixedClock
    ) -> None:
        node, _ = self.build_node(clock, INTERPRETED)
        state = build_state(build_candidate(license_id=None), build_spec())

        result = await node(state)

        quote, claim = result['evidence']
        assert quote.kind is EvidenceKind.LICENSE_FILE
        assert quote.excerpt == INTERPRETED.quoted_text
        assert quote.locator == 'https://openverse.test/items/openverse:1'
        assert claim.kind is EvidenceKind.LLM_EXTRACTION
        assert claim.excerpt == 'CC-BY-4.0'
        assert claim.extractor_version == 'test-model'

    async def test_the_model_reading_is_never_recorded_as_source_evidence(
        self, clock: FixedClock
    ) -> None:
        node, _ = self.build_node(clock, INTERPRETED)
        state = build_state(build_candidate(license_id=None), build_spec())

        result = await node(state)

        kinds = {item.kind for item in result['evidence']}
        assert EvidenceKind.LLM_EXTRACTION in kinds
        assert EvidenceKind.SOURCE_API_FIELD not in kinds

    async def test_each_attempt_is_counted(self, clock: FixedClock) -> None:
        node, _ = self.build_node(clock, INTERPRETED)
        state = build_state(
            build_candidate(license_id=None), build_spec(), investigation_attempts=1
        )

        result = await node(state)

        assert result['investigation_attempts'] == 2

    async def test_rerunning_from_the_same_state_does_not_duplicate_evidence(
        self, clock: FixedClock
    ) -> None:
        node, _ = self.build_node(clock, INTERPRETED)
        state = build_state(build_candidate(license_id=None), build_spec())

        first = await node(state)
        second = await node(state)

        assert first == second
        assert len(second['evidence']) == 2
        assert second['investigation_attempts'] == 1

    async def test_a_second_attempt_accumulates_evidence_and_attempts(
        self, clock: FixedClock
    ) -> None:
        node, _ = self.build_node(clock, INTERPRETED)
        state = build_state(build_candidate(license_id=None), build_spec())

        first = await node(state)
        second = await node({**state, **first})

        assert [item.kind for item in second['evidence']] == [
            EvidenceKind.LICENSE_FILE,
            EvidenceKind.LLM_EXTRACTION,
            EvidenceKind.LICENSE_FILE,
            EvidenceKind.LLM_EXTRACTION,
        ]
        assert second['investigation_attempts'] == 2


class TestInvestigateNodeQuoteVerification(InvestigateCase):
    """A quote is source evidence only when the page contains it.

    The model picks the sentence, so an unverified quote would let an invented one
    be recorded as though the source had stated it - and the gate accepts a licence
    file as evidence from the source. The node keeps the reading either way; only
    the claim to having read it on the page is dropped.
    """

    async def test_a_quote_the_page_does_not_contain_is_not_source_evidence(
        self, clock: FixedClock
    ) -> None:
        paraphrased = LicenseInterpretation(
            license_claim='CC-BY-4.0',
            confidence=0.6,
            quoted_text='The photographer released the images under Creative Commons.',
            reasoning='the page states a Creative Commons attribution licence',
        )
        node, _ = self.build_node(clock, paraphrased)
        state = build_state(build_candidate(license_id=None), build_spec())

        result = await node(state)

        assert [item.kind for item in result['evidence']] == [EvidenceKind.LLM_EXTRACTION]

    async def test_an_empty_quote_is_not_source_evidence(self, clock: FixedClock) -> None:
        # An empty string is a substring of every page, so this has to be rejected
        # on its own rather than by the containment check.
        silent = LicenseInterpretation(
            license_claim=None,
            confidence=0.0,
            quoted_text='',
            reasoning='no rights statement was found',
        )
        node, _ = self.build_node(clock, silent)
        state = build_state(build_candidate(license_id=None), build_spec())

        result = await node(state)

        assert [item.kind for item in result['evidence']] == [EvidenceKind.LLM_EXTRACTION]

    async def test_a_reflowed_quote_still_matches_the_page(self, clock: FixedClock) -> None:
        reflowed = LicenseInterpretation(
            license_claim='CC-BY-4.0',
            confidence=0.6,
            quoted_text='All images on this page\n    are licensed under CC BY 4.0.',
            reasoning='the page states a Creative Commons attribution licence',
        )
        node, _ = self.build_node(clock, reflowed)
        state = build_state(build_candidate(license_id=None), build_spec())

        result = await node(state)

        quote = result['evidence'][0]
        assert quote.kind is EvidenceKind.LICENSE_FILE
        assert quote.excerpt == PAGE_TEXT
