import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import json


def get_current_working_directory() -> Dict[str, str]:
    try:
        cwd = os.getcwd()
        return {
            "status": "success",
            "current_directory": cwd,
            "absolute_path": str(Path(cwd).resolve())
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def list_directory(
    path: Optional[str] = None,
    recursive: bool = False,
    include_hidden: bool = False
) -> Dict[str, Any]:
    try:
        target_path = Path(path) if path else Path.cwd()
        target_path = target_path.resolve()
        
        if not target_path.exists():
            return {
                "status": "error",
                "error": f"Path does not exist: {target_path}"
            }
        
        if not target_path.is_dir():
            return {
                "status": "error",
                "error": f"Path is not a directory: {target_path}"
            }
        
        items = []
        
        if recursive:
            for item in target_path.rglob("*"):
                if not include_hidden and any(part.startswith('.') for part in item.parts):
                    continue
                relative_path = item.relative_to(target_path)
                items.append({
                    "name": item.name,
                    "path": str(relative_path),
                    "absolute_path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
        else:
            for item in target_path.iterdir():
                if not include_hidden and item.name.startswith('.'):
                    continue
                items.append({
                    "name": item.name,
                    "path": str(item.relative_to(target_path)),
                    "absolute_path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
        
        return {
            "status": "success",
            "directory": str(target_path),
            "item_count": len(items),
            "items": sorted(items, key=lambda x: (x["type"] != "directory", x["name"]))
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def read_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {
                "status": "error",
                "error": f"File does not exist: {path}"
            }
        
        if not path.is_file():
            return {
                "status": "error",
                "error": f"Path is not a file: {path}"
            }
        
        with open(path, 'r', encoding=encoding) as f:
            content = f.read()
        
        return {
            "status": "success",
            "file_path": str(path),
            "content": content,
            "size": path.stat().st_size,
            "lines": content.count('\n') + 1
        }
    
    except UnicodeDecodeError:
        return {
            "status": "error",
            "error": f"Unable to decode file with {encoding} encoding. File may be binary."
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def create_file(file_path: str, content: str = "", encoding: str = "utf-8") -> Dict[str, Any]:
    try:
        path = Path(file_path).resolve()
        
        if path.exists():
            return {
                "status": "error",
                "error": f"File already exists: {path}. Use overwrite_file to modify existing files."
            }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        
        return {
            "status": "success",
            "file_path": str(path),
            "size": path.stat().st_size,
            "message": "File created successfully"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def overwrite_file(file_path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {
                "status": "error",
                "error": f"File does not exist: {path}. Use create_file to create new files."
            }
        
        if not path.is_file():
            return {
                "status": "error",
                "error": f"Path is not a file: {path}"
            }
        
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        
        return {
            "status": "success",
            "file_path": str(path),
            "size": path.stat().st_size,
            "message": "File overwritten successfully"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def append_to_file(file_path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {
                "status": "error",
                "error": f"File does not exist: {path}. Use create_file to create new files."
            }
        
        if not path.is_file():
            return {
                "status": "error",
                "error": f"Path is not a file: {path}"
            }
        
        with open(path, 'a', encoding=encoding) as f:
            f.write(content)
        
        return {
            "status": "success",
            "file_path": str(path),
            "size": path.stat().st_size,
            "message": "Content appended successfully"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def create_directory(directory_path: str) -> Dict[str, Any]:
    try:
        path = Path(directory_path).resolve()
        
        if path.exists():
            return {
                "status": "error",
                "error": f"Directory already exists: {path}"
            }
        
        path.mkdir(parents=True, exist_ok=False)
        
        return {
            "status": "success",
            "directory_path": str(path),
            "message": "Directory created successfully"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def delete_file(file_path: str) -> Dict[str, Any]:
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {
                "status": "error",
                "error": f"File does not exist: {path}"
            }
        
        if not path.is_file():
            return {
                "status": "error",
                "error": f"Path is not a file: {path}. Use delete_directory for directories."
            }
        
        path.unlink()
        
        return {
            "status": "success",
            "file_path": str(path),
            "message": "File deleted successfully"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def delete_directory(directory_path: str, recursive: bool = False) -> Dict[str, Any]:
    try:
        path = Path(directory_path).resolve()
        
        if not path.exists():
            return {
                "status": "error",
                "error": f"Directory does not exist: {path}"
            }
        
        if not path.is_dir():
            return {
                "status": "error",
                "error": f"Path is not a directory: {path}. Use delete_file for files."
            }
        
        if recursive:
            shutil.rmtree(path)
        else:
            path.rmdir()
        
        return {
            "status": "success",
            "directory_path": str(path),
            "message": "Directory deleted successfully"
        }
    
    except OSError as e:
        if "not empty" in str(e).lower():
            return {
                "status": "error",
                "error": f"Directory is not empty: {path}. Use recursive=True to delete non-empty directories."
            }
        return {
            "status": "error",
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def validate_path(path: str) -> Dict[str, Any]:
    try:
        p = Path(path).resolve()
        
        return {
            "status": "success",
            "path": str(p),
            "exists": p.exists(),
            "is_file": p.is_file() if p.exists() else None,
            "is_directory": p.is_dir() if p.exists() else None,
            "is_absolute": p.is_absolute(),
            "parent": str(p.parent),
            "name": p.name,
            "suffix": p.suffix if p.is_file() or not p.exists() else None
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def get_file_info(file_path: str) -> Dict[str, Any]:
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {
                "status": "error",
                "error": f"Path does not exist: {path}"
            }
        
        stat = path.stat()
        
        return {
            "status": "success",
            "path": str(path),
            "name": path.name,
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "accessed": stat.st_atime,
            "is_readable": os.access(path, os.R_OK),
            "is_writable": os.access(path, os.W_OK),
            "is_executable": os.access(path, os.X_OK)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def move_file(source_path: str, destination_path: str) -> Dict[str, Any]:
    try:
        src = Path(source_path).resolve()
        dst = Path(destination_path).resolve()
        
        if not src.exists():
            return {
                "status": "error",
                "error": f"Source path does not exist: {src}"
            }
        
        if dst.exists():
            return {
                "status": "error",
                "error": f"Destination path already exists: {dst}"
            }
        
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        
        return {
            "status": "success",
            "source_path": str(src),
            "destination_path": str(dst),
            "message": "File/directory moved successfully"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def copy_file(source_path: str, destination_path: str) -> Dict[str, Any]:
    try:
        src = Path(source_path).resolve()
        dst = Path(destination_path).resolve()
        
        if not src.exists():
            return {
                "status": "error",
                "error": f"Source path does not exist: {src}"
            }
        
        if not src.is_file():
            return {
                "status": "error",
                "error": f"Source path is not a file: {src}"
            }
        
        if dst.exists():
            return {
                "status": "error",
                "error": f"Destination path already exists: {dst}"
            }
        
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        
        return {
            "status": "success",
            "source_path": str(src),
            "destination_path": str(dst),
            "size": dst.stat().st_size,
            "message": "File copied successfully"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def search_files(
    pattern: str,
    search_path: Optional[str] = None,
    case_sensitive: bool = False
) -> Dict[str, Any]:
    try:
        target_path = Path(search_path) if search_path else Path.cwd()
        target_path = target_path.resolve()
        
        if not target_path.exists():
            return {
                "status": "error",
                "error": f"Search path does not exist: {target_path}"
            }
        
        matches = []
        
        if case_sensitive:
            for item in target_path.rglob(pattern):
                matches.append({
                    "name": item.name,
                    "path": str(item.relative_to(target_path)),
                    "absolute_path": str(item),
                    "type": "directory" if item.is_dir() else "file"
                })
        else:
            for item in target_path.rglob("*"):
                if pattern.lower() in item.name.lower():
                    matches.append({
                        "name": item.name,
                        "path": str(item.relative_to(target_path)),
                        "absolute_path": str(item),
                        "type": "directory" if item.is_dir() else "file"
                    })
        
        return {
            "status": "success",
            "search_path": str(target_path),
            "pattern": pattern,
            "match_count": len(matches),
            "matches": matches
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }