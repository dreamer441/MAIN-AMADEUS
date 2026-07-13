# Annotation Module - Future Updates

## Planned improvements

- Add autocomplete support for registered annotations in the GUI.
- Add validation messages when an annotation exists but arguments are missing or malformed.
- Add exact line-range support once Project File Reader supports it.
- Add annotation help output such as `[help][file]` or `[annotations]`.
- Add structured return payloads so Process Monitor can show annotation-specific metadata.
- Add tests for more natural language inside annotation content and malformed embedded brackets.

## Boundary

Annotations should stay deterministic command routes. They should not become a place for hidden reasoning, fake thoughts, or unrestricted project actions.

## Future Annotation System Improvements

- [x] Add keyboard navigation for the suggestion popup: arrow keys, Enter/Tab to accept, Esc to close.
- Add per-annotation block result types so callable context can preserve structured provenance instead of text alone.
- Add annotation-specific flows for `[task]`, `[current]`, `[panel]`, and future modules.
- Add `[current][last_file]` so AMADEUS can refer to the last verified file opened in Code Viewer.
- Add `[panel]` to inject current visible panel context into the main prompt when Dato explicitly requests it.
- Add richer `[file]` subcommands for line ranges, counts, summaries, and search inside an opened file.

## Memory Annotation Future Updates

- Add `[memory][delete][id]`.
- Add `[memory][update][id] new text`.
- Add `[memory][module]` for module-specific memory.
- Add confirmation flow if AMADEUS suggests saving memory herself.

## Sheets / Export Annotation Roadmap

- [x] Add `[sheet]` top-level annotation.
- [x] Add guided suggestions for sheet scope and visible titles.
- [ ] Add `[export][chat name]` annotation.
- [ ] Add `[export][chat name][4-6]` message-number segment injection.
- [ ] Add `[panel]` annotation for current right-panel context.
- [ ] Add `[current][message_number]` annotation for exact message references.

## Export Annotation Future

- [ ] Add richer export range picker suggestions based on actual message numbers.
- [ ] Add `[export][selected]` once chat text selection is tracked.
- [ ] Add annotation paths for export deletion/archive after permissions are clearer.

## Export Annotation Future Work

- [x] Add clearer `[export][open]` and `[export][use]` paths.
- [x] Keep shorthand export annotation compatibility.
- [ ] Add keyboard-friendly range builder for export annotations.
- [ ] Add Materials-panel controls that generate export annotations automatically.

## File Annotation Context

- [x] Let Code Viewer context select one exact line (`15`) or an inclusive range (`15-30`).
