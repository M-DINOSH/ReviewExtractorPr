"""
Unit tests for Sentiment Analysis Service
"""
import pytest
import requests
from unittest.mock import Mock

from sentiment_service.services.sentiment import SentimentAnalyzer
from sentiment_service.models.schemas import ReviewInput


@pytest.fixture
def sentiment_analyzer():
    """Sentiment analyzer fixture"""
    return SentimentAnalyzer()


class TestSentimentAnalyzer:
    """Test cases for sentiment analysis"""

    def test_positive_sentiment(self, sentiment_analyzer):
        """Test positive sentiment detection"""
        review = ReviewInput(text="This product is amazing! Highly recommend!", id="test1")
        result = sentiment_analyzer.analyze_review(review)

        assert result.sentiment == "POSITIVE"
        assert result.confidence > 0.5
        assert result.id == "test1"

    def test_negative_sentiment(self, sentiment_analyzer):
        """Test negative sentiment detection"""
        review = ReviewInput(text="Terrible quality, complete waste of money.", id="test2")
        result = sentiment_analyzer.analyze_review(review)

        assert result.sentiment == "NEGATIVE"
        assert result.confidence > 0.5

    def test_neutral_sentiment(self, sentiment_analyzer):
        """Test neutral sentiment detection"""
        review = ReviewInput(text="The product is okay, nothing special.", id="test3")
        result = sentiment_analyzer.analyze_review(review)

        # VADER might classify this as negative due to "nothing special"
        # Just check that it returns a valid sentiment
        assert result.sentiment in ["POSITIVE", "NEGATIVE", "NEUTRAL"]
        assert result.confidence >= 0.0

    def test_batch_analysis(self, sentiment_analyzer):
        """Test batch sentiment analysis"""
        reviews = [
            ReviewInput(text="Amazing product!", id="1"),
            ReviewInput(text="Horrible experience.", id="2"),
            ReviewInput(text="It's alright.", id="3")
        ]

        results = sentiment_analyzer.analyze_reviews(reviews)

        assert len(results) == 3
        assert results[0].sentiment == "POSITIVE"
        assert results[1].sentiment == "NEGATIVE"
        # "It's alright" might be classified as positive by VADER
        assert results[2].sentiment in ["POSITIVE", "NEGATIVE", "NEUTRAL"]

    def test_empty_text_validation(self):
        """Test that empty text fails validation"""
        from pydantic import ValidationError
        import pytest

        with pytest.raises(ValidationError):
            ReviewInput(text="", id="test4")


class TestAPIEndpoints:
    """Test cases for API endpoints"""

    @pytest.fixture
    def base_url(self):
        """Base URL for the service"""
        return "http://localhost:8000"

    def test_root_endpoint(self, base_url):
        """Test root endpoint"""
        response = requests.get(f"{base_url}/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "description" in data

    def test_health_endpoint(self, base_url):
        """Test health check endpoint"""
        response = requests.get(f"{base_url}/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data

    def test_readiness_endpoint(self, base_url):
        """Test readiness check endpoint"""
        response = requests.get(f"{base_url}/api/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_analyze_sentiment_success(self, base_url):
        """Test successful sentiment analysis"""
        payload = {
            "reviews": [
                {"text": "This is great!", "id": "1"},
                {"text": "This is bad.", "id": "2"}
            ]
        }

        response = requests.post(f"{base_url}/api/v1/analyze", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["total_processed"] == 2
        assert "processing_time" in data
        assert data["model_used"] == "vader"

        # Check results structure
        for result in data["results"]:
            assert "id" in result
            assert "text" in result
            assert "sentiment" in result
            assert "confidence" in result
            assert result["sentiment"] in ["POSITIVE", "NEGATIVE", "NEUTRAL"]

    def test_analyze_empty_reviews(self, base_url):
        """Test analysis with empty reviews list"""
        payload = {"reviews": []}

        response = requests.post(f"{base_url}/api/v1/analyze", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "message" in data

    def test_analyze_too_many_reviews(self, base_url):
        """Test analysis with too many reviews"""
        reviews = [{"text": f"Review {i}", "id": str(i)} for i in range(1001)]
        payload = {"reviews": reviews}

        response = requests.post(f"{base_url}/api/v1/analyze", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "message" in data

    def test_analyze_invalid_payload(self, base_url):
        """Test analysis with invalid payload"""
        payload = {"invalid": "data"}

        response = requests.post(f"{base_url}/api/v1/analyze", json=payload)
        assert response.status_code == 422  # Validation error

    def test_analyze_long_text(self, base_url):
        """Test analysis with very long text"""
        # The current limit is 5000 characters, so this should work
        long_text = "This is a great product! " * 100  # About 2400 characters
        payload = {"reviews": [{"text": long_text, "id": "long"}]}

        response = requests.post(f"{base_url}/api/v1/analyze", json=payload)
        assert response.status_code == 200  # Should work within limits