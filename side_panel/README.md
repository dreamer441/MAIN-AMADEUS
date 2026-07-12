# AMADEUS Side Panel Module

The Side Panel module defines the structure and runtime state for AMADEUS's right-side workspace panel.

It is intentionally narrow:

- It does **not** read files.
- It does **not** manage memory.
- It does **not** create traces.
- It does **not** summarize chats.

Other modules produce content, and the Side Panel module defines how that content is represented and tracked for display.

Current right-panel tabs in the GUI are:

- Process Monitor
- Code Viewer
- Memory

Future tabs may include:

- Sheets
- Materials
- Diff Viewer
- Current Context
- Tasks

The main reason this module exists is to stop `amadeus_gui/main_window.py` from becoming the owner of every future workspace feature.
