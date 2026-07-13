# AMADEUS Materials Module

The Materials module is the foundation for large readable references in AMADEUS.

Materials are different from sheets and memory. They are usually larger source objects such as exported chats, uploaded text files, PDFs, images, or imported information blocks.

## Current status

Materials lists managed UTF-8 files under `data/materials/` and existing chat-export
records through `export_module`. Each row exposes its stable id, name, type, and
metadata without making the item active context.

## Safe use

- Preview and Open are visual actions only.
- Use in Next Message attaches the selected material to exactly one subsequent request.
- Ask AMADEUS sends an explicit selected-material request.
- Copy Ref copies the stable `material:...` or `export:...` identifier.
- Remove requires deliberate GUI confirmation and only handles managed files or known exports.

## Planned role

- Show exported chats and managed files in the right panel.
- Show text/PDF/material references without cluttering main chat.
- Support callable annotation references such as `[export][chat name][4-6]`.
- Feed future Mind Map nodes and links.
