# OIMADIS store API

Flask backend for the [MockMSPaint](https://github.com/QuanahB/MockMSPaint) frontend. The shop is OIMADIS (Oh-I-Made-This): handmade tees, shorts, long sleeves, pants, hoodies, underwear, sweaters, and hats, grouped the same way as the Paint toolbox.

The Next app already loads its dashboard from this API when `NEXT_PUBLIC_API_URL` is set. Catalog, cart, checkout, accounts, and the contact form are on the same origin for the pages that are still placeholders.

```
MockMSPaint (localhost:4321)  →  this API (localhost:4000)  →  SQLite
```

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app --debug run --port 4000
```

`python app.py` listens on port 4000 as well. The database file is created at `instance/store.db` and seeded with 10 pieces, 3 collections, and 3 video records.

In MockMSPaint, copy `.env.example` to `.env` and set:

```bash
NEXT_PUBLIC_API_URL=http://localhost:4000
```

Restart `npm run dev`. The dashboard overview and projects pages then read live closet data instead of the bundled sample.

## What the frontend already calls

`src/lib/api.ts` fetches these paths and expects the arrays from `src/lib/types.ts`:

| Method | Path | Used by |
| --- | --- | --- |
| GET | `/projects` | Dashboard and projects. Each collection is a project (`on_track`, `at_risk`, `done`). |
| GET | `/metrics` | Overview cards. Values are strings. |
| GET | `/activity` | Recent orders, contact notes, and the catalog seed. |

Night Shift starts `at_risk` because the wool sweater has two left. Progress is the percent of that drop that has sold.

## Shop endpoints

These match the shop, collections, videos, sign-in, sign-up, and contact screens. The current pages do not call them yet; the request bodies use the same field names as the forms.

| Method | Path | Body |
| --- | --- | --- |
| GET | `/products` | Filters: `category`, `collection`, `search`, `in_stock=true` |
| GET | `/products/<id>` | |
| GET | `/products/slug/<slug>` | |
| GET | `/categories` | Toolbox groups with counts |
| GET | `/collections` | |
| GET | `/collections/<slug>` | Includes that drop's products |
| GET | `/videos` | `url` is null until a clip is hosted |
| GET | `/media/<slug>.svg` | Paint-canvas product image |
| GET | `/cart` | Session cart |
| POST | `/cart/items` | `{ "product_id" or "slug", "quantity"?, "size"? }` |
| PATCH | `/cart/items/<id>` | `{ "quantity" }` — `0` removes the line |
| DELETE | `/cart/items/<id>` | |
| DELETE | `/cart` | |
| POST | `/checkout` | `{ "email", "shipping_name", "shipping_address", "shipping_city", "shipping_postal_code", "shipping_country"? }` |
| GET | `/orders` | Orders this browser, or the signed-in account, can see |
| GET | `/orders/<id>` | Same visibility rule |
| POST | `/auth/sign-up` | `{ "name", "email", "password" }` — password at least 8 characters |
| POST | `/auth/sign-in` | `{ "email", "password" }` |
| POST | `/auth/sign-out` | |
| GET | `/auth/me` | |
| POST | `/contact` | `{ "name", "email", "message" }` |
| GET | `/health` | `{ "status": "ok", "database": "connected" }` |

Prices are JSON numbers in US dollars. Shipping is $8, and free when the subtotal is $120 or more. Checkout reserves stock and marks the order `placed`. There is no card charge; this is the handmade-shop order desk.

Cart and account calls from the browser need `credentials: "include"` so the session cookie sticks. Dashboard fetches from the Next server do not. CORS allows `http://localhost:4321` and `http://127.0.0.1:4321`.

## Tests

```bash
pytest
```

## Production

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

Set `SECRET_KEY`. Set `CORS_ORIGINS` and `FRONTEND_ORIGIN` to the deployed MockMSPaint origin. Set `DATABASE_URL` for Postgres (`postgres://` and `postgresql://` are accepted). For a cookie across two sites, set `SESSION_COOKIE_SAMESITE=None` and `SESSION_COOKIE_SECURE=true`.
