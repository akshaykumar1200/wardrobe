"""Download the vision models into the model cache during image build."""

from transformers import (
    AutoModelForImageSegmentation,
    AutoModelForSemanticSegmentation,
    SegformerImageProcessor,
)

from backend.config import settings


def main() -> None:
    SegformerImageProcessor.from_pretrained(settings.MODEL_ID)
    AutoModelForSemanticSegmentation.from_pretrained(settings.MODEL_ID)
    AutoModelForImageSegmentation.from_pretrained(
        settings.MATTING_MODEL_ID,
        trust_remote_code=True,
    )


if __name__ == "__main__":
    main()
