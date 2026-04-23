# Kram 🐙

A functional version control system built from scratch in Python.

**Kram** is a functional VCS that uses a content-addressable storage system (Blobs, Trees, and Commits) similar to Git.

## ✨ Features

- **Efficient Storage**: Uses SHA-256 hashing and `zlib` compression for all objects.
- **Metadata Caching**: Fast `status` command that skips hashing for unchanged files.
- **Branching**: Create, switch, and manage multiple lines of development.
- **Content-Addressable**: Implements the core architecture of modern version control.
- **3-Way Merge**: Intelligent merging of branches using common ancestor detection and conflict handling.
- **History management**: Allows moving back to history commits and provides reference logs.

## ⚙️ Prerequisites

- Python 3.x (Required to run the Kram engine)

## 🌐 Language Support

Kram is language-agnostic and can be used to version control projects in any language (C++, JS, Go, etc.) or even non-code assets (images, videos, etc.)

## 🚀 Installation

To install Kram locally and use it as a command-line tool:

1. Clone this repository.
2. Navigate to the project root.
3. Install using pip:
   ```bash
   pip install -e .
   ```
   Now you can use this globally as a Command-Line Tool!

## 🛠️ Usage

### Initialize a repository

```bash
kram init
```

### Check status

```bash
kram status
```

### Stage files

```bash
kram add <file_path> <folder_path> ...
kram add .   # add all files to the staging area
kram rm <file_path>  # remove file_path from staging area
```

### Commit changes

```bash
kram commit -m "Your commit message" --author "Author Name" # Author name is optional
```

### Branching

```bash
kram branch <new_branch_name>  # Create
kram checkout <branch_name>    # Switch
kram checkout -b <branch_name> # Create and switch
```

### See History

```bash
kram log -n 10 # Shows last 10 commits optional
```

### Revert to previous commit stage

```bash
kram revert -c <commit_hash> # restore working directory of commit and ONLY STAGES THE CHANGES, does not create new commit
```

### Reset commit

```bash
kram reset -c <commit_hash> -m "Reason for reset" # Head of branch is moved back. While destructive to the current state, previous commits can still be recovered using the reflog.
```

### Commit reference logs

```bash
kram reflog # View history of pointer movements for the current branch. Essential for recovering from accidental resets.
```

### Merging

```bash
kram merge -b <source_branch> -m "Merge message"
kram merge -b <source_branch> -m "Merge message" --override # Force merge in case of conflicts
```

**Use `kram --help` for getting more info on the available commands**

## 🏗️ Architecture

Kram uses a **Content-Addressable Storage (CAS)** model, where every object is identified by its SHA-256 hash.

- **Blob**: Stores the raw bytes of your files.
- **Tree**: Acts as a directory, mapping filenames to Blobs or other Trees.
- **Commit**: A permanent snapshot of the project, pointing to a root Tree and its parent commits.
- **Index**: The staging area that tracks your next commit and caches metadata (`mtime`, `size`) for performance.

**Efficient Storage**: All objects are compressed with `zlib` and sharded into subdirectories (e.g., `.kram/objects/4f/a2...`) to keep the filesystem fast even with millions of files.

---

## 🧬 Technical Deep Dive

### 3-Way Merge Algorithm

Kram employs a recursive 3-way merge algorithm to reconcile divergent histories:

1. **Optimized Ancestor Detection**: Uses a simultaneous backwards-traversal from both branch heads. A **Max-Priority Queue (ordered by UTC timestamps)** ensures the search processes the most recent history first. Commits are tracked via **Reachability Bitmasks**; the first commit popped that is reachable from both heads is identified as the Lowest Common Ancestor (LCA). Complexity is $O(D)$ where $D$ is the distance to the split point.
2. **Three-Way Tree Comparison**: Performs a delta analysis between three states: **Base** (LCA), **Target** (current HEAD), and **Source** (branch to merge).
3. **Resolution Logic**:
    - If `Source == Target`: No conflict, no action required.
    - If `Source == Base`: Change is already reflected or Source is stagnant; keep Target.
    - If `Target == Base`: Target is stagnant; automatically adopt Source.
    - If `Source != Target` and both differ from Base: A **merge conflict** is triggered.

### Merkle DAG Integrity
The repository structure is a **Merkle Directed Acyclic Graph (DAG)**. Since every Tree hash is a cryptographic digest of its children (Blobs or sub-Trees), the Root Tree hash provides a verifiable proof of the entire project state. Any mutation at the leaf level (Blobs) cascades a hash-change up to the Commit, ensuring perfect data integrity and tamper-evidence.

### Performance Optimized Status

The `status` command is designed for speed. Instead of hashing every file every time:

- It caches the `size` and `mtime` (last modified time) in the Index.
- It only performs SHA-256 hashing if the metadata indicates a file has been touched.
- This results in O(1) performance for unchanged files.

### Content-Addressable Storage

Kram uses a partitioned object store (`.kram/objects/ab/cdef...`) to avoid filesystem bottlenecks that occur when thousands of files are stored in a single directory. All files are compressed using `zlib` to minimize the on-disk footprint.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.txt) file for details.

---

## 🏆 Acknowledgements

This project was built as part of a deep-dive learning journey into the architecture of Version Control Systems. Special thanks to :

- <a href="https://github.com/rivaanranawat">Rivaan Ranawat</a> for the amazing video on building a VCS from scratch, which serves as the foundation of this project. The video can be found on his <a href="https://www.youtube.com/rivaanranawat">YouTube channel</a>.

- Academic references from the **Git Internals** documentation.

---

## 🤓 Fun Fact

The inspiration for the name of this project comes from the Sanskrit word **_krama_**, which means Order.
