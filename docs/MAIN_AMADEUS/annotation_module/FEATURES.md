# Annotation Module Features

- Parses leading bracket annotations such as `[file]`.
- Supports one annotation per user message.
- Supports annotation arguments such as `[file][amadeus_core]`.
- Normalizes arguments such as `[file][amadeus core]` into `amadeus_core`.
- Registers annotation handlers by name.
- Routes `[file]` to the File Annotation handler.
