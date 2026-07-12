# Project File Reader

Project File Reader is AMADEUS's read-only project inspection module.

Its job is to provide verified local filesystem facts to Core, annotations, and future GUI tools. It should answer questions like:

- What modules exist?
- What files are inside a module folder?
- What is the exact content of one safe text file?
- What is the exact first line or exact line count of a safe text file?

This module is intentionally strict. If it cannot verify a file, folder, line, or line count from the real local filesystem, it should say so instead of guessing.

## Safety boundary

Project File Reader may read safe project text files only. It must not edit files, delete files, run code, or inspect arbitrary private folders.

## Why this module matters

Dato already found that AMADEUS could list files correctly after the first patch, but still guessed file content and line counts. This module now includes direct line reading and line counting so those answers come from Python filesystem reads, not from model memory.

## Exact File Access Boundary

Project File Reader is used by `[file]` for verified filesystem operations. It can list folders/files inside documented modules and read safe text files. Exact reads are returned to the GUI Code Viewer, while normal chat only receives overview context for summaries.
