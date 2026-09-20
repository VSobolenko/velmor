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
| `NEXT_PUBLIC_BUYER_ID` | Temporary stand-in for `X-Buyer-Id` until real auth |

Both are public client values, not secrets. Do not put Stripe, bePaid, Saleor, or
operator keys in this app.

## Scripts

- `npm run dev` — local development
- `npm run build` — production build
- `npm start` — serve the production build
