from pathlib import Path

from fastapi.testclient import TestClient

from app import app


STATIC_DIRECTORY = Path("static")


def test_search_ui_files_exist():
    assert (
        STATIC_DIRECTORY / "index.html"
    ).exists()

    assert (
        STATIC_DIRECTORY / "styles.css"
    ).exists()

    assert (
        STATIC_DIRECTORY / "app.js"
    ).exists()


def test_root_returns_search_interface():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers[
        "content-type"
    ]

    assert (
        "Research CAISO and energy markets"
        in response.text
    )

    assert 'id="search-form"' in response.text
    assert 'id="answer-panel"' in response.text
    assert "/static/styles.css" in response.text
    assert "/static/app.js" in response.text


def test_search_javascript_uses_public_api():
    content = (
        STATIC_DIRECTORY / "app.js"
    ).read_text(encoding="utf-8")

    assert 'fetch("/api/search"' in content
    assert 'fetch("/api/status"' in content
    assert 'fetch("/api/capabilities"' in content
    assert "clarification_options" in content
    assert "payload.sources" in content
    assert "payload.evidence" in content


def test_search_styles_are_responsive():
    content = (
        STATIC_DIRECTORY / "styles.css"
    ).read_text(encoding="utf-8")

    assert "@media (max-width: 680px)" in content
    assert ".search-box" in content
    assert ".answer-panel" in content
    assert ".source-card" in content
