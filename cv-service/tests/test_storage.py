import uuid

import pytest

from app import storage


def test_image_dir_accepts_a_real_uuid4(tmp_path, monkeypatch):
    """The only shape image_id ever legitimately takes (server-minted in
    analyze.analyze) must keep working unchanged.
    """
    from app import config
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    image_id = str(uuid.uuid4())
    d = storage.image_dir(image_id)

    assert d.exists()
    assert d.is_relative_to(tmp_path.resolve())


@pytest.mark.parametrize(
    "hostile_id",
    [
        "../../etc/passwd",
        "../evil",
        "a/b",
        "a\\b",
        "..",
        "/etc/passwd",
        "",
    ],
)
def test_image_dir_rejects_path_traversal(hostile_id, tmp_path, monkeypatch):
    """CodeQL py/path-injection (cache.py:109, storage.py:16): image_id
    round-trips from an unvalidated client request body into a filesystem
    path. Anything that isn't the uuid4 alphabet must be rejected before it
    ever reaches Path construction / mkdir.
    """
    from app import config
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    with pytest.raises(ValueError):
        storage.image_dir(hostile_id)


def test_load_entry_returns_none_for_hostile_image_id(tmp_path, monkeypatch):
    """The API-facing path (cache.load_entry) must turn the ValueError into a
    clean cache-miss (-> 404 at the endpoint), never a 500.
    """
    from app import cache, config
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    assert cache.load_entry("../../etc/passwd") is None
