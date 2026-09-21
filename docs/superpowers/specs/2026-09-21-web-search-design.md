# Web search with Inner Brain context preparation

Date: 2026-09-21
Status: Design for user review; implementation pending.

## Purpose

Add explicit web search to Flow and dedicated Chats. The user requests a search with an annotation. A separate web module retrieves search results, Inner Brain prepares a compact evidence brief, and the primary chat model answers with source references.

## Verified current architecture

- Application composition creates the primary Ollama client and a separate InnerBrainService backed by `nemotron-3-nano:4b`. The primary client's default is `llama3.2:latest`; these are configured defaults, not verified installed models.
- Inner Brain currently exposes `analyze_message` and `analyze_chat`. It requests JSON, validates allowed intent and metadata fields, and returns empty analysis on model or parsing failure.
- Dedicated Chat uses advisory read hints through Context Builder and creation hints through Creation and Permissions. Explicit annotations bypass ordinary intent inference.
- Explicit Chat Data refresh calls Inner Brain for title, description, bullets, and summary. Chat Metadata owns persistence and preserves existing manual title and description.
- Flow's request handler consumes creation hints, but composition sets its inferred-read-context provider to None. The existing Inner Brain FEATURES claim about active inferred read injection in Flow is stale.
- Creation's structured generation and chat-creation metadata resolver currently use the primary LLM client. They are distinct from Inner Brain.
- Inner Brain owns no persistence, network searching, or action execution. Its existing general analysis prompt truncates input at 12,000 characters and requests 500 output tokens. Web preparation needs a separate task contract and budget.

## User syntax

- `/web [] topic or question`: search the text following the empty brackets.
- `/web [topic]`: search the bracketed topic and answer about it.
- `/web topic or question`: convenient equivalent.
- `[web] topic or question`: compatible bracket annotation.
- `/web [topic] question`: search the topic; use the trailing question as the answer request.
- Empty queries return usage guidance without a network or model call.
- Only explicit web commands trigger searching. Ordinary messages and historical commands never initiate a search implicitly.
- Annotation owns parsing and suggestions. A leading web command consumes its own query text literally, so brackets inside a query cannot execute other annotations.

## Responsibilities and request flow

1. Annotation recognizes a web request and returns a typed query and question.
2. The active conversation workflow calls the injected public web-search service.
3. The web module uses a replaceable DDGS adapter, initially a fixed DuckDuckGo backend with no API key, to obtain at most five title, URL, and snippet records. Apply bounded query/result sizes, timeouts, URL validation, and duplicate removal.
4. The web module assigns stable request-local source IDs. Only the explicit query goes to the external search provider; conversation history and memory do not.
5. A dedicated Inner Brain web-context method receives the question and bounded source records. It returns a validated structured brief containing relevant findings with source IDs, gaps, and disagreements.
6. Context Builder formats the brief alongside the original source snippets and the authoritative ID-to-URL mapping. Model-supplied URLs are not accepted. Invalid source IDs or malformed output trigger fallback to the original results.
7. The active conversation workflow asks the primary chat model to answer using the evidence, distinguish uncertainty, and cite supplied source IDs. The response includes a deterministic source list from actual results; formatting must not imply every result supports every claim.
8. Existing conversation owners persist the exchange in the correct history. Core remains a router and application composition wires the services.

The first version uses search snippets, not downloaded full articles. Both the context and user-visible source section identify that limitation. Summarization is not factual verification; retaining source excerpts lets the answering model inspect the underlying evidence.

## Failure and trust behavior

- No results or search failure produces a clear search status, never an answer presented as web verified.
- Inner Brain failure or invalid output falls back to bounded original search results and records that preparation was skipped.
- Primary model failure still makes retrieved sources available with a clear answer-generation failure status.
- External text is explicitly delimited as untrusted evidence, never instructions. Web context cannot authorize writes or call other tools.
- No automatic memory writes or graph creation accompany a search.
- Show real search, preparation, and answer events through Process Monitor. Do not expose raw provider errors or hidden model reasoning.
- Work stays on existing background request workers. Use a finite, shorter timeout for web preparation so a failed secondary model does not inherit the general ten-minute model wait.
- Preserve dedicated-chat response-mode behavior, including suppressing answer generation in No Response mode, and keep Flow history isolated.

## Alternatives considered

- Direct results to primary chat: simpler and faster, retained as the failure fallback.
- Inner Brain preparation followed by primary chat: selected at the user's request; adds an inference call but gives the preparation task a clear contract.
- Dedicated search API: replaceable future provider; introduces credentials and possible costs, so it is outside the initial implementation.

## Verification and documentation

Test command parsing and suggestions; literal brackets and empty input; normalization, deduplication, unsafe URLs, bounded inputs and results; provider failure and no matches; valid and invalid structured briefs; unknown source IDs; secondary and primary model failure; source rendering; explicit-command bypass of ordinary inference; Flow and dedicated-chat isolation; and response modes. Use fake providers and model clients for repeatable tests. Perform a separate live public-query smoke check when dependency and network access allow, and report live-model validation separately from mocked tests.

Update affected module FEATURES and FUTURE_UPDATES, the architecture map, README usage, and AMADEUS_CHANGELOG. Correct the stale Flow inference documentation without changing that unrelated behavior. Run compileall and relevant regression tests, review intended changes, commit only feature paths, and push the current branch under the repository rules.

## Scope limits

No full-page browser, automatic iterative research, image/news-specific search, embedding index, autonomous searching, or changes to existing Creation model routing. DDGS search availability may vary with provider limits. Installed model availability and live model quality remain to be checked during implementation.
