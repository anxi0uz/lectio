from alembic import command

from tests.support import alembic_config


def test_migrations_match_models_and_roundtrip(
    migrated_database: None,
) -> None:
    config = alembic_config()

    # Fails if the models changed without a matching migration.
    command.check(config)

    command.downgrade(config, "base")
    command.upgrade(config, "head")
