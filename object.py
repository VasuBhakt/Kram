import hashlib
import zlib


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
        header = decompressed[:null_idx]
        content = decompressed[null_idx + 1 :]
        obj_type, _ = header.split(" ")
        return cls(obj_type, content)


# Binary large object
class Blob(KramObject):
    def __init__(self, content: bytes):
        super().__init__("blob", content)

    def get_content(self) -> bytes:
        return self.content
