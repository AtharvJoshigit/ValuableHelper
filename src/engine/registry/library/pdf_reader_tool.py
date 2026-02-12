
import pypdf
from engine.registry.base_tool import BaseTool

class PDFReaderTool(BaseTool):
    """
    Extracts and returns all text from a PDF file.
    """
    name: str = "pdf_reader"
    description: str = "Reads a PDF file and returns the text content."

    def execute(self, **kwargs) -> str:
        file_path = kwargs.get("file_path")
        if not file_path:
            return "Error: No file_path provided."
        try:
            reader = pypdf.PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text if text.strip() else "PDF is empty or contains only images."
        except Exception as e:
            return f"Error reading PDF: {str(e)}"
