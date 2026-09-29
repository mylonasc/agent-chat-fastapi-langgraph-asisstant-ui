# Legacy Minimal Frontend

This frontend is used only by `docker-compose.minimal.yml`. It connects to the
package-backed compatibility server at `http://localhost:8011/assistant` and is
separate from the unified static UI that ships in the portable wheel.

Run the complete split stack from the repository root:

```bash
docker-compose -f docker-compose.minimal.yml up --build
```

The UI is available at <http://localhost:3000>. For standalone frontend work:

```bash
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8011/assistant pnpm dev
```

The backend implements the Assistant transport streaming protocol; credentials
belong in the backend environment, not in this frontend. See the
[Docker Compose guide](../../../docs/docker-compose.md) for configuration and
the [packaged app guide](../../../docs/packaged-app.md) for the recommended
single-port deployment.
