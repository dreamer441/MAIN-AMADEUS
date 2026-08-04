# Module Metadata Annotation Design

## Purpose

Give AMADEUS a first-class, read-only way to retrieve the `FEATURES.md` and
`FUTURE_UPDATES.md` metadata maintained in every module folder. The feature
must work through an explicit annotation and through bounded Inner Brain
inference in general AMADEUS chat. It must not run in Flow Chat.

## Scope

The feature reads only the two fixed metadata files in verified top-level
module folders. It displays the exact selected Markdown text in the existing
Memory side-panel tab. It does not write files, save memory, alter module
metadata, or add a new side-panel tab.

## Architecture

### Metadata Reader

`project_file_reader` will expose a small public metadata-reading API. It
will use the existing verified module index and its safe project-root
boundaries rather than letting Core or annotations inspect the filesystem.

The API accepts:

- a module selection: every verified module or one verified module name;
- a document selection: `features`, `future`, or `both`.

It reads only `FEATURES.md` and `FUTURE_UPDATES.md`, orders results by module
name and then filename, labels every returned section with its source, and
reports missing files without inventing content. A bounded aggregate size
limit prevents an all-module request from producing unbounded context or UI
payloads.

### Explicit Annotation

`annotation_module` will register a read-only `[metadata]` annotation. Its
handler asks the metadata reader for content and returns a Memory panel
payload. The payload opts out of normal chat-context prepending so the Memory
tab displays the selected file text exactly, with the reader's source labels
and result summary.

The existing annotation suggestion service will provide the guided stages:

1. `[metadata][all]` or `[metadata][module]`.
2. For `all`, choose `[features]`, `[future]`, or `[both]`.
3. For `module`, choose a real verified module name.
4. Choose `[features]`, `[future]`, or `[both]`.

The existing popup continues to own Up/Down arrow navigation, Tab/Enter
selection, Escape dismissal, and insertion. No special keyboard behavior is
added to the GUI.

### General Chat Inference

The Inner Brain schema gains one constrained read intent:
`module_metadata`. Its validated fields state only:

- whether to select all modules or one validated module;
- whether to read features, future updates, or both;
- whether the user asked to `open` source text or `answer` a question using
  the text.

Core validates every inferred field before use. A module name that is absent
from the verified index is rejected or safely falls back to an all-module
selection only where the inferred request explicitly selected all modules.
The model never supplies paths, arbitrary filenames, shell commands, or
unvalidated identifiers.

Inference occurs only for plain messages entering the general AMADEUS chat
route. Explicit annotations bypass inference. Flow Chat keeps its existing
route and does not call this metadata inference.

For `open`, Core executes the same annotation handler path and returns its
Memory panel payload. For `answer`, Core loads the same bounded metadata as
callable context, sends the original question to the normal chat module, and
returns the answer together with the same Memory panel payload.

## Error Handling

- An invalid annotation shape returns concise usage instructions.
- A module not present in the verified index returns available module guidance.
- Missing metadata files are shown in the result summary; valid files still
  render.
- Empty results return a clear no-metadata response and a valid Memory panel
  payload.
- Reader or model failures produce safe empty/no-context behavior and do not
  execute writes.

## Testing

Focused tests will cover:

- verified selection, ordering, fixed-file enforcement, missing files, and
  aggregate bounds in the metadata reader;
- annotation parsing, handler output, and staged suggestions;
- Memory-tab rendering without chat-context prepending;
- Inner Brain schema validation and general-chat inferred `open` and `answer`
  behavior;
- explicit annotation bypass and Flow Chat exclusion.

## Non-Goals

- Editing metadata files through AMADEUS.
- Persisting metadata as user memory.
- Reading arbitrary Markdown or nested module files.
- Changing current Flow Chat behavior.
