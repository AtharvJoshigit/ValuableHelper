import os
import datetime

def generate_tool_manifest():
    search_dirs = [
        "src/engine/registry/library",
        "src/tools"
    ]
    manifest_path = "me/knowledge/tools_manifest.md"
    
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("# ValH Tool Manifest\n")
        f.write(f"*Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        f.write("This file is a generated index of all available native and custom tools. ")
        f.write("ValH should refer to this if unsure about available capabilities.\n\n")
        
        for directory in search_dirs:
            f.write(f"## Directory: `{directory}`\n")
            if os.path.exists(directory):
                files = [f for f in os.listdir(directory) if f.endswith(".py") and f != "__init__.py"]
                for file in files:
                    # Very basic "parsing" of tool name from filename
                    tool_name = file.replace("_tool.py", "").replace(".py", "")
                    f.write(f"- **{tool_name}** (`{file}`)\n")
            else:
                f.write("- *Directory not found.*\n")
            f.write("\n")

    print(f"Manifest generated at {manifest_path}")

if __name__ == "__main__":
    generate_tool_manifest()
