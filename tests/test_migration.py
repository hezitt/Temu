import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def load_initial_migration() -> ModuleType:
    path = Path("alembic/versions/20260915_0001_initial_schema.py")
    spec = importlib.util.spec_from_file_location("initial_schema", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_initial_migration_upgrades_and_downgrades() -> None:
    migration = load_initial_migration()
    engine = create_engine("sqlite://")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        table_names = set(inspect(connection).get_table_names())
        assert "designs" in table_names
        assert "pricing_decisions" in table_names
        assert "financial_transactions" in table_names

        with Operations.context(context):
            migration.downgrade()

        assert inspect(connection).get_table_names() == []
