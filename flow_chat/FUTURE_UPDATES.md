# Flow Chat Future Updates

- Add token-aware Flow history trimming when a shared prompt budget is defined.
- Design explicit user-selected dedicated-chat retrieval only after permissions and content boundaries are defined.
- Add relevance ranking for metadata records without loading dedicated-chat bodies.
- Keep any future persistence changes transactional at the full user/AMADEUS exchange boundary.
- Do not treat Flow's current metadata-only registry as dedicated-chat content access.
- Do not operationalize chat scope until explicit selection, permissions, and content boundaries are designed.
