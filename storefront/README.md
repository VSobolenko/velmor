# Proofbasket storefront

Next.js (App Router) presentation layer for Velmor. Holds no rights logic and no
payment secrets. Talks only to the Python commerce API.

## Setup

```bash
cp .env.example .env.local
npm ci
npm run dev
```

Open http://localhost:3000. The API must be reachable at
`NEXT_PUBLIC_VELMOR_API_URL` (default `http://127.0.0.1:8080`).

## Environment

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_VELMOR_API_URL` | Base URL of the FastAPI commerce API |

It is a public client value, not a secret. Do not put Stripe, bePaid, Saleor, or
operator keys in this app.

Buyer identity is the API's own session cookie. A browser request goes to the shop's
own origin at `/api`, so the cookie travels first-party and no `X-Buyer-Id` header
exists; a request made on the Next server carries no cookie of its own, so
`lib/api/server.ts` reads the caller's with `cookies()` and forwards it. The cart is
keyed `velmor.cart` for every visitor, so signing in and signing out keep the lines
already added.

## Scripts

- `npm run dev` — local development
- `npm run build` — production build
- `npm start` — serve the production build
