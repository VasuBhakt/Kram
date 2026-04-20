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

    # commit command
    commit_parser = subparsers.add_parser(
        "commit", help="Commit changes to the repository"
    )
    commit_parser.add_argument(
        "-m", "--message", help="Message to commit", required=True
    )
    commit_parser.add_argument("-author", help="Commit author details")

    # remove command (rm)
    rm_parser = subparsers.add_parser("rm", help="Remove file from the staging area")
    rm_parser.add_argument(
        "paths", nargs="+", help="Paths to files to remove"
    )  # nargs = + implies atleast one file is needed

    # checkout parser
    checkout_parser = subparsers.add_parser(
        "checkout", help="Move to or create new branch"
    )
    checkout_parser.add_argument(
        "-b",
        "--create-branch",
        action="store_true",
        help="Create and switch to a new branch",
    )
    checkout_parser.add_argument("branch", help="Name of the branch to switch to")

    # branch command
    branch_parser = subparsers.add_parser("branch", help="List or manage branches")
    branch_parser.add_argument(
        "name",
        nargs="?",
        help="If provided, creates a new branch with this name if not exists",
    )
    branch_parser.add_argument(
        "-d", "--delete", action="store_true", help="Delete specified branch"
    )

    # log command
    log_parser = subparsers.add_parser("log", help="Show commit logs")
    log_parser.add_argument(
        "-n",
        "--max-count",
        type=int,
        help="Number of commits to show",
        default=10,
    )

    # status command
    status_parser = subparsers.add_parser(
        "status", help="Show status of the repository"
    )

    # revert command
    revert_parser = subparsers.add_parser(
        "revert",
        help="Revert to previous commits. This will NOT create a new commit, just stage the changes from the particular commit which can then be commited manually.",
    )
    revert_parser.add_argument(
        "--commit", "-c", help="Commit hash to revert to", required=True
    )

    # reset parser
    reset_parser = subparsers.add_parser(
        "reset",
        help="Reset to previous commits. This will HARD RESET the branch to the specified commit. All data commited after specified commit will be lost, SO BE CAUTIOUS. ",
    )
    reset_parser.add_argument(
        "--commit", "-c", help="Commit hash to reset to", required=True
    )
    reset_parser.add_argument(
        "-m", "--message", help="Message to reset", required=True
    )
    reset_parser.add_argument(
        "-a", "--author", help="Author of the reset"
    )

    # reflog parser
    reflog_parser = subparsers.add_parser(
        "reflog", help="Show commit logs and commit history"
    )
    

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
        elif args.command == "commit":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            author = args.author or "Kram User"
            repo.commit(args.message, author)
        elif args.command == "rm":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            for path in args.paths:
                repo.remove_path(path)
        elif args.command == "checkout":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            repo.checkout(args.branch, args.create_branch)
        elif args.command == "branch":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            repo.branch(args.name, args.delete)
        elif args.command == "log":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            repo.log(args.max_count)
        elif args.command == "status":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            repo.status()
        elif args.command == "revert":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            repo.revert(args.commit)
        elif args.command == "reset":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            author = args.author or "Kram User"
            repo.reset(args.commit, args.message, author)
        elif args.command == "reflog":
            if not repo.kram_dir.exists():
                print("Not a kram repository")
                return
            repo.reflog()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(args)


if __name__ == "__main__":
    main()
