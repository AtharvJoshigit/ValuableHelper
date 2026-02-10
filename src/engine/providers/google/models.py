
from enum import Enum


class GeminiModel(str, Enum):
    # --- Gemini 3 (Latest / Experimental) ---
    GEMINI_3_PRO_PREVIEW = "gemini-3-pro-preview"
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"
    GEMINI_3_THINKING_PREVIEW = "gemini-3-thinking-preview"

    # --- Gemini 2.5 (Stable / Current Gen) ---
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"

    # --- Gemini 2.0 (Stable / Current Gen) ---
    GEMINI_2_PRO = "gemini-2.0-pro"
    GEMINI_2_FLASH = "gemini-2.0-flash"
    GEMINI_2_FLASH_LITE = "gemini-2.0-flash-lite"
    GEMINI_2_THINKING_EXPERIMENTAL = "gemini-2.0-flash-thinking-exp"

    # --- Gemini 1.5 (Legacy / Long Context Support) ---
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_FLASH_8B = "gemini-1.5-flash-8b"

    # --- Specialized / Vision ---
    GEMINI_PRO_VISION = "gemini-pro-vision"