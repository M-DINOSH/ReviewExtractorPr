"""
Sentiment analysis service using VADER
"""
import time
from typing import List

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..core.config import settings
from ..core.logging import get_logger
from ..models.schemas import ReviewInput, SentimentResult


logger = get_logger(__name__)


class SentimentAnalyzer:
    """Sentiment analysis service using VADER"""

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

        # Enhanced lexicon for better accuracy
        self.analyzer.lexicon.update({
            "amazing": 3.0,
            "awesome": 3.0,
            "excellent": 2.5,
            "fantastic": 2.5,
            "great": 2.0,
            "good": 1.5,
            "decent": 1.0,
            "okay": 0.5,
            "mediocre": -0.5,
            "poor": -1.5,
            "bad": -2.0,
            "terrible": -3.0,
            "horrible": -3.0,
            "awful": -3.0
        })

        logger.info("Sentiment analyzer initialized", extra={"model": settings.sentiment_model})

    def analyze_review(self, review: ReviewInput) -> SentimentResult:
        """Analyze sentiment of a single review"""
        start_time = time.time()

        # Get sentiment scores
        scores = self.analyzer.polarity_scores(review.text)

        # Determine sentiment
        compound = scores['compound']
        if compound >= 0.05:
            sentiment = "POSITIVE"
        elif compound <= -0.05:
            sentiment = "NEGATIVE"
        else:
            sentiment = "NEUTRAL"

        # Calculate confidence (absolute value of compound score normalized to 0-1)
        confidence = min(abs(compound), 1.0)

        processing_time = time.time() - start_time
        logger.debug(
            f"Analyzed review in {processing_time:.4f}s",
            extra={
                "review_id": review.id,
                "sentiment": sentiment,
                "confidence": confidence,
                "text_length": len(review.text)
            }
        )

        return SentimentResult(
            id=review.id,
            text=review.text,
            sentiment=sentiment,
            confidence=confidence
        )

    def analyze_reviews(self, reviews: List[ReviewInput]) -> List[SentimentResult]:
        """Analyze sentiment of multiple reviews"""
        start_time = time.time()

        results = []
        for review in reviews:
            result = self.analyze_review(review)
            results.append(result)

        processing_time = time.time() - start_time

        logger.info(
            f"Batch analyzed {len(reviews)} reviews in {processing_time:.4f}s",
            extra={
                "batch_size": len(reviews),
                "processing_time": processing_time,
                "avg_time_per_review": processing_time / len(reviews) if reviews else 0
            }
        )

        return results


# Global analyzer instance
sentiment_analyzer = SentimentAnalyzer()