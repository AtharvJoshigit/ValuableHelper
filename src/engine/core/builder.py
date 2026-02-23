import datetime
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import List, Union

logger = logging.getLogger(__name__)

def get_load_eligible_files() -> List[str]: 
    """Returns the list of files to be loaded."""
    return ["system.md"]

def _get_project_root() -> Path:
    """Helper to find project root."""
    return Path(__file__).parent.parent if "__file__" in globals() else Path.cwd()

def _build_system_context(path: Path = None) -> str:
    """
    Builds context by replacing placeholders. 
    Returns default data if path doesn't exist.
    """
    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    
    sys_info = {
        "{{CURRENT_DATETIME}}": now.strftime("%B %d, %Y %I:%M %p IST"),
        "{{DAY_OF_WEEK}}": now.strftime("%A"),
        "{{OS_FULL}}": f"{platform.system()} {platform.release()}",
        "{{ARCH}}": platform.machine(),
        "{{PYTHON_VERSION}}": platform.python_version(),
        "{{CWD}}": os.getcwd(),
        "{{GEMINI_MODEL_NAME}}": "gemini-3-flash",
        "{{TURN_START}}": now.strftime("%H:%M:%S IST")
    }

    try:
        _, _, free = shutil.disk_usage("/")
        sys_info["{{DISK_FREE_GB}}"] = str(round(free / (1024**3), 1))
    except Exception:
        sys_info["{{DISK_FREE_GB}}"] = "N/A"

    # Default data template if the file is missing
    if path and path.exists():
        context = path.read_text(encoding='utf-8')
    else:
        context = "--- SYSTEM DATA ---\nTime: {{CURRENT_DATETIME}}\nOS: {{OS_FULL}}"

    for key, value in sys_info.items():
        context = context.replace(key, value)
        
    return context

def build_turn_prompt(original_prompt: str, filenames: Union[str, List[str]] = None) -> str: 
    """
    Constructs the final prompt:
    1. Original Prompt
    2. System Metadata / Files
    """
    if filenames is None:
        filenames = get_load_eligible_files()
    
    if isinstance(filenames, str):
        filenames = [filenames]

    # We start the list with the user's original message
    prompt_parts = [original_prompt.strip()]
    
    try:
        for filename in filenames:
            prompt_path = _get_project_root() / "me" / filename
            
            if "system.md" in filename:
                # Always adds system info (even if file is missing, via default data)
                prompt_parts.append(_build_system_context(path=prompt_path))
            elif prompt_path.exists():
                prompt_parts.append(prompt_path.read_text(encoding='utf-8'))
            else:
                logger.warning(f"File {filename} not found, skipping.")

        # Join everything with double newlines for clear separation
        return "\n\n".join(prompt_parts).strip()

    except Exception as e:
        logger.error(f"Error building prompt: {e}")
        return original_prompt # Fallback to just the user prompt on error