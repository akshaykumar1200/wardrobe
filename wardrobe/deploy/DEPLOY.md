# Build and deploy

From the `wardrobe/` directory, build the image locally with:

```sh
docker build -f deploy/Dockerfile .
```

The build context is the repository root (`wardrobe/`), which provides the backend, frontend build, and deployment files to Docker.

Set these environment variables on whichever container host you choose:

- `SUPABASE_DB_URL`
- `SESSION_SECRET`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `CLOUD_MODE=true`
- `PUBLIC_ORIGIN`

Enter these values in the host's own secrets or environment settings. Never commit them to a file in the repository.

`PUBLIC_ORIGIN` must be the public HTTPS address the browser will use to reach the app. Password-reset links and CORS are both built from this value.
