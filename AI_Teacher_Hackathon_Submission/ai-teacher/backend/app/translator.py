"""
translator.py — Multilingual support.

Uses `deep-translator` (free, no API key) for text translation and maps
human language names to both translator codes and gTTS voice codes.
Supports major Indian + international languages as encouraged by the brief.
"""
from deep_translator import GoogleTranslator

# name -> (translate_code, gtts_code)
LANGUAGES = {
    "english": ("en", "en"),
    "hindi": ("hi", "hi"),
    "hinglish": ("hi", "hi"),  # transliteration handled at prompt level, spoken as Hindi
    "bengali": ("bn", "bn"),
    "tamil": ("ta", "ta"),
    "telugu": ("te", "te"),
    "marathi": ("mr", "mr"),
    "gujarati": ("gu", "gu"),
    "kannada": ("kn", "kn"),
    "malayalam": ("ml", "ml"),
    "punjabi": ("pa", "pa"),
    "urdu": ("ur", "ur"),
    "spanish": ("es", "es"),
    "french": ("fr", "fr"),
    "german": ("de", "de"),
    "chinese": ("zh-CN", "zh-CN"),
    "japanese": ("ja", "ja"),
    "arabic": ("ar", "ar"),
    "russian": ("ru", "ru"),
    "portuguese": ("pt", "pt"),
}


def resolve_language(name: str):
    key = (name or "english").strip().lower()
    return LANGUAGES.get(key, LANGUAGES["english"])


def translate_text(text: str, target_language_name: str) -> str:
    code, _ = resolve_language(target_language_name)
    if code == "en" or not text.strip():
        return text
    try:
        # deep-translator has a request size limit; chunk long text
        out = []
        for i in range(0, len(text), 4500):
            out.append(GoogleTranslator(source="auto", target=code).translate(text[i:i + 4500]))
        return " ".join(out)
    except Exception as e:
        # Network-restricted / offline environments: fail soft, return original
        return text + f"\n\n[translation unavailable: {e}]"
