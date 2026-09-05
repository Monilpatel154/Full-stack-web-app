# Render Deployment Summary

## Artifacts generated
- `render.yaml` for a Render Python Web Service.
- Gunicorn production dependency in `requirements.txt`.
- `/healthz` readiness endpoint.
- Render-specific deployment instructions in `DEPLOYMENT.md`.

## Key configuration
- Render installs dependencies with `pip install -r requirements.txt`.
- Render starts `app:app` with Gunicorn on `$PORT`.
- A generated `SECRET_KEY` is used instead of relying on ephemeral disk.
- `DATABASE_URL`, admin credentials, and SMTP credentials are supplied through Render environment variables.

## Verification
- Dependencies installed successfully.
- Python compilation and application import passed.
- Public home page, admin login page, and health endpoint returned HTTP 200.
- Gunicorn command was checked against the production WSGI target; it cannot run on Windows locally because Gunicorn requires Unix `fcntl`, but Render runs Linux.

## Required Render setup
- Connect the GitHub repository through **New > Blueprint** and select the repository root.
- Create or attach a Render PostgreSQL database and set its Internal Database URL as `DATABASE_URL`.
- Set `ADMIN_PASSWORD` and `ADMIN_EMAIL`; configure SMTP variables for email features.
- Use a persistent disk or external object storage for uploaded documents and quote attachments if those files must survive deploys.