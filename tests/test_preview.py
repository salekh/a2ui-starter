"""FastAPI preview server smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.preview.server import app


def test_demo_endpoint_returns_a2ui_stream() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/demo")
    assert resp.status_code == 200
    stream = resp.json()
    assert isinstance(stream, list)
    assert stream, "expected at least one A2UI message"
    for msg in stream:
        assert isinstance(msg, dict)
        assert "version" in msg
    # First message must be a createSurface
    assert "createSurface" in stream[0]


def test_root_redirects_to_preview() -> None:
    with TestClient(app) as client:
        resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/preview"


def test_healthz() -> None:
    with TestClient(app) as client:
        resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_widget_endpoint_isolated_stream() -> None:
    with TestClient(app) as client:
        ok = client.get("/api/widget/data_table")
        missing = client.get("/api/widget/no_such_widget")
    assert ok.status_code == 200
    assert missing.status_code == 404
    stream = ok.json()
    assert isinstance(stream, list) and stream
    assert "createSurface" in stream[0]


def test_maps_embed_without_api_key() -> None:
    """Without GOOGLE_MAPS_API_KEY, /maps/embed returns a 500 error."""
    import os

    # Ensure key is not set
    old = os.environ.pop("GOOGLE_MAPS_API_KEY", None)
    try:
        with TestClient(app) as client:
            resp = client.get(
                "/maps/embed?mode=place&q=Google+Playa+Vista",
                follow_redirects=False,
            )
        assert resp.status_code == 500
        assert "GOOGLE_MAPS_API_KEY" in resp.json()["error"]
    finally:
        if old is not None:
            os.environ["GOOGLE_MAPS_API_KEY"] = old


def test_maps_embed_with_api_key() -> None:
    """With GOOGLE_MAPS_API_KEY set, /maps/embed redirects to Google."""
    import os

    os.environ["GOOGLE_MAPS_API_KEY"] = "test-key-12345"
    try:
        with TestClient(app) as client:
            resp = client.get(
                "/maps/embed?mode=place&q=Google+Playa+Vista",
                follow_redirects=False,
            )
        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "google.com/maps/embed/v1/place" in location
        assert "key=test-key-12345" in location
        assert "Google+Playa+Vista" in location or "Google%20Playa%20Vista" in location
    finally:
        os.environ.pop("GOOGLE_MAPS_API_KEY", None)


def test_maps_embed_directions() -> None:
    """Directions mode passes origin and destination."""
    import os

    os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"
    try:
        with TestClient(app) as client:
            resp = client.get(
                "/maps/embed?mode=directions&origin=NYC&destination=Boston",
                follow_redirects=False,
            )
        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "mode=directions" not in location  # mode is in the path, not query
        assert "directions" in location
        assert "origin=NYC" in location
        assert "destination=Boston" in location
    finally:
        os.environ.pop("GOOGLE_MAPS_API_KEY", None)

