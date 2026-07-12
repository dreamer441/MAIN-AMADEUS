# Project File Reader - Future Updates

## Near-term improvements

- Add recursive tree inspection with depth limits.
- Add exact line-range reads, for example lines 10-30 from a file.
- Add exact search within files, for example finding every occurrence of a class or function name.
- Add file metadata display such as modified time and size in human-readable format.
- Add a small GUI file viewer panel so Dato can inspect verified files visually.
- Add tests for more natural-language phrasing around file reads and line counts.

## Later improvements

- Add safe project-wide search with ignore rules for `.git`, virtual environments, caches, and build folders.
- Add structured file summaries generated only after verified content is loaded.
- Add token-aware truncation for large files.
- Add code-outline extraction for classes/functions without reading unrelated content.
- Add permission-controlled editing later, but only after read-only inspection is reliable.

## Important future rule

Do not add file editing, deletion, autonomy, or unrestricted disk scanning inside this module yet. Project File Reader should stay read-only until AMADEUS has a mature permission system and reversible action logs.

## Future File Reader Improvements

- Add explicit line-range reads such as `[file][module][file.py][lines 1-50]`.
- Add safe search inside module files without loading every file into the prompt.
- Add a verified-file reference object so `[current][last_file]` can reuse opened file content without relying on chat history truncation.
- Add read limits and warnings for very large files before they are sent to Code Viewer.
- Add optional file tree view in the right panel after the Code Viewer foundation is stable.
