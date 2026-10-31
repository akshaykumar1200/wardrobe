# Digital Wardrobe container

This image contains the Digital Wardrobe FastAPI service, its built web app, and the SegFormer and BiRefNet vision models. It listens on port **8000**.

Configure the service with these environment variables:

- `SUPABASE_DB_URL`: connection URL for the persistent Postgres database.
- `SESSION_SECRET`: a long, private value used to sign sessions.
- `ADMIN_EMAIL`: email address for the initial administrator account.
- `ADMIN_PASSWORD`: password for the initial administrator account.
- `CLOUD_MODE`: set to `true` when running with container storage that does not survive a restart.
- `PUBLIC_ORIGIN`: the public HTTPS URL used by browsers to reach the app.

The first request after an idle period can be slow because the vision models load when the application is imported.
