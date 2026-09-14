# Workspace Integration

Application composition supplies Mind Map, Canvas, Chat History, Sheets, Comments,
and Memory services to `MindMapWorkspaceSync`. This owner translates public source
records into graph nodes and the read-only Canvas projection. Each source module
continues to own its content and persistence; existing data formats are unchanged.

Import from `workspace_integration`. The historical `mindmap.integrations` import
is a compatibility export. Canvas reconciliation uses the validated public
`replace_mindmap_projection` operation and does not emit source mutation events.

`graph_workspace.py` owns graph request workflows and source-aware edits/deletion.
`creation_adapter.py` translates approved workspace creation into calls to the
public source owners. These workflows belong here because they coordinate more
than one module; graph storage and source persistence remain with their owners.
