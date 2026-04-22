from object import *
import json
from pathlib import Path
import platform
import ctypes
import fnmatch
from datetime import datetime

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
        # .kram/logs
        self.logs_dir = self.kram_dir / "logs"
        # .kram/logs/heads
        self.logs_heads_dir = self.logs_dir / "heads"
        

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
        self.logs_dir.mkdir()
        self.logs_heads_dir.mkdir()

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
        rel_path = full_path.relative_to(self.path)
        if self._should_ignore(rel_path, ignore_patterns=current_ignore_patterns):
            return
        index = self._load_index()
        if not full_path.exists():
            if rel_path.as_posix() in index:
                del index[rel_path.as_posix()]
                print(f"Removed missing file {rel_path.as_posix()} from the index")
                self._save_index(index)
                return
            else:
                raise FileNotFoundError(f"File not found: {full_path}")
        # read the file content
        content = full_path.read_bytes()
        # create BLOB object from the content
        blob = Blob(content)
        # store the blob object in .kram/objects i.e. the database
        blob_hash = self._store_object(blob)
        # update index to include the file and its metadata for faster status checks

        stat = full_path.stat()
        index[rel_path.as_posix()] = {
            "hash": blob_hash,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }
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
                # update index with hash and metadata
                stat = file_path.stat()
                index[rel_path.as_posix()] = {
                    "hash": blob_hash,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
                added_count += 1
                print(f"Added {rel_path.as_posix()} to the index")

        # remove missing files
        missing_file = 0
        for tracked_path in list(index.keys()):
            if not (self.path / tracked_path).exists():
                del index[tracked_path]
                missing_file += 1
                print(f"Removed missing file {tracked_path} from the index")

        if missing_file > 0:
            print(f"Removed {missing_file} missing files from index")

        self._save_index(index)
        print(f"Added {added_count} files from {path} to the index")

    def _rm_file(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")
        rel_path = full_path.relative_to(self.path)
        index = self._load_index()
        if rel_path.as_posix() not in index:
            print(f"{path} is not tracked by Kram")
            return
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
        index = self._load_index()
        if not full_path.exists():
            if path in index:
                del index[path]
                print(f"Removed missing file {path} from the index")
                self._save_index(index)
                return
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
        for file_path, entry in index.items():
            # handle both old string index and new dict index
            blob_hash = entry["hash"] if isinstance(entry, dict) else entry
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

    def _log_commit_reset(self, current_branch: str, action:str, message: str, author: str, current_commit_hash: str, previous_commit_hash: str = "*"):
        log_file = self.logs_heads_dir / current_branch
        with log_file.open("a") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {action}:  {previous_commit_hash} -> {current_commit_hash}   author: {author}   message: {message}\n")

    def _log_merge(self, to_branch: str, from_branch: str, to_commit: str, new_commit: str, message: str, author: str = "Kram User", from_commit: str = "*" ):
        log_file = self.logs_heads_dir / to_branch
        with log_file.open("a") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} merge::  {from_branch}:{from_commit} -> {to_branch}:{to_commit} = {new_commit}   author: {author}   message: {message}\n")

    def commit(self, message: str, author: str = "Kram User", additional_parents: list[str] = None):
        # create a tree object from the index (staging area)
        tree_hash = self._create_tree_from_index()

        current_branch = self.get_current_branch()
        parent_commit = self.get_branch_commit(current_branch)
        parent_hashes = [parent_commit] if parent_commit else []
        if additional_parents:
            parent_hashes.extend(additional_parents)

        index = self._load_index()

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

        self._log_commit_reset(current_branch, "commit", message, author,commit_hash, (parent_commit or "*"))
        print(f"Created commit {commit_hash} on branch {current_branch}")
        return commit_hash

    def get_files_from_tree_recursive(self, tree_hash: str, prefix: str = ""):
        files = set()
        try:
            tree_obj = self._load_object(tree_hash)
            tree_data = Tree._deserialize_entries(tree_obj.content)
            for mode, name, obj_hash in tree_data.entries:
                full_name = f"{prefix}{name}"
                if mode.startswith("100"):
                    files.add(full_name)
                elif mode.startswith("400"):
                    files.update(
                        self.get_files_from_tree_recursive(obj_hash, full_name)
                    )
        except Exception as e:
            print(f"Warning: Could not load tree {tree_hash}: {e}")
        return files

    def _clear_files(self, files_to_clear: set[str]):
        # remove files from previous branch
        if files_to_clear:
            for rel_path in sorted(files_to_clear):
                file_path = self.path / rel_path
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        # clear ghost folders
                        parent = file_path.parent
                        while parent != self.path:
                            if not any(parent.iterdir()):
                                parent.rmdir()
                                parent = parent.parent
                            else:
                                break
                except Exception as e:
                    print(f"Warning: Could not remove file {file_path}: {e}")

    def _restore_working_directory(
        self, files_to_clear: set[str], target_commit_hash: str
    ):
        current_index = self._load_index()
        target_commit_obj = self._load_object(target_commit_hash)
        target_commit_data = Commit._deserialize_commit(target_commit_obj.content)
        target_files = self._get_tree_files_dict(target_commit_data.tree_hash)

        to_delete = set(current_index.keys()) - set(target_files.keys())
        self._clear_files(to_delete)

        for rel_path, blob_hash in target_files.items():
            current_entry = current_index.get(rel_path, {})
            current_hash = current_entry.get("hash") if isinstance(current_entry, dict) else current_entry
            if current_hash != blob_hash:
                file_path = self.path / rel_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                blob_obj = self._load_object(blob_hash)
                file_path.write_bytes(blob_obj.content)

        new_index = self._get_index_from_tree_recursive(
            target_commit_data.tree_hash, self.path
        )
        self._save_index(new_index)

    def _get_index_from_tree_recursive(self, tree_hash: str, path: Path):
        index = {}
        try:
            tree_obj = self._load_object(tree_hash)
            tree_data = Tree._deserialize_entries(tree_obj.content)
            for mode, name, obj_hash in tree_data.entries:
                file_path = path / name
                if mode.startswith("100"):
                    # Record metadata from the restored file for faster status checks
                    rel_path = file_path.relative_to(self.path).as_posix()
                    entry = {
                        "hash": obj_hash,
                        "size": 0,
                        "mtime": 0,
                    }
                    if file_path.exists():
                        stat = file_path.stat()
                        entry["size"] = stat.st_size
                        entry["mtime"] = stat.st_mtime

                    index[rel_path] = entry
                elif mode.startswith("400"):
                    index.update(
                        self._get_index_from_tree_recursive(obj_hash, file_path)
                    )
        except Exception as e:
            print(f"Warning: Could not load tree {tree_hash}: {e}")
        return index

    def _restore_tree_recursive(self, tree_hash: str, path: Path):
        try:
            tree_obj = self._load_object(tree_hash)
            tree_data = Tree._deserialize_entries(tree_obj.content)

            for mode, name, obj_hash in tree_data.entries:
                file_path = path / name
                if mode.startswith("100"):
                    blob_obj = self._load_object(obj_hash)
                    blob = Blob(blob_obj.content)
                    file_path.write_bytes(blob.content)
                elif mode.startswith("400"):
                    file_path.mkdir(exist_ok=True)
                    self._restore_tree_recursive(obj_hash, file_path)
        except Exception as e:
            print(f"Warning: Could not load tree {tree_hash}: {e}")

    def _get_files_set_from_index(self):
        index = self._load_index()
        return set(index.keys())

    def _get_tree_files_dict(self, tree_hash: str, prefix: str = "") -> dict[str, str]:
        files = {}
        tree_obj = self._load_object(tree_hash)
        tree_data = Tree._deserialize_entries(tree_obj.content)
        for mode, name, obj_hash in tree_data.entries:
            full_name = f"{prefix}{name}"
            full_path = Path(full_name)
            if mode.startswith("100"):
                files[full_path.as_posix()] = obj_hash
            elif mode.startswith("400"):
                files.update(self._get_tree_files_dict(obj_hash, f"{full_name}/"))
        return files

    def checkout(self, branch: str, create_branch: bool = False):
        # get previous branch latest commit
        previous_branch = self.get_current_branch()
        previous_commit_hash = self.get_branch_commit(previous_branch)
        files_to_clear = self._get_files_set_from_index()
        if previous_branch == branch:
            print(f"Already on branch {branch}")
            return
        # manage branch
        branch_file = self.heads_dir / branch
        if not branch_file.exists():
            if create_branch:
                if previous_commit_hash:
                    self.set_branch_commit(
                        current_branch=branch, commit_hash=previous_commit_hash
                    )
                    print(f"Created new branch {branch}")
                else:
                    print("No commits yet, cannot create branch")
                    return
            else:
                print(f"Branch '{branch}' does not exist")
                print(f"Use -b flag to create new branch")
                return
        self.head_file.write_text(f"ref: refs/heads/{branch}\n")

        # restore working directory
        if not create_branch:
            target_commit_hash = self.get_branch_commit(branch)
            self._restore_working_directory(files_to_clear, target_commit_hash)
        print(f"Switched to branch {branch}")

    def branch(self, branch_name: str, delete: bool = False):
        current_branch = self.get_current_branch()
        if delete and branch_name:
            branch_file = self.heads_dir / branch_name
            if branch_file.exists():
                if branch_name == current_branch:
                    print(
                        f"Branch '{branch_name}' is the current branch. Checkout to another branch first."
                    )
                    return
                if branch_name == "main":
                    print(f"Branch '{branch_name}' cannot be deleted")
                    return
                branch_file.unlink()
                print(f"Deleted branch {branch_name}")
            else:
                print(f"Branch '{branch_name}' does not exist")
            return
        else:
            current_branch = self.get_current_branch()
            if branch_name:
                branch_file = self.heads_dir / branch_name
                if branch_file.exists():
                    print(f"Branch '{branch_name}' already exists")
                    return
                current_branch_commit = self.get_branch_commit(current_branch)
                if current_branch_commit:
                    self.set_branch_commit(branch_name, current_branch_commit)
                    print(f"Created new branch {branch_name}")
                else:
                    print("No commits yet, cannot create branch")
            else:
                branches = self.heads_dir.iterdir()
                for branch in branches:
                    current_marker = "*" if branch.name == current_branch else " "
                    print(f"{branch.name}{current_marker}")

    def log(self, max_count: int = 10):
        current_branch = self.get_current_branch()
        current_branch_commit = self.get_branch_commit(current_branch)

        if not current_branch_commit:
            print("No commits yet")
            return

        count = 0
        while current_branch_commit and count < max_count:
            commit_obj = self._load_object(current_branch_commit)
            commit_data = Commit._deserialize_commit(commit_obj.content)
            print(f"Commit: {current_branch_commit}")
            print(f"Message: {commit_data.message}")
            print(f"Author: {commit_data.author}")
            print(f"Date: {commit_data.timestamp}")
            print()
            current_branch_commit = (
                commit_data.parent_hashes[0] if commit_data.parent_hashes else None
            )
            count += 1

    def _get_all_files(self):
        files = []
        for file in self.path.rglob("*"):
            if file.is_file() and not self._should_ignore(file, self._ignore_patterns):
                files.append(file.relative_to(self.path).as_posix())
        return files

    def status(self):
        current_branch = self.get_current_branch()
        print(f"On branch {current_branch}")
        index = self._load_index()
        all_files = self._get_all_files()
        current_commit = self.get_branch_commit(current_branch)
        new_files = []
        modified_files = []
        unstaged_files = []
        untracked_files = []
        unstaged_deleted_files = []
        staged_deleted_files = []

        last_index = {}
        if current_commit:
            try:
                commit_obj = self._load_object(current_commit)
                commit_data = Commit._deserialize_commit(commit_obj.content)
                last_index = self._get_index_from_tree_recursive(
                    commit_data.tree_hash, self.path
                )
            except Exception as e:
                print(f"Warning: Could not load last commit: {e}")

        # Compare Index vs Last Commit (or empty)
        # Compare Index vs Last Commit (or empty)
        for file_path, entry in index.items():
            if isinstance(entry, dict):
                file_hash = entry["hash"]
                cached_size = entry["size"]
                cached_mtime = entry["mtime"]
            else:
                file_hash = entry
                cached_size = 0
                cached_mtime = 0

            full_path = self.path / file_path
            if file_path not in last_index:
                new_files.append(file_path)
            elif last_index[file_path]["hash"] != file_hash:
                modified_files.append(file_path)
            if full_path.exists():
                stat = full_path.stat()
                # FAST PATH: if size and mtime match, skip hashing
                if stat.st_size == cached_size and stat.st_mtime == cached_mtime:
                    continue

                content = full_path.read_bytes()
                current_hash = Blob(content).hash_object()
                if current_hash != file_hash:
                    unstaged_files.append(file_path)
            else:
                unstaged_deleted_files.append(file_path)
        
        # Compare Last Commit vs Working Directory
        for file_path, entry in last_index.items():
            if file_path not in index:
                staged_deleted_files.append(file_path)

        if new_files or modified_files or staged_deleted_files:
            print("\nChanges to be committed:")
            for file_path in new_files:
                print(f"   New file: {file_path}")
            for file_path in modified_files:
                print(f"   Modified file: {file_path}")
            for file_path in staged_deleted_files:
                print(f"   Deleted file: {file_path}")
        elif not current_commit and not index:
            print("\nNo commits yet. Nothing staged.")
        else:
            print("\nNo changes to commit. Branch up to date.")

        if unstaged_files or unstaged_deleted_files:
            print("\nChanges not staged for commit:")
            for file_path in unstaged_files:
                print(f"   Modified file: {file_path}")
            for file_path in unstaged_deleted_files:
                print(f"   Deleted file: {file_path}")
            

        # untracked files
        for file in all_files:
            if file not in index:
                untracked_files.append(file)
        if untracked_files:
            print("\nUntracked files:")
            for file_path in untracked_files:
                print(f"   Untracked file: {file_path}")


    def revert(self, commit_hash: str):
        # get current branch
        current_branch = self.get_current_branch()
        try:
            commit_obj = self._load_object(commit_hash)
            if commit_obj.obj_type != "commit":
                print(
                    f"Error: Object {commit_hash} is a {commit_obj.obj_type}, not a commit."
                )
        except Exception as e:
            print(f"Commit not found")
            return
        # delete current files
        files_to_clear = self._get_files_set_from_index()
        # restore previous commit stage
        self._restore_working_directory(files_to_clear, commit_hash)
        print(f"Reverted to commit {commit_hash}. Changes staged for commit.")

    def reset(self, commit_hash: str, message: str, author: str = "Kram User"):
        # get current branch
        current_branch = self.get_current_branch()
        parent_commit = self.get_branch_commit(current_branch)
        try:
            commit_obj = self._load_object(commit_hash)
            if commit_obj.obj_type != "commit":
                print(
                    f"Error: Object {commit_hash} is a {commit_obj.obj_type}, not a commit."
                )
                return 
        except Exception as e:
            print(f"Commit not found")
            return
        # delete current files_
        files_to_clear = self._get_files_set_from_index()
        # restore previous commit stage
        self._restore_working_directory(files_to_clear, commit_hash)
        self.set_branch_commit(current_branch, commit_hash)
        self._log_commit_reset(current_branch, "reset", message, author, commit_hash, (parent_commit or "*"))
        print(f"Reset to commit {commit_hash}. Branch {current_branch} updated. {author}: {message}")

    def reflog(self):
        branch = self.get_current_branch()
        log_file = self.logs_heads_dir / branch
        if not log_file.exists():
            print(f"No reflog found for branch {branch}")
            return
        print(f"Reflog for branch {branch}:\n")
        with log_file.open("r") as f:
            for line in reversed(list(f)):
                print(line.strip())

    def _find_merge_base(self, commit1_hash: str, commit2_hash: str) -> str:
        if not commit1_hash or not commit2_hash:
            return None
            
        def get_ancestors(commit_hash):
            ancestors = set()
            queue = [commit_hash]
            while queue:
                curr = queue.pop(0)
                if curr not in ancestors:
                    ancestors.add(curr)
                    try:
                        obj = self._load_object(curr)
                        data = Commit._deserialize_commit(obj.content)
                        queue.extend(data.parent_hashes)
                    except:
                        pass
            return ancestors

        ancestors1 = get_ancestors(commit1_hash)
        
        # Walk back from commit2 and find first shared ancestor
        queue = [commit2_hash]
        visited = set()
        while queue:
            curr = queue.pop(0)
            if curr in ancestors1:
                return curr
            if curr not in visited:
                visited.add(curr)
                try:
                    obj = self._load_object(curr)
                    data = Commit._deserialize_commit(obj.content)
                    queue.extend(data.parent_hashes)
                except:
                    pass
        return None

    def merge(self, branch: str, message: str, author: str = "Kram User", override: bool = False):
        current_branch = self.get_current_branch()
        to_commit_hash = self.get_branch_commit(current_branch)
        from_commit_hash = self.get_branch_commit(branch)

        if not from_commit_hash:
            print(f"Branch '{branch}' not found or has no commits.")
            return

        if not to_commit_hash:
            print("Current branch has no commits. Taking everything from source branch.")
            self._restore_working_directory(set(), from_commit_hash)
            self.set_branch_commit(current_branch, from_commit_hash)
            return

        base_commit_hash = self._find_merge_base(to_commit_hash, from_commit_hash)
        
        if not base_commit_hash:
            print("No common ancestor found. Performing unrelated histories merge (taking source).")
            base_tree = {}
        else:
            base_obj = self._load_object(base_commit_hash)
            base_data = Commit._deserialize_commit(base_obj.content)
            base_tree = self._get_tree_files_dict(base_data.tree_hash)

        if base_commit_hash == from_commit_hash:
            print(f"Already up to date.")
            return
        
        if base_commit_hash == to_commit_hash:
            print(f"Fast-forwarding to {from_commit_hash}")
            self._restore_working_directory(self._get_files_set_from_index(), from_commit_hash)
            self.set_branch_commit(current_branch, from_commit_hash)
            return

        # 3-way merge
        to_obj = self._load_object(to_commit_hash)
        to_data = Commit._deserialize_commit(to_obj.content)
        to_tree = self._get_tree_files_dict(to_data.tree_hash)

        from_obj = self._load_object(from_commit_hash)
        from_data = Commit._deserialize_commit(from_obj.content)
        from_tree = self._get_tree_files_dict(from_data.tree_hash)

        all_files = set(base_tree.keys()) | set(to_tree.keys()) | set(from_tree.keys())
        
        index = self._load_index()
        conflicts = []
        files_to_restore = {}
        files_to_delete = []

        for file_path in all_files:
            b = base_tree.get(file_path)
            t = to_tree.get(file_path)
            f = from_tree.get(file_path)

            if f == t:
                # Both match, or both deleted. No action needed.
                continue
            
            if f == b:
                # No change in source. Keep current (t).
                continue
                
            if t == b:
                # Source changed it, we didn't. Take source (f).
                if f:
                    files_to_restore[file_path] = f
                else:
                    files_to_delete.append(file_path)
                continue
            
            # Both changed and are different
            if override:
                print(f"Conflict in {file_path}, overriding with branch {branch}")
                if f:
                    files_to_restore[file_path] = f
                else:
                    files_to_delete.append(file_path)
            else:
                print(f"CONFLICT in {file_path}")
                conflicts.append(file_path)

        if conflicts:
            print("Merge aborted due to conflicts. Use --override to force merge.")
            return

        # Apply changes
        for file_path in files_to_delete:
            if file_path in index:
                del index[file_path]
            p = self.path / file_path
            if p.exists():
                p.unlink()

        for file_path, blob_hash in files_to_restore.items():
            full_path = self.path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            blob_obj = self._load_object(blob_hash)
            full_path.write_bytes(blob_obj.content)
            
            stat = full_path.stat()
            index[file_path] = {
                "hash": blob_hash,
                "size": stat.st_size,
                "mtime": stat.st_mtime
            }

        self._save_index(index)
        print(f"Successfully Merged branch {branch} into {current_branch}")
        new_commit = self.commit(message, author, additional_parents=[from_commit_hash])
        self._log_merge(from_branch=branch, to_branch=current_branch, from_commit=from_commit_hash, to_commit=to_commit_hash, new_commit=new_commit, message=message, author=author )

        
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
        patterns = {".kram"}  # Hardcoded safety
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
