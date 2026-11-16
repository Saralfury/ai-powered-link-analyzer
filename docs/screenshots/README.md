# Screenshots

The frontend and API were verified running locally at
`http://127.0.0.1:4000/`:

- `GET /` — serves the HTML/CSS/vanilla-JS frontend
- `GET /health` — returns service info JSON
- `POST /link-analysis` — returns all five analysis sections
- `GET /docs` — Swagger UI

Screenshot capture was not possible in this headless environment, but the
frontend was verified end-to-end via browser snapshot: the "Analyse" button
triggers the API, the loading state displays, and all five result sections
render with website-specific content (competitors, search queries, SEO,
services, audience).
