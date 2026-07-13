# Materials Module - Current Features

- Manages UTF-8 text files located under `data/materials/`.
- Lists managed files and existing export records with stable id, name, type, and metadata.
- Provides preview/open payloads without automatic prompt injection.
- Builds strict one-request callable context only after an explicit Use or Ask action.
- Supports copyable references and deliberate removal of managed files or known export records.
- Keeps Materials separate from Sheets, Memory, and Code Viewer.

## Chat Export Integration

- Exported chats are now the first concrete Materials objects.
- Materials composes the Export module public API; export annotations and formats remain compatible.
- Human display uses TXT-style formatting; Markdown and JSON files are stored for future AMADEUS reference/retrieval.
