# Chat Workspace Future Updates

- Replace broad service annotations with narrower protocols as interfaces stabilize. Preserve isolated history and explicit approval semantics.
- Keep metadata refresh all-or-nothing: do not replace a successful analysis with incomplete model output. The synchronous Chat Data refresh remains a candidate for a dedicated background worker.
