"""MobileNetV2 image classification, via a Hugging Face `transformers` pipeline.

The model is downloaded once (from the Hugging Face Hub) and cached on disk by
`transformers` itself (~/.cache/huggingface by default). We lazy-load the
pipeline into a module-level singleton so the (fairly slow) model load only
happens once per process, on the first request that needs it, rather than on
every classification call.
"""

import io
import threading

from PIL import Image
from transformers import pipeline

_pipeline = None
_pipeline_lock = threading.Lock()


def _get_pipeline(model_name):
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:  # re-check inside the lock
                _pipeline = pipeline("image-classification", model=model_name)
    return _pipeline


def classify_image(image_bytes, model_name, top_k=5, min_score=0.15):
    """Run MobileNetV2 on raw image bytes and return suggested tags.

    Returns a list of {"label": str, "score": float} dicts, highest
    confidence first, filtered to predictions >= min_score.
    """
    pipe = _get_pipeline(model_name)

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    raw_results = pipe(image, top_k=top_k)

    predictions = []
    for item in raw_results:
        score = float(item["score"])
        if score < min_score:
            continue
        # ImageNet labels sometimes look like "Labrador retriever, Labrador".
        # Keep just the first, most common name and normalize casing so it
        # reads like a plain tag (e.g. "dog", "golden retriever").
        label = item["label"].split(",")[0].strip().lower()
        predictions.append({"label": label, "score": round(score, 4)})

    return predictions
