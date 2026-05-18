import logging

logger = logging.getLogger(__name__)


class SimpleClassifier:
    """Simple keyword-based query classifier."""
    
    CATEGORIES = {
        "algorithms": ["algorithm", "approach", "method", "technique", "how to"],
        "concepts": ["what is", "concept", "definition", "meaning", "explain"],
        "examples": ["example", "sample", "case", "instance", "demo"],
        "implementation": ["implement", "code", "build", "create", "write"],
        "performance": ["fast", "slow", "efficient", "optimization", "performance"],
        "comparison": ["vs", "difference", "compare", "versus", "better"],
    }

    def __init__(self):
        self.categories = self.CATEGORIES

    def predict(self, texts: list) -> list:
        """Predict category for each text."""
        predictions = []
        for text in texts:
            text_lower = text.lower()
            category = "general"
            max_matches = 0

            for cat, keywords in self.categories.items():
                matches = sum(1 for kw in keywords if kw in text_lower)
                if matches > max_matches:
                    max_matches = matches
                    category = cat

            predictions.append(category)
            logger.debug("Classified '%s' as '%s'", text[:50], category)

        return predictions
