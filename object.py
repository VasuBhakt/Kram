import hashlib
import zlib
import time


class KramObject:
    def __init__(self, obj_type: str, content: bytes):
        self.obj_type = obj_type
        self.content = content

    # for creating file location
    def hash_object(self) -> str:
        # <type> <size>\0<content>
        header = f"{self.obj_type} {len(self.content)}\0".encode()
        return hashlib.sha256(header + self.content).hexdigest()

    # for data compression
    def serialize(self) -> bytes:
        header = f"{self.obj_type} {len(self.content)}\0".encode()
        return zlib.compress(header + self.content)

    @classmethod
    def deserialize(cls, data: bytes) -> "KramObject":
        decompressed = zlib.decompress(data)
        null_idx = decompressed.find(b"\0")
        header = decompressed[:null_idx].decode()
        content = decompressed[null_idx + 1 :]
        obj_type, _ = header.split(" ")
        return cls(obj_type, content)


# Binary large object
class Blob(KramObject):
    def __init__(self, content: bytes):
        super().__init__("blob", content)

    def get_content(self) -> bytes:
        return self.content


class Tree(KramObject):
    def __init__(self, entries: list[tuple[str, str, str]] = None):
        self.entries = entries or []
        content = self._serialize_entries()
        super().__init__("tree", content)

    def _serialize_entries(self) -> bytes:
        # <mode> <name>\0<hash>
        content = b""
        for mode, name, obj_hash in sorted(self.entries):
            content += f"{mode} {name}\0".encode()
            content += bytes.fromhex(
                obj_hash
            )  # because hash is stored in hex format using hexdigest()
        return content

    def add_entry(self, mode: str, name: str, obj_hash: str):
        self.entries.append((mode, name, obj_hash))
        self.content = self._serialize_entries()

    @classmethod
    def _deserialize_entries(cls, content: bytes) -> "Tree":
        tree = cls()
        i = 0
        while i < len(content):
            null_idx = content.find(b"\0", i)
            if null_idx == -1:
                break
            mode_name = content[i:null_idx].decode()
            mode, name = mode_name.split(" ", 1)
            obj_hash = content[
                null_idx + 1 : null_idx + 33
            ].hex()  # start+32 becase sha256 has 32 bytes
            tree.entries.append((mode, name, obj_hash))
            i = null_idx + 33
        return tree


class Commit(KramObject):
    def __init__(
        self,
        tree_hash: str,
        parent_hashes: list[str],
        author: str,
        committer: str,
        message: str,
        timestamp: int = None,
    ):
        self.tree_hash = tree_hash
        self.parent_hashes = parent_hashes
        self.author = author
        self.committer = committer
        self.message = message
        self.timestamp = timestamp or int(time.time())

        content = self._serialize_commit()
        super().__init__("commit", content)

    def _serialize_commit(self):
        lines = [f"tree {self.tree_hash}"]
        for parent in self.parent_hashes:
            lines.append(f"parent {parent}")

        lines.append(f"author {self.author} {self.timestamp} +0000")
        lines.append(f"committer {self.committer} {self.timestamp} +0000")
        lines.append("")
        lines.append(self.message)

        return "\n".join(lines).encode()

    @classmethod
    def _deserialize_commit(cls, content: bytes) -> "Commit":
        lines = content.decode().split("\n")
        tree_hash = None
        parent_hashes = []
        author = None
        committer = None
        message_start = 0

        for i, line in enumerate(lines):
            if line.startswith("tree "):
                tree_hash = line[5:]
            elif line.startswith("parent "):
                parent_hashes.append(line[7:])
            elif line.startswith("author "):
                author_parts = line[7:].rsplit(" ", 2)
                author = author_parts[0]
                timestamp = int(author_parts[1])
            elif line.startswith("committer "):
                committer_parts = line[10:].rsplit(" ", 2)
                committer = committer_parts[0]
                timestamp = int(committer_parts[1])
            elif line == "":
                message_start = i + 1
                break
        message = "\n".join(lines[message_start:])
        commit = Commit(tree_hash, parent_hashes, author, committer, message, timestamp)
        return commit
