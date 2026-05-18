"""
ML Query Classifier — Phase 8
==============================
Uses a scikit-learn Logistic Regression (with TF-IDF features) to classify
natural-language queries into domain categories.

Categories (matching the build guide):
  academic       — courses, exams, grades, curriculum
  finance        — fees, scholarships, payments, budget
  hostel         — accommodation, rooms, wardens, facilities
  administration — policies, staff, forms, deadlines
  general        — fallback for anything that does not match the above

Training / Usage
----------------
1. First run trains and saves the model automatically to Backend/ml/model.pkl.
2. Subsequent runs load the saved model for fast inference.
3. Re-train by calling: python -m Backend.ml.classifier --train
"""
import logging
import os
import pickle
from typing import List

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")

# ---------------------------------------------------------------------------
# Training data — hand-crafted labelled examples per category
# ---------------------------------------------------------------------------
TRAINING_DATA = [
    # academic
    ("What are the exam dates?", "academic"),
    ("How many credit hours are required to graduate?", "academic"),
    ("Where can I find the course outline for CS-301?", "academic"),
    ("What is the grading policy?", "academic"),
    ("When does the semester start?", "academic"),
    ("How do I apply for a course drop?", "academic"),
    ("What subjects are offered in spring semester?", "academic"),
    ("Who is the department head for computer science?", "academic"),
    ("What is the attendance policy?", "academic"),
    ("How do I get a transcript?", "academic"),
    # finance
    ("What is the fee structure?", "finance"),
    ("When are tuition fees due?", "finance"),
    ("How do I apply for a scholarship?", "finance"),
    ("Are there any financial aid programs?", "finance"),
    ("What is the late payment penalty?", "finance"),
    ("How can I pay my semester fee online?", "finance"),
    ("Is there a fee waiver for top students?", "finance"),
    ("What is the refund policy?", "finance"),
    ("How much is the hostel fee?", "finance"),
    ("Who do I contact for fee-related issues?", "finance"),
    # hostel
    ("How do I apply for hostel accommodation?", "hostel"),
    ("What are the hostel rules?", "hostel"),
    ("Is Wi-Fi available in the hostel?", "hostel"),
    ("What time is the hostel gate closed?", "hostel"),
    ("Who is the warden of boys hostel?", "hostel"),
    ("Can I bring a guest to the hostel?", "hostel"),
    ("What facilities are available in the hostel?", "hostel"),
    ("How do I report a maintenance issue in my room?", "hostel"),
    ("Is there a curfew in the hostel?", "hostel"),
    ("How many students can share a hostel room?", "hostel"),
    # administration
    ("How do I apply for a no-objection certificate?", "administration"),
    ("What are the office hours?", "administration"),
    ("Where do I submit my leave application?", "administration"),
    ("What is the process for changing my major?", "administration"),
    ("Who do I contact for document verification?", "administration"),
    ("How do I get a degree certificate?", "administration"),
    ("What is the deadline for form submission?", "administration"),
    ("How do I file a complaint?", "administration"),
    ("What documents are required for enrollment?", "administration"),
    ("How can I contact the registrar?", "administration"),
    # general
    ("Tell me about the university.", "general"),
    ("What is the history of this institution?", "general"),
    ("Where is the library located?", "general"),
    ("Is there a cafeteria on campus?", "general"),
    ("What are the working hours of the IT department?", "general"),
    ("How do I reset my student portal password?", "general"),
    ("Where is the parking area?", "general"),
    ("Is there a gym on campus?", "general"),
    ("What sports facilities are available?", "general"),
    ("How do I contact student support?", "general"),
]


def _build_model():
    """Train and return a TF-IDF + LogisticRegression pipeline."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [t for t, _ in TRAINING_DATA]
    labels = [l for _, l in TRAINING_DATA]

    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=5000,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    C=5.0,
                    solver="lbfgs",
                ),
            ),
        ]
    )
    pipeline.fit(texts, labels)
    return pipeline


def _save_model(model) -> None:
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    logger.info("ML classifier saved to %s", MODEL_PATH)


def _load_model():
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


# ---------------------------------------------------------------------------
# Public classifier class
# ---------------------------------------------------------------------------
class QueryClassifier:
    """
    Scikit-learn–based query classifier.

    On first instantiation the model is trained (≈ 0.1 s) and persisted.
    Subsequent instantiations load from disk.
    """

    CATEGORIES = ["academic", "finance", "hostel", "administration", "general"]

    def __init__(self):
        if os.path.exists(MODEL_PATH):
            try:
                self._model = _load_model()
                logger.info("ML classifier loaded from %s", MODEL_PATH)
                return
            except Exception as exc:
                logger.warning(
                    "Failed to load saved classifier (%s); retraining.", exc
                )

        logger.info("Training ML classifier …")
        self._model = _build_model()
        try:
            _save_model(self._model)
        except Exception as exc:
            logger.warning("Could not save classifier: %s", exc)

    def predict(self, texts: List[str]) -> List[str]:
        """Return predicted category label for each text."""
        if not texts:
            return []
        return list(self._model.predict(texts))

    def predict_proba(self, texts: List[str]) -> List[dict]:
        """Return per-class probabilities for each text."""
        if not texts:
            return []
        proba_matrix = self._model.predict_proba(texts)
        classes = self._model.classes_
        return [
            {cls: round(float(prob), 4) for cls, prob in zip(classes, row)}
            for row in proba_matrix
        ]


# ---------------------------------------------------------------------------
# CLI — python -m Backend.ml.classifier --train
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if "--train" in sys.argv:
        print("Training and saving ML classifier …")
        model = _build_model()
        _save_model(model)
        print(f"Model saved to {MODEL_PATH}")
    else:
        print("Usage: python -m Backend.ml.classifier --train")
