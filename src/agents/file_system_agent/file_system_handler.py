from typing import Optional
from src.agents.file_system_agent.files_system_handler import LLMFileSystemAgent


def create_filesystem_agent(
    provider: str = "groq",
    model: str = "groq/compound",
    api_key: Optional[str] = None
) -> LLMFileSystemAgent:
    from src.agents.file_system_agent.tools.filesystem_tools import (
        get_current_working_directory,
        list_directory,
        read_file,
        create_file,
        overwrite_file,
        append_to_file,
        create_directory,
        delete_file,
        delete_directory,
        validate_path,
        get_file_info,
        move_file,
        copy_file,
        search_files
    )
    
    functions = {
        "get_current_working_directory": get_current_working_directory,
        "list_directory": list_directory,
        "read_file": read_file,
        "create_file": create_file,
        "overwrite_file": overwrite_file,
        "append_to_file": append_to_file,
        "create_directory": create_directory,
        "delete_file": delete_file,
        "delete_directory": delete_directory,
        "validate_path": validate_path,
        "get_file_info": get_file_info,
        "move_file": move_file,
        "copy_file": copy_file,
        "search_files": search_files
    }
    
    return LLMFileSystemAgent(
        provider=provider,
        model=model,
        filesystem_functions=functions,
        api_key=api_key
    )