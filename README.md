# fs_flowstate_svc

## Database Migrations

Alembic is used for database schema versioning and migrations in FlowState. It generates migration scripts from your SQLAlchemy models and applies them to the configured database.

- Initialization: The Alembic environment is already set up in this repo; you should see the `migrations/` directory.
- Database URL configuration: Set `DATABASE_URL` in your `.env` file. Configuration is loaded via Pydantic settings (`fs_flowstate_svc.config.Settings`), and Alembic picks it up in `migrations/env.py`, which sets `sqlalchemy.url` from `settings.DATABASE_URL`.

Example `.env` snippet:
```
DATABASE_URL=sqlite:///local.db
```

### Generating new revisions
When you modify SQLAlchemy models, create a new migration script:
```
poetry run alembic revision --autogenerate -m "A descriptive message for your changes"
```
Review the generated script in `migrations/versions/` and adjust if necessary.

### Applying migrations
Apply all pending migrations to the database:
```
poetry run alembic upgrade head
```
Alternatively, you can run:
```
make setup
```
which internally executes `alembic upgrade head`.

### Downgrading migrations
Revert the last applied migration:
```
poetry run alembic downgrade -1
```
Revert all migrations back to the base:
```
poetry run alembic downgrade base
```

### Checking current status
Display the current database revision:
```
poetry run alembic current
```

Notes:
- Ensure your models are imported in `fs_flowstate_svc/models/__init__.py` so `Base.metadata` includes them during autogeneration.
- Do not edit Alembic-generated scripts or env configuration manually unless you know what you are doing.