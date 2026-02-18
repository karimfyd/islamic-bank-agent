import pytest
from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client

def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200

def test_index_contains_generate_button(client):
    response = client.get("/")
    assert b"Generate Strategy Proposal" in response.data

def test_index_contains_default_context(client):
    response = client.get("/")
    assert b"Al Noor Islamic Bank" in response.data
