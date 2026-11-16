"""Image OCR: macOS Vision first, tesseract as a fallback."""

from pathlib import Path

from app.rag.text import normalize_text


def ocr_image(path: Path) -> tuple[str, str]:
    """Return recognized text and a warning. Never raises for OCR failures."""
    try:
        from ocrmac import ocrmac

        annotations = ocrmac.OCR(
            str(path), language_preference=["zh-Hans", "en-US"]
        ).recognize()
        text = "\n".join(
            str(item[0]) for item in annotations if str(item[0]).strip()
        )
        if text.strip():
            return normalize_text(text), ""
        vision_warning = "macOS Vision 没有识别出文字。"
    except Exception as exc:  # noqa: BLE001 - fall back to tesseract
        vision_warning = f"macOS Vision OCR 不可用：{exc}"

    try:
        import pytesseract
        from PIL import Image

        with Image.open(path) as image:
            text = pytesseract.image_to_string(image, lang="eng")
        if text.strip():
            return normalize_text(text), (
                "中文 OCR 使用了英文回退，识别结果可能不完整。"
            )
    except Exception as exc:  # noqa: BLE001 - report a clear OCR failure
        return "", f"图片 OCR 失败：{vision_warning}；{exc}"

    return "", vision_warning
