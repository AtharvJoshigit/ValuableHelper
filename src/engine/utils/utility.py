@staticmethod
def to_gemini_role(role: str) -> str:
    return "user" if role == "user" else "model"