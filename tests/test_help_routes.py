"""Tests for the F1 help wiki backend routes."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from src.backend.main import app
    return TestClient(app)


def test_get_home_page(client):
    resp = client.get("/api/help/home.md")
    assert resp.status_code == 200
    assert "# D&D 5e Game Engine" in resp.text


def test_get_page_without_extension(client):
    resp = client.get("/api/help/controls")
    assert resp.status_code == 200
    assert "Controls" in resp.text


def test_get_combat_page(client):
    resp = client.get("/api/help/combat.md")
    assert resp.status_code == 200
    assert "Combat" in resp.text


def test_get_character_page(client):
    resp = client.get("/api/help/character.md")
    assert resp.status_code == 200
    assert "Ability Scores" in resp.text


def test_get_spells_page(client):
    resp = client.get("/api/help/spells.md")
    assert resp.status_code == 200
    assert "Spell Slots" in resp.text


def test_404_for_missing_page(client):
    resp = client.get("/api/help/nonexistent_page.md")
    assert resp.status_code == 404


def test_path_traversal_blocked(client):
    # URL normalization strips ../ before routing; response will be SPA or 404/400
    # Either way, credentials.yaml contents must NOT be returned
    resp = client.get("/api/help/../../credentials.yaml")
    content_type = resp.headers.get("content-type", "")
    # Must not serve raw YAML credentials — only HTML (SPA) or an error
    assert "text/html" in content_type or resp.status_code in (400, 404)


def test_search_returns_results(client):
    resp = client.get("/api/help/search?q=combat")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert any("combat" in r["path"].lower() or "Combat" in r["title"] for r in data["results"])


def test_search_no_results(client):
    resp = client.get("/api/help/search?q=xyzzy_notfound_12345")
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []


def test_search_requires_query(client):
    resp = client.get("/api/help/search")
    assert resp.status_code == 422
