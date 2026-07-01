import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.scheduler import pull_all_sources
from app.routes import get_current_user
from unittest.mock import patch
import json

# Override dependency to avoid 401 Unauthorized
app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)

def test_health_check():
    """Test the /health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "online", "service": "siliconpulse-backend"}

def test_get_signals():
    """Test the /api/signals endpoint to ensure it returns a valid response"""
    response = client.get("/api/signals")
    assert response.status_code == 200
    
    # Should return a list
    data = response.json()
    assert isinstance(data, list)

@patch('app.scheduler.pull_gdelt_signals')
@patch('app.scheduler.ingest_news_stream_sync')
@patch('app.scheduler.pull_hn_signals')
def test_scheduler_trigger(mock_hn, mock_news, mock_gdelt):
    """
    Test the ingestion scheduler logic manually to ensure it won't crash
    when triggered by APScheduler.
    """
    mock_hn.return_value = 5
    mock_news.return_value = {"new_added": 10}
    mock_gdelt.return_value = 3
    
    # Run the function
    try:
        pull_all_sources()
        success = True
    except Exception as e:
        success = False
        print(f"Scheduler update failed: {e}")
        
    assert success == True
    mock_hn.assert_called_once()
    mock_news.assert_called_once()
    mock_gdelt.assert_called_once()
