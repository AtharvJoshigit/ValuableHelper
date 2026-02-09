import html
from typing import Any, Dict, Union

def escape_html(text: str) -> str:
    """
    Escapes <, >, & for Telegram HTML.
    
    Args:
        text: The text to escape.
        
    Returns:
        The escaped string.
    """
    if not isinstance(text, str):
        return str(text)
    return html.escape(text, quote=False)

def format_tool_call(tool_name: str, tool_input: Union[Dict[str, Any], str, Any]) -> str:
    """
    Returns a user-friendly summary of a tool call.

    Args:
        tool_name: The name of the tool.
        tool_input: The input provided to the tool.

    Returns:
        A formatted string describing the tool call.
    """
    if not isinstance(tool_input, dict):
        # Fallback if input is not a dict
        return f"🔨 {escape_html(tool_name)}"

    try:
        if tool_name == 'read_file':
            path = tool_input.get('file_path') or tool_input.get('path', 'unknown')
            return f"📖 Reading file: {escape_html(str(path))}"
        
        if tool_name == 'add_task':
            title = tool_input.get('title', 'Untitled')
            return f"➕ Adding task: {escape_html(str(title))}"
        
        if tool_name == 'coder_agent':
            # Handle task_input if it's the key, or task_summary if that's preferred
            summary = tool_input.get('task_input') or tool_input.get('task_summary', 'Working...')
            return f"🧑‍💻 Coder Agent: {escape_html(str(summary))}"
            
        return f"🔨 {escape_html(tool_name)}"
        
    except Exception:
        # robust fallback
        return f"🔨 {escape_html(tool_name)}"

def format_tool_result(tool_name: str, tool_result: Any) -> str:
    """
    Returns a truncated summary of a tool result.

    Args:
        tool_name: The name of the tool (unused in current logic but kept for interface).
        tool_result: The result returned by the tool.

    Returns:
        A formatted and potentially truncated string.
    """
    result_str = str(tool_result)
    if len(result_str) > 100:
        return escape_html(result_str[:100]) + "... (truncated)"
    return escape_html(result_str)

def format_section(title: str, content: str) -> str:
    """
    Helper to format a section with a header.

    Args:
        title: The section title.
        content: The section content.

    Returns:
        HTML formatted string.
    """
    return f"<b>{escape_html(title)}</b>\n{content}"
