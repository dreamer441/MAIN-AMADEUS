# AMADEUS Unreal Engine 5 Live Control Design

**Date:** 2026-09-24  
**Status:** Approved for implementation

## Goal

Let AMADEUS control an open Unreal Engine 5 Editor project live from chat,
starting with Blueprint and Material graph authoring. The integration must be
local-first, modular, observable, and safe for project-changing actions.

## Scope

The first release provides a live, authenticated localhost connection between
AMADEUS and a project-local Unreal Editor plugin. It supports typed actions to
inspect Blueprint and Material graphs; create, connect, position, and configure
nodes; then compile and save affected assets. A small general-editor catalog
will also cover asset/actor selection, asset-folder creation, supported asset
creation, and actor placement.

"Full control" is an expansion path, not unrestricted model code execution.
Each new editor capability must be added to the registered action catalog with
validation, a preview, execution handler, and tests.

## Architecture

```text
Flow Chat / Dedicated Chat
        |
        v
Core explicit Unreal route
        |
        v
unreal_module (intent, plans, connection, results)
        |
        v
PermissionGuard (single-use approval)
        |
        v
localhost authenticated bridge
        |
        v
AMADEUS Unreal Editor plugin
        |
        v
UE5 editor-thread graph and asset APIs
```

`unreal_module` owns request interpretation, typed action plans, connection
state, bridge requests, result mapping, and its own documentation. Core only
forwards its public routes. The GUI displays module-owned response payloads and
never talks directly to the bridge. The existing Code Viewer and
`project_file_reader` remain read-only and are not broadened into an execution
boundary.

The Unreal-side plugin is placed in a UE project as an Editor-only plugin. It
owns the Unreal implementation details and exposes no network listener beyond
the local machine. It dispatches every mutation on the Unreal Editor thread.

## Live protocol

When its plugin loads, Unreal creates a random per-session token and opens a
localhost-only bridge. AMADEUS connects only after an explicit user connection
action and validates the token, plugin version, UE version, and project identity.
The connection status shows disconnected, connecting, connected, or error.

Messages use versioned JSON envelopes. Requests contain a unique request ID,
target asset or editor scope, and a typed action. Replies contain the request
ID, structured result, created node references when applicable, compile/save
status, and user-safe errors. Raw editor paths, stack traces, tokens, and
untrusted payloads do not enter chat history or Process Monitor summaries.

The bridge does not accept arbitrary Python, console commands, shell commands,
or C++ source from AMADEUS. It accepts only a whitelist of schema-validated
actions.

## Chat and approvals

Chat recognizes an explicit Unreal command namespace, for example:

```text
/unreal status
/unreal inspect /Game/Blueprints/BP_Door
/unreal In /Game/Blueprints/BP_Door, add BeginPlay to Print String, connect them, compile, and save.
/unreal In /Game/Materials/M_Wall, add Texture Coordinate -> Multiply -> Base Color, then save.
```

Normal language may be used only after `/unreal`; AMADEUS turns it into a
bounded typed plan. The plan lists the target, nodes, pins, property values,
compile/save behavior, and any editor-wide effect. Read-only status and inspect
requests execute immediately. Every mutation becomes an expiring, single-use
pending approval. Approval dispatches the frozen plan; decline does nothing.

The first action catalog is:

- `editor.status`, `asset.inspect`, `graph.inspect`
- `blueprint.node.create`, `blueprint.pin.connect`, `blueprint.node.set_property`, `blueprint.graph.layout`, `blueprint.compile`, `asset.save`
- `material.expression.create`, `material.pin.connect`, `material.expression.set_property`, `material.graph.layout`, `material.compile`, `asset.save`
- `editor.select`, `asset_folder.create`, `asset.create`, `level.actor.place`

Each action validates the asset type, target graph, node class, pin direction,
pin type compatibility, allowable property names, and project-relative path.
Multi-step plans execute atomically where Unreal supports transactions; failures
report which unapplied step stopped and retain Unreal's normal undo support.

## Unreal implementation

The plugin uses supported Editor-only APIs to locate assets and manipulate graph
models. It opens or focuses affected editors only when needed for user-visible
verification. Blueprint changes compile through the editor compiler and Material
changes trigger the editor's normal material recompilation path. Saving uses
Unreal asset APIs rather than direct filesystem writes so references remain
consistent.

The plugin includes a dockable AMADEUS status panel showing connection state,
the last accepted request ID, and a disconnect control. It may use Unreal Remote
Control and Editor Scripting Utilities where appropriate, but graph-specific
operations remain plugin-owned typed handlers rather than generic remote calls.

## Errors and safety

- Connections bind to loopback only and reject absent, invalid, or expired tokens.
- AMADEUS rejects commands while disconnected or when the active UE project does
  not match the connected project identity.
- Unsupported intent receives a concise capability message; it never falls back
  to arbitrary execution.
- Invalid assets, node classes, pins, and properties are rejected before mutation.
- Compile failures return a readable UE diagnostic and do not silently report
  success.
- Save failures remain visible and do not imply an on-disk change.
- The plugin never runs in packaged game builds; this is an Unreal Editor feature.

## Tests and acceptance criteria

Python tests cover action schemas, command parsing, connection state, approval
freezing, result handling, and Core/module boundaries. Unreal automated tests
or plugin test fixtures cover a Blueprint node creation and connection flow, a
Material expression creation and connection flow, rejected token, invalid pin,
compile error, and save result.

The initial release is accepted when a user can connect AMADEUS to an open UE5
Editor project, inspect a named Blueprint or Material graph, receive an exact
preview, approve it, see nodes and wires created live, and receive the true
compile and save result.

## Non-goals for the first release

- No remote Internet or LAN control.
- No game-runtime control or packaged-build feature.
- No arbitrary code, Python, console, filesystem, or shell execution from chat.
- No automatic approval for editor mutations.
- No promise that every UE subsystem is controllable before it receives a typed,
  validated action handler.
