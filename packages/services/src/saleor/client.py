from __future__ import annotations

from decimal import Decimal
from typing import Generic, TypeVar

import httpx
from pydantic import BaseModel, SecretStr

from packages.services.src.saleor.errors import (
    SaleorAuthError,
    SaleorGraphQLError,
    SaleorTransportError,
)


class GraphQLError(BaseModel):
    """One entry of a GraphQL ``errors`` array."""

    message: str


class SaleorNode(BaseModel):
    """A node read only for its identity."""

    id: str


DataT = TypeVar('DataT')


class GraphQLEnvelope(BaseModel, Generic[DataT]):
    """One GraphQL answer over the operation's own ``data`` shape.

    Saleor answers HTTP 200 whether it succeeded or refused, so the outcome is
    stated in the payload and nowhere else. ``errors`` is a tuple because it is
    read, never rearranged, and ``data`` is nullable only so that an answer
    carrying neither can be recognised rather than coerced into a value.
    """

    data: DataT | None = None
    errors: tuple[GraphQLError, ...] = ()


class ProductTypeNode(BaseModel):
    """A product type as the lookup returns it."""

    id: str
    name: str


class ProductTypeEdge(BaseModel):
    node: ProductTypeNode


class ProductTypeConnection(BaseModel):
    edges: tuple[ProductTypeEdge, ...]


class ProductTypesData(BaseModel):
    productTypes: ProductTypeConnection


class ProductTypeCreatePayload(BaseModel):
    productType: SaleorNode


class ProductTypeCreateData(BaseModel):
    productTypeCreate: ProductTypeCreatePayload


class ProductPayload(BaseModel):
    product: SaleorNode


class ProductCreateData(BaseModel):
    productCreate: ProductPayload


class ProductUpdateData(BaseModel):
    productUpdate: ProductPayload


class VariantPayload(BaseModel):
    productVariant: SaleorNode


class ProductVariantCreateData(BaseModel):
    productVariantCreate: VariantPayload


class ProductVariantUpdateData(BaseModel):
    productVariantUpdate: VariantPayload


class CategoryPayload(BaseModel):
    category: SaleorNode


class CategoryCreateData(BaseModel):
    categoryCreate: CategoryPayload


class CategoryDeleteData(BaseModel):
    categoryDelete: CategoryPayload


class Money(BaseModel):
    amount: Decimal
    currency: str


class TaxedMoney(BaseModel):
    gross: Money


class OrderLine(BaseModel):
    variant: SaleorNode


class OrderNode(BaseModel):
    id: str
    number: str
    status: str
    total: TaxedMoney
    lines: tuple[OrderLine, ...]


class OrderData(BaseModel):
    order: OrderNode


class SaleorProduct(BaseModel):
    """One Saleor product, identified by its id."""

    model_config = {'frozen': True}

    product_id: str


class SaleorVariant(BaseModel):
    """One Saleor product variant, identified by its id."""

    model_config = {'frozen': True}

    variant_id: str


class SaleorCategory(BaseModel):
    """One Saleor category, identified by its id."""

    model_config = {'frozen': True}

    category_id: str


class SaleorOrder(BaseModel):
    """The parts of an order a caller needs to identify, state and price it."""

    model_config = {'frozen': True}

    order_id: str
    number: str
    status: str
    currency: str
    total: Decimal
    variant_ids: tuple[str, ...]


class SaleorClient:
    """The one boundary through which Velmor talks to Saleor.

    A caller receives a typed result or one of the three typed errors; it never
    sees a GraphQL envelope, and no other module constructs a Saleor request.
    The client does exactly one thing: it performs an operation it was given and
    returns that operation's result. It performs no retries, keeps no cache,
    applies no rate limit, and holds no business rule. It knows nothing of a
    ``GateDecision``, a catalogue entry, an entitlement or a publication, and it
    never decides whether a product, a variant or a category should exist. Those
    decisions belong to the publication bridge, the rights engine and the gate;
    this client only carries out the operation it was handed.
    """

    GRAPHQL_PATH = '/graphql/'
    AUTH_FAILURE_STATUSES: frozenset[int] = frozenset({401, 403})
    HTTP_ERROR_FLOOR = 400

    PRODUCT_TYPES_BY_NAME_QUERY = """
        query ProductTypesByName($name: String!) {
          productTypes(first: 100, filter: {search: $name}) {
            edges {
              node {
                id
                name
              }
            }
          }
        }
    """

    PRODUCT_TYPE_CREATE_MUTATION = """
        mutation CreateProductType($input: ProductTypeInput!) {
          productTypeCreate(input: $input) {
            productType {
              id
            }
          }
        }
    """

    PRODUCT_CREATE_MUTATION = """
        mutation CreateProduct($input: ProductCreateInput!) {
          productCreate(input: $input) {
            product {
              id
            }
          }
        }
    """

    PRODUCT_UPDATE_MUTATION = """
        mutation UpdateProduct($id: ID!, $input: ProductInput!) {
          productUpdate(id: $id, input: $input) {
            product {
              id
            }
          }
        }
    """

    PRODUCT_VARIANT_CREATE_MUTATION = """
        mutation CreateVariant($input: ProductVariantCreateInput!) {
          productVariantCreate(input: $input) {
            productVariant {
              id
            }
          }
        }
    """

    PRODUCT_VARIANT_UPDATE_MUTATION = """
        mutation UpdateVariant($id: ID!, $input: ProductVariantInput!) {
          productVariantUpdate(id: $id, input: $input) {
            productVariant {
              id
            }
          }
        }
    """

    CATEGORY_CREATE_MUTATION = """
        mutation CreateCategory($input: CategoryInput!) {
          categoryCreate(input: $input) {
            category {
              id
            }
          }
        }
    """

    CATEGORY_DELETE_MUTATION = """
        mutation DeleteCategory($id: ID!) {
          categoryDelete(id: $id) {
            category {
              id
            }
          }
        }
    """

    ORDER_QUERY = """
        query ReadOrder($id: ID!) {
          order(id: $id) {
            id
            number
            status
            total {
              gross {
                amount
                currency
              }
            }
            lines {
              variant {
                id
              }
            }
          }
        }
    """

    def __init__(self, http: httpx.AsyncClient, api_url: str, app_token: SecretStr) -> None:
        self._http = http
        self._api_url = api_url
        self._app_token = app_token

    async def ensure_product_type(self, name: str) -> str:
        """Return the id of the product type called ``name``, creating it if absent.

        Saleor exposes no product type lookup by name, so the lookup searches and
        accepts only an exact name match; a partial match is not a match, which
        is the same rule the licence matrix applies. Creation is attempted only
        after the lookup has answered, so a second call for a type that now
        exists returns that type rather than creating a duplicate.
        """
        known = await self._execute(
            'ensure_product_type',
            self.PRODUCT_TYPES_BY_NAME_QUERY,
            {'name': name},
            ProductTypesData,
        )
        for edge in known.productTypes.edges:
            if edge.node.name == name:
                return edge.node.id
        created = await self._execute(
            'ensure_product_type',
            self.PRODUCT_TYPE_CREATE_MUTATION,
            {'input': {'name': name}},
            ProductTypeCreateData,
        )
        return created.productTypeCreate.productType.id

    async def create_product(
        self, name: str, slug: str, product_type_id: str, category_id: str | None
    ) -> SaleorProduct:
        """Create a product of the given product type, optionally in a category."""
        data = await self._execute(
            'create_product',
            self.PRODUCT_CREATE_MUTATION,
            {
                'input': {
                    'name': name,
                    'slug': slug,
                    'productType': product_type_id,
                    'category': category_id,
                }
            },
            ProductCreateData,
        )
        return SaleorProduct(product_id=data.productCreate.product.id)

    async def update_product(
        self, product_id: str, name: str, slug: str, category_id: str | None
    ) -> SaleorProduct:
        """Update a product's identity and its category."""
        data = await self._execute(
            'update_product',
            self.PRODUCT_UPDATE_MUTATION,
            {
                'id': product_id,
                'input': {'name': name, 'slug': slug, 'category': category_id},
            },
            ProductUpdateData,
        )
        return SaleorProduct(product_id=data.productUpdate.product.id)

    async def create_variant(self, product_id: str, sku: str) -> SaleorVariant:
        """Create a variant of the given product."""
        data = await self._execute(
            'create_variant',
            self.PRODUCT_VARIANT_CREATE_MUTATION,
            {'input': {'product': product_id, 'sku': sku}},
            ProductVariantCreateData,
        )
        return SaleorVariant(variant_id=data.productVariantCreate.productVariant.id)

    async def update_variant(self, variant_id: str, sku: str) -> SaleorVariant:
        """Update a variant's stock keeping unit."""
        data = await self._execute(
            'update_variant',
            self.PRODUCT_VARIANT_UPDATE_MUTATION,
            {'id': variant_id, 'input': {'sku': sku}},
            ProductVariantUpdateData,
        )
        return SaleorVariant(variant_id=data.productVariantUpdate.productVariant.id)

    async def create_category(self, name: str, slug: str) -> SaleorCategory:
        """Create a category."""
        data = await self._execute(
            'create_category',
            self.CATEGORY_CREATE_MUTATION,
            {'input': {'name': name, 'slug': slug}},
            CategoryCreateData,
        )
        return SaleorCategory(category_id=data.categoryCreate.category.id)

    async def delete_category(self, category_id: str) -> None:
        """Delete a category.

        Nothing is returned: whether the operation was accepted is stated by the
        envelope, and a refusal raises like any other refused operation.
        """
        await self._execute(
            'delete_category',
            self.CATEGORY_DELETE_MUTATION,
            {'id': category_id},
            CategoryDeleteData,
        )

    async def read_order(self, order_id: str) -> SaleorOrder:
        """Read an order's identity, state, total and line variants."""
        data = await self._execute(
            'read_order',
            self.ORDER_QUERY,
            {'id': order_id},
            OrderData,
        )
        order = data.order
        return SaleorOrder(
            order_id=order.id,
            number=order.number,
            status=order.status,
            currency=order.total.gross.currency,
            total=order.total.gross.amount,
            variant_ids=tuple(line.variant.id for line in order.lines),
        )

    async def _execute(
        self,
        operation: str,
        query: str,
        variables: dict[str, object],
        data_model: type[DataT],
    ) -> DataT:
        """Send one operation and return its validated ``data``.

        The status code is branched on rather than raised from, so the transport
        failure below stays the only exception this class catches.
        """
        try:
            response = await self._http.post(
                f'{self._api_url}{self.GRAPHQL_PATH}',
                json={'query': query, 'variables': variables},
                headers={'Authorization': f'Bearer {self._app_token.get_secret_value()}'},
            )
        except httpx.RequestError as error:
            # httpx reports a transport-level failure - connection refused, DNS
            # failure, read timeout - by raising a RequestError subclass, which
            # carries no status code, no payload and no GraphQL information.
            # This repository already relies on that contract and names it at
            # packages/auditor/src/nodes/investigate.py:47-49. There is nothing
            # to branch on, and letting it propagate would hand an httpx type
            # across the boundary this class exists to create.
            raise SaleorTransportError(f'{operation} could not reach Saleor: {error}') from error

        if response.status_code in self.AUTH_FAILURE_STATUSES:
            raise SaleorAuthError(f'{operation} was refused by Saleor: HTTP {response.status_code}')
        if response.status_code >= self.HTTP_ERROR_FLOOR:
            raise SaleorTransportError(
                f'{operation} could not be completed: Saleor answered HTTP {response.status_code}'
            )

        envelope = GraphQLEnvelope[data_model].model_validate(response.json())
        if envelope.errors:
            raise SaleorGraphQLError(
                f'{operation} was refused by Saleor: {self._messages(envelope.errors)}'
            )
        if envelope.data is None:
            raise SaleorGraphQLError(
                f'{operation} could not be read: Saleor answered neither data nor errors'
            )
        return envelope.data

    @staticmethod
    def _messages(errors: tuple[GraphQLError, ...]) -> str:
        return '; '.join(error.message for error in errors)
