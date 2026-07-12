# Project File Reader - Current Features

## Purpose
Project File Reader is AMADEUS's read-only filesystem truth boundary for the current project. It exists so AMADEUS can verify files and folders from the real local project instead of guessing from the LLM.

## Implemented features

- Lists readable AMADEUS module folders from the real local filesystem.
- Reads required module tracking docs:
  - `README.md`
  - `FEATURES.md`
  - `FUTURE_UPDATES.md`
- Lists exact direct files inside a module folder, including `.py` and `.md` files.
- Reads exact safe text file content from a verified module file.
- Reads one exact line from a verified module file, for example the first line of `identity_charter.py`.
- Counts exact logical lines in a verified module file using Python, not the LLM.
- Resolves a uniquely named file across modules when the user mentions only the filename in a follow-up.
- Refuses to guess when a module, file, line, or folder cannot be verified.
- Returns exact available files when the requested file does not exist.
- Blocks unsafe path traversal and unsupported file types.
- Supports deterministic natural-language file requests through `FileRequestRouter` before normal chat.
- Supports deterministic `[file]` annotation inspection for module docs, file lists, file content, line reads, and line counts.

## Current accepted examples

```text
list all files in identity module
open the identity module folder and list all files
what is the first line of identity_charter.py
what is line 12 of identity_charter.py
how many lines are in identity_charter.py
[file][identity_module][files]
[file][identity_module] read README.md
[file][identity_module] first line identity_charter.py
[file][identity_module] how many lines identity_charter.py
```

## Accuracy rule

For file/folder/content questions, AMADEUS must answer from Project File Reader output or say she cannot verify the answer. She must not invent filenames, first lines, line counts, or file contents.

## File Annotation Access v2

- Project File Reader can now list both direct folders and direct files inside a module path.
- Subfolders such as `annotation_module/annotations/` are visible through `[file][annotation_module]` and selectable through suggestions.
- File reads preserve exact visible text without trimming the final character or newline.
- Full-file reads are intended for Code Viewer side-panel display, not main chat dumping.
- Normal chat now receives only compact overview context for summaries/explanations; exact read operations should use `[file]`.
