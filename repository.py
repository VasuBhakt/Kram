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

    def _load_object(self, obj_hash: str) -> KramObject:
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir / obj_hash[2:]

        if not obj_file.exists():
            raise FileNotFoundError(f"Object {obj_hash} not found")

        return KramObject.deserialize(obj_file.read_bytes())

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
        index[rel_path.as_posix()] = blob_hash
        self._save_index(index)
        print(f"Added {rel_path.as_posix()} to the index")

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
                index[rel_path.as_posix()] = blob_hash
                added_count += 1
                print(f"Added {rel_path.as_posix()} to the index")
        self._save_index(index)
        print(f"Added {added_count} files from {path} to the index")

    def _rm_file(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")
        rel_path = full_path.relative_to(self.path)
        index = self._load_index()
        if rel_path.as_posix() not in index:
            raise ValueError(f"{path} is not tracked by Kram")
        del index[rel_path.as_posix()]
        self._save_index(index)
        print(f"Untracked file {full_path.as_posix()}")

    def _rm_dir(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Directory not found: {full_path}")
        index = self._load_index()
        rm_count = 0
        for file_path in full_path.rglob("*"):
            rel_path = file_path.relative_to(self.path)
            if file_path.is_file():
                if rel_path.as_posix() in index:
                    del index[rel_path.as_posix()]
                    rm_count += 1
                    print(f"Untracked file {file_path.as_posix()} ")
        self._save_index(index)
        print(f"Untrack {rm_count} files from {path}")

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

    def remove_path(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            print(f"File not found: {full_path}")
            return
        # load current ignore patterns
        if full_path.is_file():
            self._rm_file(path)
        elif full_path.is_dir():
            self._rm_dir(path)
        else:
            raise ValueError(f"{path} is neither a file nor a directory")

    def _create_tree_from_index(self):
        index = self._load_index()
        if not index:
            tree = Tree()
            return self._store_object(tree)
        dirs = {}
        files = {}
        for file_path, blob_hash in index.items():
            parts = file_path.split("/")
            if len(parts) == 1:
                # file in root folder
                files[parts[0]] = blob_hash
            else:
                dir_name = parts[0]
                if dir_name not in dirs:
                    dirs[dir_name] = {}
                current = dirs[dir_name]
                for part in parts[1:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                current[parts[-1]] = blob_hash

        def _create_tree_recursive(entries_dict: dict):
            tree = Tree()
            for name, value in entries_dict.items():
                if isinstance(value, str):
                    # file
                    tree.add_entry("100644", name, value)
                if isinstance(value, dict):
                    # directory
                    subtree_hash = _create_tree_recursive(value)
                    tree.add_entry("40000", name, subtree_hash)
            return self._store_object(tree)

        root_entries = {**files}
        for dir_name, dir_content in dirs.items():
            root_entries[dir_name] = dir_content

        return _create_tree_recursive(root_entries)

    def get_branch_commit(self, current_branch: str):
        branch_file = self.heads_dir / current_branch
        if branch_file.exists():
            return branch_file.read_text().strip()
        return None

    def set_branch_commit(self, current_branch: str, commit_hash: str):
        branch_file = self.heads_dir / current_branch
        branch_file.write_text(commit_hash + "\n")

    def commit(self, message: str, author: str = "Kram User"):
        # create a tree object from the index (staging area)
        tree_hash = self._create_tree_from_index()

        current_branch = self.get_current_branch()
        parent_commit = self.get_branch_commit(current_branch)
        parent_hashes = [parent_commit] if parent_commit else []

        index = self._load_index()
        if not index:
            print(f"nothing to commit, working tree clean")
            return None

        if parent_commit:
            parent_commit_obj = self._load_object(parent_commit)
            parent_commit_data = Commit._deserialize_commit(parent_commit_obj.content)
            if tree_hash == parent_commit_data.tree_hash:
                print(f"nothing to commit, working tree clean")
                return None

        commit = Commit(
            tree_hash=tree_hash,
            parent_hashes=parent_hashes,
            author=author,
            committer=author,
            message=message,
        )
        commit_hash = self._store_object(commit)
        self.set_branch_commit(current_branch, commit_hash)
        print(f"Created commit {commit_hash} on branch {current_branch}")
        return commit_hash

    def get_current_branch(self) -> str:
        if not self.head_file.exists():
            return "main"
        head_content = self.head_file.read_text().strip()
        if head_content.startswith("ref: refs/heads/"):
            return head_content[16:]
        return "main"

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

            if part_lower in ignore_patterns or part_lower in [".kram", ".git"]:
                return True

        return False
