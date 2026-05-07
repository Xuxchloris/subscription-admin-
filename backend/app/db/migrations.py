from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_job_metadata_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "job_metadata" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("job_metadata")}
    columns = {
        "content_id": "VARCHAR(120) DEFAULT ''",
        "content_title": "VARCHAR(255) DEFAULT ''",
        "delivery_label": "VARCHAR(255) DEFAULT ''",
        "content_template_id": "INTEGER",
        "content_template_name": "VARCHAR(255) DEFAULT ''",
        "duration_days": "INTEGER",
        "starts_at": "DATETIME",
        "expires_at": "DATETIME",
        "expired_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE job_metadata ADD COLUMN {name} {definition}"))
