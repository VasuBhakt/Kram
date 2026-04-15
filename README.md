# Kram 🐙

A functional version control system built from scratch in Python.

**Kram** is a functional VCS that uses a content-addressable storage system (Blobs, Trees, and Commits) similar to Git. It features a staging area (Index) and a performance-optimized status engine using file metadata caching.

## ✨ Features

- **Efficient Storage**: Uses SHA-256 hashing and `zlib` compression for all objects.
- **Metadata Caching**: Fast `status` command that skips hashing for unchanged files.
- **Branching**: Create, switch, and manage multiple lines of development.
- **Content-Addressable**: Implements the core architecture of modern version control.

## 🚀 Installation

To install Kram locally and use it as a command-line tool:

1. Clone this repository.
2. Navigate to the project root.
3. Install using pip:
   ```bash
   pip install -e .
   ```

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

## 🏗️ Architecture

Kram follows the following object model:

- **Blob**: Binary Large Object stores the file content.
- **Tree**: Stores directory structure and links names to Blobs/Sub-trees.
- **Commit**: Stores a snapshot of a Tree, parent commit hashes, author, and message.
- **Index**: A staging area that stores the target state for the next commit, optimized with file size and mtime metadata.

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

The inspiration for the name of this project comes from the Sanskrit word ***krama***, which means Order.
