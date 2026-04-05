import argparse
import sys
from pathlib import Path
import json
import ctypes
import platform
from repository import Repository


def main():
    parser = argparse.ArgumentParser(description="Kram - A version control system!")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new Kram repository")
    # add command
    add_parser = subparsers.add_parser("add", help="Add file to the staging area")
    add_parser.add_argument(
        "paths", nargs="+", help="Paths to files to add"
    )  # nargs = + implies atleast one file is needed

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    repo = Repository()
    try:
        if args.command == "init":
            if not repo.init():
                print("Kram repository already exists.")
                return
        elif args.command == "add":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            for path in args.paths:
                repo.add_path(path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(args)


main()
