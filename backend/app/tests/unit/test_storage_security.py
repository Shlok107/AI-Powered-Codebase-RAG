import uuid

import pytest

from app.services.storage import RepositoryStorage


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("path", ["../outside.py", "..\\outside.py", "C:\\outside.py", "\\\\server\\share\\file.py", "/etc/passwd"])
def test_repository_storage_rejects_absolute_and_traversal_paths(tmp_path, path) -> None:
    storage = RepositoryStorage(str(tmp_path / "repositories"))

    with pytest.raises(ValueError, match="relative|escapes"):
        storage.get_file_path(uuid.uuid4(), path)


def test_repository_storage_resolves_valid_paths_inside_repository(tmp_path) -> None:
    storage = RepositoryStorage(str(tmp_path / "repositories"))
    repository_id = uuid.uuid4()
    source = storage.get_repo_source_path(repository_id)
    source.mkdir(parents=True)
    expected = source / "src" / "main.py"

    assert storage.get_file_path(repository_id, "src/main.py") == expected.resolve()
