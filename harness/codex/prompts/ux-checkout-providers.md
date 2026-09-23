# Make the checkout page offer the payment providers the API advertises

A buyer cannot pay for anything on the running shop. Every attempt ends in
"Ошибка оформления заказа". This change fixes the cause.

## The measured defect

`GET https://velmor-api.78-111-89-46.sslip.io/checkout/providers` returns:

```json
["stripe", "bepaid", "stub"]
```

`POST /checkout/start` with `provider_id: "stripe"` returns `502`:

```json
{"detail": "start_payment was refused by Stripe: HTTP 401"}
```

The deployed API holds a placeholder Stripe key, so Stripe answers 401. In this environment
the API wires a third provider, `stub`, which completes a payment without any live credential,
and `/checkout/providers` exists precisely so a client can learn which providers are available.

`storefront/src/app/[locale]/checkout/page.tsx` ignores that endpoint. It hardcodes the list:

```ts
type ProviderId = "stripe" | "bepaid";

const PROVIDERS: { id: ProviderId; labelKey: keyof Dictionary }[] = [
  { id: "stripe", labelKey: "checkout.providerStripe" },
  { id: "bepaid", labelKey: "checkout.providerBepaid" },
];
```

The buyer is therefore offered only the two providers that cannot work here, and the one that
works is invisible. Offering a payment method that is known to fail is worse than offering none.

## The change

The provider list is the API's contract. Read it, do not restate it.

1. Add to `CommerceApiClient` in `storefront/src/lib/api/client.ts`:

   ```ts
   async listCheckoutProviders(): Promise<string[]>
   ```

   It must call `GET /checkout/providers` and return the ids in the order the API returned
   them. Follow the existing methods in that file; `getCheckoutDisclosure` is the closest one.

2. In `storefront/src/app/[locale]/checkout/page.tsx`, replace the hardcoded `PROVIDERS`
   constant and the `ProviderId` union with the list fetched from the API: one radio per id the
   API returned, in the API's order, and the first one selected by default. The provider id is
   now an arbitrary string, so do not keep a two-value union type.

3. The visible label of a provider comes from the dictionary, keyed by id, and must never be a
   literal in the component and never a raw id shown to a buyer when a key exists:

   - `checkout.providerStripe` and `checkout.providerBepaid` already exist; keep their text.
   - Add `checkout.providerStub` to `storefront/src/lib/i18n/en.json`, `ru.json` and `be.json`.
     The label must tell the truth: this is an environment's test payment that completes without
     a card. English "Demo payment (test)", Russian "Демо-оплата (тест)", Belarusian
     "Дэма-аплата (тэст)". Do not imply a real card is charged.
   - An id the dictionaries do not cover falls back to the id itself. Do not invent a label.

4. Fetch it the way the disclosure is fetched, in the same effect or an equivalent one:
   a client component calling `CommerceApiClient.fromEnv(locale)`. If the request fails, the
   page must still render and must not offer a provider list that was not returned: keep the
   existing error affordance and do not silently fall back to a hardcoded pair.

5. Keep every existing behaviour exactly: the acknowledgement checkbox and its required-message
   path, the `payingRef` in-flight guard, `paymentBlocked`, the disclosure section with its
   loading, failed and incomplete states, the empty-cart state, the step indicator and the
   `#disclosure` anchor.

## Scope

Working directory: the repository root.

You may WRITE only these files:

- `storefront/src/app/[locale]/checkout/page.tsx`
- `storefront/src/lib/api/client.ts`
- `storefront/src/lib/i18n/en.json`
- `storefront/src/lib/i18n/ru.json`
- `storefront/src/lib/i18n/be.json`

You may READ anything under `storefront/src/` and `packages/api/src/app.py`.

You may NOT write any other file. In particular do not touch `cart/`, `account/`,
`SiteHeader.tsx`, `MobileNav.tsx`, `ProductCard.tsx`, `AddToCartButton.tsx`,
`ui/Button.tsx`, `ui/Select.tsx`, or anything under `packages/`, `velmor/`, `.cursor/`,
`harness/`, `scripts/`, `openspec/`.

## Hard rules

- Every buyer-visible string lives in the three dictionaries. A literal in a component is a
  defect. All three locales must carry the same keys.
- Do not choose a language for the buyer and do not read a language from the browser.
- Do not add a dependency. No `TODO`. Do not run git. Nothing that reaches the network.
- Do not change the API. `packages/api` is read-only for you.
- **Do not ask me to confirm a design and do not end with a question.** Implement the change.

## Verification boundary

Run exactly these, in this order, and no others:

```
npm --prefix storefront run check:i18n
npm --prefix storefront run lint
```

Do not retry a failure. If a command fails, stop and report it.

## Reply contract

On success reply with exactly:

```
DONE <comma-separated list of files you changed>
```

On failure reply with exactly:

```
BLOCKED <one-line reason>
```
