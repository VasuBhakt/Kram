import argparse
import sys
from pathlib import Path
import json
import ctypes
import platform


class Repository:
    def __init__(self, path="."):
        self.path = Path(path).resolve()  # git init
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
        # directories
        self.kram_dir.mkdir()
        # hide the directory
        if platform.system() == "Windows":
            # 0x02 is the hex code for the 'Hidden' attribute in Windows
            ctypes.windll.kernel32.SetFileAttributesW(str(self.kram_dir), 0x02)
        self.objects_dir.mkdir()
        self.refs_dir.mkdir()
        self.heads_dir.mkdir()

        # create initial HEAD  pointing to a branch
        self.head_file.write_text("ref: refs/heads/main\n")
        # create initial index
        self.index_file.write_text(json.dumps({}, indent=2))

        print(f"Initialized empty Kram repository in {self.kram_dir}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Kram - A version control system!")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new Kram repository")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    try:
        if args.command == "init":
            repo = Repository()
            if not repo.init():
                print("Kram repository already exists.")
                return
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(args)


main()
