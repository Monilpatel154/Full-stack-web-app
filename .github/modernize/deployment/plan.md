# Render Deployment Plan

## Scope
- Deploy the root Flask application as one Render Web Service.
- Preserve the existing website and admin routes.
- Use Gunicorn as the production WSGI server and bind to Render's `$PORT`.
- Keep secrets and database configuration in Render environment variables.

## Files to create or update
- `render.yaml`: Render Blueprint configuration with build and start commands.
- `requirements.txt`: Ensure the production WSGI server is available.
- `wsgi_pythonanywhere.py` or the existing Flask entry point: Confirm the WSGI import path.
- `.gitignore`: Prevent local databases, uploads, mail outbox contents, and secrets from being deployed accidentally.
- `DEPLOYMENT.md`: Document Render setup, required environment variables, and persistent-storage considerations.

## Deployment type
Render Web Service from the connected GitHub repository, using the Python runtime.

## Required runtime configuration
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --bind 0.0.0.0:$PORT wsgi_pythonanywhere:application`
- Configure application secrets and database URL in Render, never in source control.
- Use a managed PostgreSQL database for production persistence; local SQLite and filesystem uploads are not durable across Render redeploys unless an appropriate persistent disk or external storage is configured.

## Validation steps
1. Inspect the Flask entry point and dependency manifest.
2. Install dependencies in the local virtual environment.
3. Import the WSGI application and start Gunicorn on a local port.
4. Request the public site and an application health/page route.
5. Validate the Render Blueprint syntax and review the final diff.

## Out of scope
- Changes to business logic or page content.
- Azure infrastructure, Kubernetes manifests, or service migrations.
- Moving uploaded files to object storage unless required by an observed deployment blocker.