import io
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.chain.steps import AiPipelineResponse
from app.models.models import UpcomingGameResponse
from app.services.data_service import NoDatabaseDataError

client = TestClient(app)
app.state.uploaded_df = None


def test_health():
    """GET /health ska returnera 200 med status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stats_without_data():
    """GET /data/stats utan uppladdat dataset ska returnera 404."""
    app.state.uploaded_df = None
    with patch("app.api.data.get_stats", side_effect=NoDatabaseDataError):
        response = client.get("/data/stats")
        assert response.status_code == 404


def test_upload_invalid_extension():
    """POST /data/upload med fel filtyp ska returnera 400."""
    file = io.BytesIO(b"some content")
    response = client.post(
        "/data/upload",
        files={"file": ("data.txt", file, "text/plain")},
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_upload_valid_csv():
    """POST /data/upload med giltig CSV ska returnera 200 med metadata."""
    csv_content = b"city,temp_c,precip\nMalmo,8.3,50\nStockholm,6.5,40\n"
    file = io.BytesIO(csv_content)
    response = client.post(
        "/data/upload",
        files={"file": ("data.csv", file, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rows"] == 2
    assert "city" in data["columns"]
    assert "temp_c" in data["columns"]


def test_ai_ask_mocked():
    """POST /ai/ask med mockad pipeline ska returnera korrekt svar."""
    mock_response = AiPipelineResponse(
        question="Vilken hast ar bast?",
        intent="horse_stats",
        answer="Elitlansen ar bast.",
        model="HuggingFaceTB/SmolLM-135M-Instruct",
    )

    with patch("app.api.ai.db.count_starters", return_value=100), \
         patch("app.api.ai.ask_question", return_value=mock_response):
        response = client.post(
            "/ai/ask",
            json={"question": "Vilken hast ar bast?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Vilken hast ar bast?"
    assert data["answer"] == "Elitlansen ar bast."
    assert data["model"] == "HuggingFaceTB/SmolLM-135M-Instruct"


def test_upcoming_game_not_found():
    """POST /data/upcoming med datum utan spel ska ge 404."""
    with patch("app.services.data_service.atg.fetch_upcoming_starts", return_value=[]):
        response = client.post(
            "/data/upcoming",
            json={"game_type": "V86", "date": "2020-01-01"},
        )
    assert response.status_code == 404


def test_upcoming_game_mocked():
    """POST /data/upcoming med mockad ATG-data ska returnera analys."""
    mock_entries = [
        {
            "race_number": 1,
            "track": "Solvalla",
            "distance_m": 2140.0,
            "post_position": 3,
            "horse_id": 100,
            "horse_name": "Testhast",
            "horse_age": 5,
            "driver_id": 200,
            "driver_name": "Test Kansen",
        },
    ]
    mock_horse_stats = {100: {"starts": 10, "wins": 3, "win_pct": 30.0, "avg_odds": 5.0, "avg_position": 3.2}}
    mock_driver_stats = {200: {"driver_name": "Test Kansen", "starts": 50, "wins": 10, "win_pct": 20.0}}

    with patch("app.services.data_service.atg.fetch_upcoming_starts", return_value=mock_entries), \
         patch("app.services.data_service.db.load_horse_stats", return_value=mock_horse_stats), \
         patch("app.services.data_service.db.load_driver_stats", return_value=mock_driver_stats):
        response = client.post(
            "/data/upcoming",
            json={"game_type": "V86", "date": "2026-06-10"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["game_type"] == "V86"
    assert data["date"] == "2026-06-10"
    assert len(data["races"]) == 1
    assert data["races"][0]["starters"][0]["horse_name"] == "Testhast"
    assert data["horses_with_history"] == 1
