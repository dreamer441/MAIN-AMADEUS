# Project File Reader - Future Updates

## Near-term improvements

- Add exact search within files, for example finding every occurrence of a class or function name.
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

- Add line-range syntax to `[file]` annotations using the existing verified range reader.
- Add safe search inside module files without loading every file into the prompt.
- Add a verified-file reference object so `[current][last_file]` can reuse opened file content without relying on chat history truncation.
- Add modified-time metadata and human-readable size formatting.
- Add optional recursive tree expansion depth limits for very large projects.
