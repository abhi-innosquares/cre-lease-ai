from src.extractors.lease_extractor import LeaseExtractor
from src.utils.language import translate_to_english_if_needed
import pytesseract
from pdf2image import convert_from_path


def ocr_pdf(file_path: str) -> str:
    """Convert scanned PDF to text using OCR"""
    images = convert_from_path(file_path)
    full_text = ""

    for img in images:
        text = pytesseract.image_to_string(img)
        full_text += text + "\n"

    return full_text


def document_agent(state: dict):

    file_path = state["file_path"]

    extractor = LeaseExtractor()

    # -------------------------------
    # STEP 1: Extract raw text safely
    # -------------------------------

    try:
        raw_text = extractor.extract_text_from_pdf(file_path)

        if not raw_text or not raw_text.strip():
            raise ValueError("Empty text from PDF")

    except Exception:
        print("⚠ No embedded text found. Falling back to OCR...")
        raw_text = ocr_pdf(file_path)

    translation_result = translate_to_english_if_needed(raw_text)
    normalized_text = translation_result.get("text", raw_text)

    if translation_result.get("translated"):
        print(
            "Translated lease text to English "
            f"(detected: {translation_result.get('language_info', {}).get('language', 'unknown')})."
        )

    # -------------------------------
    # STEP 2: Extract structured data
    # -------------------------------

    structured_data = extractor.extract(normalized_text)

    # -------------------------------
    # Save to state
    # -------------------------------

    state["structured_data"] = structured_data
    state["raw_text"] = normalized_text
    state["raw_text_original"] = raw_text
    state["translation_meta"] = {
        "translated": bool(translation_result.get("translated")),
        "language_info": translation_result.get("language_info", {}),
    }

    return state