from pathlib import Path
from typing import Dict, Any, Callable
import json
import yaml


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        self.register("read_file", self._read_file)
        self.register("write_file", self._write_file)
        self.register("list_directory", self._list_directory)
        self.register("create_directory", self._create_directory)
        self.register("read_json", self._read_json)
        self.register("write_json", self._write_json)

    def register(self, name: str, func: Callable):
        self._tools[name] = func

    def get_tool(self, name: str) -> Callable:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found")
        return self._tools[name]

    def list_tools(self) -> list:
        return list(self._tools.keys())

    def _read_file(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"Error: File '{path}' not found"
        return p.read_text(encoding="utf-8")

    def _write_file(self, path: str, content: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"File written: {path}"

    def _list_directory(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"Error: Directory '{path}' not found"
        items = [f"{item.name}{'/' if item.is_dir() else ''}" for item in p.iterdir()]
        return "\n".join(items) if items else "Empty directory"

    def _create_directory(self, path: str) -> str:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return f"Directory created: {path}"

    def _read_json(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"Error: File '{path}' not found"
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data, indent=2)

    def _write_json(self, path: str, data: Dict[str, Any]) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return f"JSON written: {path}"


tool_registry = ToolRegistry()