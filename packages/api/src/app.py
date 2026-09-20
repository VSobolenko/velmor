"""The Proofbasket storefront: the goods the publication gate approved.

This module renders; it does not decide. It is handed a ``StorefrontCatalog``,
whose only query is over the gate's own ``publishable`` column, so there is no
code path here that could list a good the gate refused. Every value that came
from a third party - a title, a creator, a URL - is escaped on the way into the
markup, because those strings are written by strangers.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from html import escape

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from packages.services.src.commerce.delivery import DeliveryService
from packages.services.src.commerce.errors import DeliveryRefusedError, GrantRefusedError
from packages.services.src.commerce.grants import DeliveryGrantService
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.entitlement import EntitlementState
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.persistence.contract import EntitlementRepository, StorefrontCatalog

Good = tuple[Candidate, RightsRecord]
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


class StorefrontPage:
    """The catalogue page: one card per published good."""

    TITLE = 'Proofbasket'
    SUBTITLE = 'Goods that passed the Velmor rights gate.'
    EMPTY = (
        'Nothing has passed the gate yet. Run discovery, then verification, and the '
        'goods that are provably sellable appear here.'
    )
    NOTICE = (
        'Read-only catalogue. Payment and checkout are not implemented: this page '
        'records what may be sold, it does not sell it.'
    )
    UNKNOWN_CREATOR = 'Unknown creator'
    NO_LICENCE = 'no licence'

    STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.55;
  color: #14161a;
  background: #f6f7f9;
}
header {
  padding: 2.5rem 1.5rem 1.75rem;
  background: #14161a;
  color: #ffffff;
}
header h1 { margin: 0 0 .35rem; font-size: 1.9rem; letter-spacing: -.02em; }
header p { margin: 0; color: #b9bfc9; }
.count { margin-top: .85rem !important; color: #ffffff !important; font-weight: 600; }
main {
  display: grid;
  gap: 1.25rem;
  grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
  padding: 2rem 1.5rem 3rem;
  max-width: 74rem;
  margin: 0 auto;
}
.card {
  background: #ffffff;
  border: 1px solid #e2e5ea;
  border-radius: .6rem;
  padding: 1.15rem 1.25rem 1.25rem;
  display: flex;
  flex-direction: column;
}
.card h2 { margin: 0 0 .3rem; font-size: 1.05rem; line-height: 1.35; }
.creator { margin: 0 0 .8rem; color: #626a76; font-size: .9rem; }
.badges { margin: 0 0 .9rem; display: flex; flex-wrap: wrap; gap: .4rem; }
.badge {
  display: inline-block;
  padding: .2rem .55rem;
  border-radius: 999px;
  background: #eef1f5;
  color: #2a3038;
  font-size: .78rem;
  font-weight: 600;
}
.verdict { background: #e3f3e8; color: #1d6b37; }
.obligations { margin-top: auto; }
.obligations h3 {
  margin: 0 0 .35rem;
  font-size: .74rem;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: #767d89;
}
.obligations ul { margin: 0; padding-left: 1.1rem; font-size: .87rem; }
.obligations p { margin: 0; font-size: .87rem; color: #626a76; }
.links { margin: 1rem 0 0; font-size: .87rem; }
.links a { color: #1a5fb4; }
.empty {
  grid-column: 1 / -1;
  background: #ffffff;
  border: 1px dashed #c8cdd5;
  border-radius: .6rem;
  padding: 2rem 1.5rem;
  color: #626a76;
}
footer {
  padding: 1.25rem 1.5rem 2.5rem;
  color: #767d89;
  font-size: .84rem;
  text-align: center;
}
"""

    def render(self, goods: tuple[Good, ...], total: int) -> str:
        if goods:
            body = '\n'.join(self._card(candidate, record) for candidate, record in goods)
        else:
            body = f'<p class="empty">{escape(self.EMPTY)}</p>'
        return self._document(body, shown=len(goods), total=total)

    def _document(self, body: str, shown: int, total: int) -> str:
        return (
            '<!DOCTYPE html>'
            '<html lang="en">'
            '<head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(self.TITLE)}</title>'
            f'<style>{self.STYLE}</style>'
            '</head>'
            '<body>'
            '<header>'
            f'<h1>{escape(self.TITLE)}</h1>'
            f'<p>{escape(self.SUBTITLE)}</p>'
            f'<p class="count">{self._count(shown, total)}</p>'
            '</header>'
            f'<main>{body}</main>'
            f'<footer>{escape(self.NOTICE)}</footer>'
            '</body>'
            '</html>'
        )

    def _count(self, shown: int, total: int) -> str:
        if shown == total:
            return escape(f'{total} approved for sale')
        return escape(f'{total} approved for sale, showing the {shown} most recent')

    def _card(self, candidate: Candidate, record: RightsRecord) -> str:
        return (
            '<article class="card">'
            f'<h2>{escape(candidate.title)}</h2>'
            f'<p class="creator">{self._creator(candidate)}</p>'
            f'<p class="badges">{self._badges(record)}</p>'
            f'{self._obligations(record)}'
            f'<p class="links">{self._links(candidate)}</p>'
            '</article>'
        )

    def _creator(self, candidate: Candidate) -> str:
        if candidate.creator is None:
            return escape(self.UNKNOWN_CREATOR)
        return escape(candidate.creator)

    def _badges(self, record: RightsRecord) -> str:
        licence = record.license_id or self.NO_LICENCE
        return (
            f'<span class="badge">{escape(licence)}</span>'
            f'<span class="badge verdict">{escape(record.verdict.value)}</span>'
        )

    def _obligations(self, record: RightsRecord) -> str:
        if record.obligations:
            items = ''.join(f'<li>{escape(item)}</li>' for item in record.obligations)
            content = f'<ul>{items}</ul>'
        else:
            content = '<p>None</p>'
        return f'<div class="obligations"><h3>Obligations</h3>{content}</div>'

    def _links(self, candidate: Candidate) -> str:
        source = f'<a href="{escape(candidate.landing_url, quote=True)}">Source page</a>'
        if candidate.download_url is None:
            return source
        download = (
            f'<a href="{escape(candidate.download_url, quote=True)}">Download</a>'
        )
        return f'{source} &middot; {download}'


class ApiApplication:
    """The HTTP surface of the platform.

    Routes are registered as bound methods rather than decorated module-level
    functions, so the handlers can read the injected catalogue without a global.
    """

    CATALOGUE_LIMIT = 100
    BUYER_HEADER = 'x-buyer-id'

    def __init__(
        self,
        environment: str,
        catalog: StorefrontCatalog,
        grants: DeliveryGrantService,
        delivery: DeliveryService,
        entitlements: EntitlementRepository,
        clock: Callable[[], datetime],
        lifespan: Lifespan | None = None,
    ) -> None:
        self._environment = environment
        self._catalog = catalog
        self._grants = grants
        self._delivery = delivery
        self._entitlements = entitlements
        self._clock = clock
        self._lifespan = lifespan
        self._page = StorefrontPage()

    def build(self) -> FastAPI:
        app = FastAPI(
            title=StorefrontPage.TITLE,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
            lifespan=self._lifespan,
        )
        app.add_api_route('/health', self._health, methods=['GET'])
        app.add_api_route(
            '/', self._storefront, methods=['GET'], response_class=HTMLResponse
        )
        app.add_api_route(
            '/account/goods/{candidate_id}/grant',
            self._issue_grant,
            methods=['POST'],
        )
        app.add_api_route('/downloads/{token}', self._download, methods=['GET'])
        return app

    async def _health(self) -> dict[str, str]:
        return {'status': 'ok', 'environment': self._environment}

    async def _storefront(self) -> HTMLResponse:
        goods = await self._catalog.published(self.CATALOGUE_LIMIT)
        total = await self._catalog.published_count()
        return HTMLResponse(self._page.render(goods, total))

    async def _issue_grant(self, candidate_id: str, request: Request) -> JSONResponse:
        """Issue a short-lived download grant for an entitled buyer.

        Buyer identity is taken from the temporary ``X-Buyer-Id`` header until
        account auth lands in task 5.5; that task must replace this stand-in and
        extend this wiring rather than rewrite the grant routes.
        """
        buyer_id = self._require_buyer_id(request)
        if buyer_id is None:
            return JSONResponse(
                {'detail': 'missing or empty X-Buyer-Id header'},
                status_code=401,
            )
        rows = await self._entitlements.for_buyer_candidate(buyer_id, candidate_id)
        if not any(row.state is EntitlementState.ACTIVE for row in rows):
            return JSONResponse(
                {'detail': 'no active entitlement for this good'},
                status_code=403,
            )
        token, grant = self._grants.issue(buyer_id, candidate_id, self._clock())
        return JSONResponse(
            {
                'token': token,
                'expires_at': self._format_instant(grant.expires_at),
            }
        )

    async def _download(self, token: str, request: Request) -> Response:
        """Serve bytes for a verified grant.

        Buyer identity is taken from the temporary ``X-Buyer-Id`` header until
        account auth lands in task 5.5.
        """
        buyer_id = self._require_buyer_id(request)
        if buyer_id is None:
            return JSONResponse(
                {'detail': 'missing or empty X-Buyer-Id header'},
                status_code=401,
            )
        # GrantRefusedError / DeliveryRefusedError are the documented refusal
        # contracts of the grant and delivery services; mapping them to HTTP is
        # the route's job (task 4.3 R4 / R6).
        try:
            grant = self._grants.verify(token, buyer_id, self._clock())
        except GrantRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        try:
            result = await self._delivery.deliver(buyer_id, grant.candidate_id)
        except DeliveryRefusedError as error:
            return JSONResponse({'detail': str(error)}, status_code=403)
        filename = f'{grant.candidate_id}.bin'
        return Response(
            content=result.payload,
            media_type='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )

    def _require_buyer_id(self, request: Request) -> str | None:
        if self.BUYER_HEADER not in request.headers:
            return None
        buyer_id = request.headers[self.BUYER_HEADER]
        if buyer_id == '':
            return None
        return buyer_id

    @staticmethod
    def _format_instant(instant: datetime) -> str:
        return instant.astimezone(UTC).isoformat().replace('+00:00', 'Z')
