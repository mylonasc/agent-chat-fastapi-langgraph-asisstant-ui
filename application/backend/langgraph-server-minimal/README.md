
To start the API-only development server, run:

```bash
uv run uvicorn server:app --port 8011
```

To serve a static export of `frontend-minimal` on the same port, set the web
directory before starting the server:

```bash
MINIMAL_WEB_DIR=../../frontend/frontend-minimal/out \
  uv run uvicorn server:app --port 8011
```

`/health`, `/assistant`, `/docs`, and `/openapi.json` are registered before the
root static mount. Existing files under `MINIMAL_WEB_DIR` are served directly;
other browser paths fall back to `index.html` for client-side routing. If the
directory or its `index.html` is missing, the server logs a warning and starts
in API-only mode.
