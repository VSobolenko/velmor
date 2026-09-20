from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from packages.services.src.saleor.client import (
    SaleorCategory,
    SaleorClient,
    SaleorOrder,
    SaleorProduct,
    SaleorVariant,
)
from packages.services.src.saleor.errors import (
    SaleorAuthError,
    SaleorGraphQLError,
    SaleorTransportError,
)

API_URL = 'https://saleor.test'
TOKEN = 'saleor-app-token-7f3a'
PRODUCT_TYPE_ID = 'UHJvZHVjdFR5cGU6MQ=='
PRODUCT_ID = 'UHJvZHVjdDox'
VARIANT_ID = 'UHJvZHVjdFZhcmlhbnQ6MQ=='
CATEGORY_ID = 'Q2F0ZWdvcnk6MQ=='
ORDER_ID = 'T3JkZXI6MQ=='
VARIANT_IDS = ('UHJvZHVjdFZhcmlhbnQ6MQ==', 'UHJvZHVjdFZhcmlhbnQ6Mg==')

PRODUCT_TYPE_FOUND = {
    'data': {
        'productTypes': {
            'edges': [{'node': {'id': PRODUCT_TYPE_ID, 'name': 'Digital goods'}}],
        }
    }
}
PRODUCT_TYPE_ABSENT = {'data': {'productTypes': {'edges': []}}}
PRODUCT_TYPE_CREATED = {'data': {'productTypeCreate': {'productType': {'id': PRODUCT_TYPE_ID}}}}
PRODUCT_CREATED = {'data': {'productCreate': {'product': {'id': PRODUCT_ID}}}}
PRODUCT_UPDATED = {'data': {'productUpdate': {'product': {'id': PRODUCT_ID}}}}
VARIANT_CREATED = {'data': {'productVariantCreate': {'productVariant': {'id': VARIANT_ID}}}}
VARIANT_UPDATED = {'data': {'productVariantUpdate': {'productVariant': {'id': VARIANT_ID}}}}
CATEGORY_CREATED = {'data': {'categoryCreate': {'category': {'id': CATEGORY_ID}}}}
CATEGORY_DELETED = {'data': {'categoryDelete': {'category': {'id': CATEGORY_ID}}}}
ORDER_READ = {
    'data': {
        'order': {
            'id': ORDER_ID,
            'number': '17',
            'status': 'UNFULFILLED',
            'total': {'gross': {'amount': '42.50', 'currency': 'USD'}},
            'lines': [{'variant': {'id': variant_id}} for variant_id in VARIANT_IDS],
        }
    }
}


class StubTransport:
    """An httpx transport that records every request and answers with one payload."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self._payload = payload
        self._status_code = status_code

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self._status_code, json=self._payload)


class ProductTypeTransport:
    """Answer the product type lookup with nothing and the creation with an id."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        query = json.loads(request.content)['query']
        if 'productTypeCreate' in query:
            return httpx.Response(200, json=PRODUCT_TYPE_CREATED)
        return httpx.Response(200, json=PRODUCT_TYPE_ABSENT)


class RaisingTransport:
    """An httpx transport that fails the way a dead connection does."""

    def __init__(self, failure: Exception) -> None:
        self.requests: list[httpx.Request] = []
        self._failure = failure

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        raise self._failure


def build_client(http: httpx.AsyncClient) -> SaleorClient:
    return SaleorClient(http, API_URL, SecretStr(TOKEN))


def request_body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def assert_graphql_request(request: httpx.Request, operation_field: str) -> dict:
    """Every operation must reach the one endpoint, authorised, with its own query."""
    assert request.method == 'POST'
    assert str(request.url) == f'{API_URL}/graphql/'
    assert request.headers['Authorization'] == f'Bearer {TOKEN}'
    body = request_body(request)
    assert operation_field in body['query']
    return body


class TestTheEightOperations:
    """One case per operation, asserting the value and the request that produced it."""

    async def test_ensure_product_type_reuses_a_type_that_already_exists(self) -> None:
        stub = StubTransport(PRODUCT_TYPE_FOUND)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            product_type_id = await build_client(http).ensure_product_type('Digital goods')

        assert product_type_id == PRODUCT_TYPE_ID
        assert len(stub.requests) == 1
        body = assert_graphql_request(stub.requests[0], 'productTypes')
        assert body['variables'] == {'name': 'Digital goods'}

    async def test_ensure_product_type_creates_a_type_that_is_absent(self) -> None:
        stub = ProductTypeTransport()

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            product_type_id = await build_client(http).ensure_product_type('Digital goods')

        assert product_type_id == PRODUCT_TYPE_ID
        assert len(stub.requests) == 2
        lookup, creation = stub.requests
        assert assert_graphql_request(lookup, 'productTypes')['variables'] == {
            'name': 'Digital goods'
        }
        assert assert_graphql_request(creation, 'productTypeCreate')['variables'] == {
            'input': {'name': 'Digital goods'}
        }

    async def test_create_product_returns_the_product_id(self) -> None:
        stub = StubTransport(PRODUCT_CREATED)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            product = await build_client(http).create_product(
                'Lantern photograph', 'lantern-photograph', PRODUCT_TYPE_ID, None
            )

        assert product == SaleorProduct(product_id=PRODUCT_ID)
        body = assert_graphql_request(stub.requests[0], 'productCreate')
        assert body['variables'] == {
            'input': {
                'name': 'Lantern photograph',
                'slug': 'lantern-photograph',
                'productType': PRODUCT_TYPE_ID,
                'category': None,
            }
        }

    async def test_update_product_returns_the_product_id(self) -> None:
        stub = StubTransport(PRODUCT_UPDATED)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            product = await build_client(http).update_product(
                PRODUCT_ID, 'Lantern photograph', 'lantern-photograph', CATEGORY_ID
            )

        assert product == SaleorProduct(product_id=PRODUCT_ID)
        body = assert_graphql_request(stub.requests[0], 'productUpdate')
        assert body['variables'] == {
            'id': PRODUCT_ID,
            'input': {
                'name': 'Lantern photograph',
                'slug': 'lantern-photograph',
                'category': CATEGORY_ID,
            },
        }

    async def test_create_variant_returns_the_variant_id(self) -> None:
        stub = StubTransport(VARIANT_CREATED)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            variant = await build_client(http).create_variant(PRODUCT_ID, 'LANTERN-1')

        assert variant == SaleorVariant(variant_id=VARIANT_ID)
        body = assert_graphql_request(stub.requests[0], 'productVariantCreate')
        assert body['variables'] == {'input': {'product': PRODUCT_ID, 'sku': 'LANTERN-1'}}

    async def test_update_variant_returns_the_variant_id(self) -> None:
        stub = StubTransport(VARIANT_UPDATED)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            variant = await build_client(http).update_variant(VARIANT_ID, 'LANTERN-2')

        assert variant == SaleorVariant(variant_id=VARIANT_ID)
        body = assert_graphql_request(stub.requests[0], 'productVariantUpdate')
        assert body['variables'] == {'id': VARIANT_ID, 'input': {'sku': 'LANTERN-2'}}

    async def test_create_category_returns_the_category_id(self) -> None:
        stub = StubTransport(CATEGORY_CREATED)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            category = await build_client(http).create_category('Photographs', 'photographs')

        assert category == SaleorCategory(category_id=CATEGORY_ID)
        body = assert_graphql_request(stub.requests[0], 'categoryCreate')
        assert body['variables'] == {'input': {'name': 'Photographs', 'slug': 'photographs'}}

    async def test_delete_category_returns_nothing(self) -> None:
        stub = StubTransport(CATEGORY_DELETED)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            deleted = await build_client(http).delete_category(CATEGORY_ID)

        assert deleted is None
        body = assert_graphql_request(stub.requests[0], 'categoryDelete')
        assert body['variables'] == {'id': CATEGORY_ID}

    async def test_read_order_returns_its_state_and_lines(self) -> None:
        stub = StubTransport(ORDER_READ)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            order = await build_client(http).read_order(ORDER_ID)

        assert order == SaleorOrder(
            order_id=ORDER_ID,
            number='17',
            status='UNFULFILLED',
            currency='USD',
            total=Decimal('42.50'),
            variant_ids=VARIANT_IDS,
        )
        assert_graphql_request(stub.requests[0], 'order')

    async def test_read_order_sends_the_order_id_it_was_given(self) -> None:
        stub = StubTransport(ORDER_READ)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            await build_client(http).read_order(ORDER_ID)

        assert request_body(stub.requests[0])['variables'] == {'id': ORDER_ID}


class TestTransportFailure:
    async def test_a_transport_failure_is_translated_with_the_cause_attached(self) -> None:
        failure = httpx.ConnectError('connection refused')
        stub = RaisingTransport(failure)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(SaleorTransportError) as raised:
                await build_client(http).read_order(ORDER_ID)

        assert 'read_order' in str(raised.value)
        assert raised.value.__cause__ is failure
        assert isinstance(raised.value.__cause__, httpx.ConnectError)

    async def test_the_transport_failure_is_not_an_httpx_error_at_the_boundary(self) -> None:
        stub = RaisingTransport(httpx.ReadTimeout('the read timed out'))

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(SaleorTransportError):
                await build_client(http).create_category('Photographs', 'photographs')


class TestAuthFailure:
    @pytest.mark.parametrize('status_code', [401, 403])
    async def test_a_refused_credential_is_an_auth_error(self, status_code: int) -> None:
        stub = StubTransport({}, status_code=status_code)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(SaleorAuthError) as raised:
                await build_client(http).create_category('Photographs', 'photographs')

        assert str(status_code) in str(raised.value)


class TestServerFailure:
    async def test_a_server_error_is_not_mistaken_for_a_refused_credential(self) -> None:
        stub = StubTransport({}, status_code=500)

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(SaleorTransportError) as raised:
                await build_client(http).create_category('Photographs', 'photographs')

        assert '500' in str(raised.value)


class TestGraphQLErrors:
    async def test_saleors_own_message_survives_into_the_error(self) -> None:
        stub = StubTransport({'errors': [{'message': 'Product type already exists.'}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(SaleorGraphQLError) as raised:
                await build_client(http).create_product(
                    'Lantern photograph', 'lantern-photograph', PRODUCT_TYPE_ID, None
                )

        assert 'Product type already exists.' in str(raised.value)

    async def test_an_answer_with_neither_data_nor_errors_is_reported(self) -> None:
        stub = StubTransport({})

        async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
            with pytest.raises(SaleorGraphQLError) as raised:
                await build_client(http).create_category('Photographs', 'photographs')

        assert 'neither data nor errors' in str(raised.value)


class TestTokenHandling:
    async def test_the_revealed_token_is_not_reachable_from_the_client(self) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(StubTransport({}))) as http:
            client = build_client(http)

            assert TOKEN not in repr(client)
            assert TOKEN not in str(client)
            for name, value in vars(client).items():
                assert TOKEN not in repr(value), name
                assert TOKEN not in str(value), name
