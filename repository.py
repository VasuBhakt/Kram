from object import *
import json
from pathlib import Path
import platform
import ctypes
import fnmatch

DEFAULT_IGNORES = """# Kram Ignore File
# For directories, DON'T end it with a trailing slash (e.g. venv not venv/). This could end disastrously
# For files, write the file names AS THEY ARE. (e.g. - text.txt, not just text)

.kram
.git
venv
.venv
env
.env
__pycache__
node_modules
.vscode
.idea
"""


class Repository:
    def __init__(self, path="."):
        self.path = Path(path).resolve()  # kram init
        self.kram_ignore = self.path / ".kramignore"
        self.kram_dir = self.path / ".kram"
        # .kram/objects
        self.objects_dir = self.kram_dir / "objects"
        # .kram/HEAD
        self.head_file = self.kram_dir / "HEAD"
        # .kram/refs
        self.refs_dir = self.kram_dir / "refs"
        # .kram/refs/heads
        self.heads_dir = self.refs_dir / "heads"
        # .kram/index
        self.index_file = self.kram_dir / "index"

    def init(self) -> bool:
        if self.kram_dir.exists():
            print(f"Kram repository already exists in {self.kram_dir}")
            return False

        # kram directory
        self.kram_dir.mkdir()
        # hide the directory
        if platform.system() == "Windows":
            # 0x02 is the hex code for the 'Hidden' attribute in Windows
            ctypes.windll.kernel32.SetFileAttributesW(str(self.kram_dir), 0x02)

        # kram ignore
        self.kram_ignore.touch()
        if self.kram_ignore.exists():
            self.kram_ignore.write_text(DEFAULT_IGNORES)
        # directories
        self.objects_dir.mkdir()
        self.refs_dir.mkdir()
        self.heads_dir.mkdir()

        # create initial HEAD  pointing to a branch
        self.head_file.write_text("ref: refs/heads/main\n")
        # create initial index
        self.index_file.write_text(json.dumps({}, indent=2))

        print(
            f"Initialized empty Kram repository in {self.kram_dir}. Please do fill out the .kramignore file to untrack all the files you don't need to be tracked."
        )
        return True

    def _store_object(self, obj: KramObject) -> str:
        obj_hash = obj.hash_object()
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir / obj_hash[2:]

        # check for duplicate file
        if not obj_file.exists():
            obj_dir.mkdir(exist_ok=True)
            obj_file.write_bytes(obj.serialize())

        return obj_hash

    def _load_index(self) -> dict[str, str]:
        if not self.index_file.exists():
            return {}
        try:
            return json.loads(self.index_file.read_text())
        except:
            return {}

    def _save_index(self, index: dict[str, str]):
        self.index_file.write_text(json.dumps(index, indent=2))

    def _delete_object(self, path: str):
        obj_dir = self.objects_dir / path[:2]
        obj_file = obj_dir / path[2:]
        if not obj_file.exists():
            raise FileNotFoundError(f"The file {path} does not exist")
        obj_file.unlink()
        # remove the directory if it is empty
        if not any(obj_dir.iterdir()):
            obj_dir.rmdir()

    def _add_file(self, path: str, current_ignore_patterns: set[str]):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")
        rel_path = full_path.relative_to(self.path)
        if self._should_ignore(rel_path, ignore_patterns=current_ignore_patterns):
            return
        # read the file content
        content = full_path.read_bytes()
        # create BLOB object from the content
        blob = Blob(content)
        # store the blob object in .kram/objects i.e. the database
        blob_hash = self._store_object(blob)
        # update index to include the file
        index = self._load_index()
        # delete previous location (garbage collection)
        old_hash = index.get(path)
        if old_hash and old_hash != blob_hash:
            self._delete_object(old_hash)
        index[path] = blob_hash
        self._save_index(index)
        print(f"Added {path} to the index")

    def _add_directory(self, path: str, current_ignore_patterns: set[str]):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Directory not found: {full_path}")
        if not full_path.is_dir():
            raise ValueError(f"{path} is not a directory")

        index = self._load_index()
        added_count = 0
        # recursively traverse the directory
        for file_path in full_path.rglob("*"):
            rel_path = file_path.relative_to(self.path)
            if self._should_ignore(rel_path, ignore_patterns=current_ignore_patterns):
                continue
            if file_path.is_file():
                # create blob
                # read the file content
                content = file_path.read_bytes()
                # create BLOB object from the content
                blob = Blob(content)
                # store the blob object in .kram/objects i.e. the database
                blob_hash = self._store_object(blob)
                # update index
                rel_path_str = rel_path.as_posix()
                old_hash = index.get(rel_path_str)
                if old_hash and old_hash != blob_hash:
                    self._delete_object(old_hash)
                index[rel_path_str] = blob_hash
                added_count += 1
                print(f"Added {rel_path.as_posix()} to the index")
        self._save_index(index)
        print(f"Added {added_count} files from {path} to the index")

    def add_path(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            print(f"File not found: {full_path}")
            return
        # load current ignore patterns
        current_ignore_patterns = self._ignore_patterns
        if full_path.is_file():
            self._add_file(path, current_ignore_patterns)
        elif full_path.is_dir():
            self._add_directory(path, current_ignore_patterns)
        else:
            raise ValueError(f"{path} is neither a file nor a directory")

    @property
    def _ignore_patterns(self) -> set[str]:
        """Always returns the fresh state of .kramignore"""
        patterns = {".kram", ".git"}  # Hardcoded safety
        if self.kram_ignore.exists():
            lines = self.kram_ignore.read_text().splitlines()
            patterns.update(
                line.strip().lower().rstrip("/")
                for line in lines
                if line.strip() and not line.startswith("#")
            )
        return patterns

    def _should_ignore(self, file_path: Path, ignore_patterns: set[str]) -> bool:
        # Normalize the full path to a string (e.g., "test_folder/text1.txt")
        full_rel_path = file_path.as_posix().lower()

        # 1. Full Path Check: O(1)
        if full_rel_path in ignore_patterns:
            return True

        # 2. Part-by-Part Check: O(1) per part
        for part in file_path.parts:
            part_lower = part.lower()

            if part_lower in ignore_patterns:
                return True

            if part_lower.startswith(".") and part_lower != ".":
                return True

        return False
