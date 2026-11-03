import pytest
from sqlalchemy.pool import NullPool


pytestmark = pytest.mark.unit


def test_test_environment_uses_null_pool_without_incompatible_pool_size_options() -> None:
    from app.db.session import engine

    assert isinstance(engine.sync_engine.pool, NullPool)
