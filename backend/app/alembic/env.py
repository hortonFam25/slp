from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os, sys

# Add the backend directory to the path so we can import app modules
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(backend_dir)

from app.db.base import Base
from app import models  # noqa

# Load settings with explicit .env path
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

from app.settings import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL from settings (environment variables)
if not config.get_main_option("sqlalchemy.url"):
    db_url = settings.sql_server_connection_string
    if not db_url:
        # Fallback for development
        db_url = "sqlite:///./local.db"
    # set_main_option runs configparser %-interpolation; odbc_connect-style
    # URLs are full of %XX escapes, so % must be doubled or alembic dies with
    # "invalid interpolation syntax".
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, 
        target_metadata=target_metadata, 
        literal_binds=True, 
        dialect_opts={"paramstyle": "named"},
        # Skip column comments for SQL Server compatibility
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Create engine with explicit configuration for SQL Server
    engine_config = config.get_section(config.config_ini_section)
    engine_config["sqlalchemy.poolclass"] = pool.NullPool

    # Entra token auth (no password, no Authentication= keyword): when
    # SLP_DB_ACCESS_TOKEN holds an access token for https://database.windows.net/,
    # hand it to the driver as SQL_COPT_SS_ACCESS_TOKEN (1256). This works on
    # every ODBC Driver 17/18 build, unlike Authentication=ActiveDirectoryAzCli
    # which needs 18.1+. Used by .github/workflows/migrate.yml and the
    # provisioning scripts; a plain connection string keeps working unchanged.
    access_token = os.environ.get("SLP_DB_ACCESS_TOKEN", "").strip()
    if access_token:
        import struct
        from sqlalchemy import create_engine

        token_bytes = access_token.encode("utf-16-le")
        attrs = {1256: struct.pack("<i", len(token_bytes)) + token_bytes}
        connectable = create_engine(
            engine_config["sqlalchemy.url"],
            poolclass=pool.NullPool,
            connect_args={"attrs_before": attrs},
        )
    else:
        connectable = engine_from_config(
            engine_config,
            prefix="sqlalchemy."
        )
    

    with connectable.connect() as connection:
        def process_revision_directives(context, revision, directives):
            """Filter out all comment-related operations"""
            for directive in directives:
                if hasattr(directive, 'upgrade_ops'):
                    # Remove all modify_comment operations
                    directive.upgrade_ops.ops = [
                        op for op in directive.upgrade_ops.ops 
                        if not (hasattr(op, 'op_name') and op.op_name == 'modify_comment')
                    ]
        
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            # SQL Server configuration for stable migrations
            compare_type=True,
            # Skip server default comparison for SQL Server - too many false positives  
            compare_server_default=False,
            # Filter out comment operations completely
            process_revision_directives=process_revision_directives,
            # Enable transaction per migration for better rollback behavior
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
