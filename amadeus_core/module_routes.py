"""Explicit Core-owned module routes used by reusable module views.

Every operation resolves its registered owner. No arbitrary attribute forwarding
or storage/service construction is available to the GUI through these facades.
"""
from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from typing import Any
from amadeus_core.module_registry import ModuleRegistry


class CanvasRoutes:
    """Route public canvas operations through Core registration."""

    def __init__(self, module_registry: ModuleRegistry) -> None:
        self.module_registry = module_registry

    @property
    def workspace_id(self) -> str:
        """Read the active workspace identity through its registered owner."""
        return self.module_registry.require("canvas").workspace_id

    def get_workspace_descriptor(self) -> Any:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("canvas").get_workspace_descriptor()

    def list_workspaces(self) -> list[Any]:
        """Return the lightweight workspace registry in stable display order."""
        return self.module_registry.require("canvas").list_workspaces()

    def workspace_by_id(self, workspace_id: str) -> Any | None:
        """Return one registered workspace without changing the active workspace."""
        return self.module_registry.require("canvas").workspace_by_id(workspace_id)

    def ensure_workspace(self, workspace_id: str, title: str) -> Any:
        """Create a stable workspace ID without taking focus from the active Canvas."""
        return self.module_registry.require("canvas").ensure_workspace(workspace_id, title)

    def create_workspace(self, title: str) -> Any:
        """Create and activate an empty independent Canvas workspace."""
        return self.module_registry.require("canvas").create_workspace(title)

    def switch_workspace(self, workspace_id: str) -> Any:
        """Activate a registered workspace and persist it as the last opened."""
        return self.module_registry.require("canvas").switch_workspace(workspace_id)

    def rename_workspace(self, workspace_id: str, title: str) -> Any:
        """Rename a workspace without changing its stable ID or document."""
        return self.module_registry.require("canvas").rename_workspace(workspace_id, title)

    def delete_workspace(self, workspace_id: str) -> Any:
        """Archive a workspace and activate a safe remaining workspace."""
        return self.module_registry.require("canvas").delete_workspace(workspace_id)

    def get_snapshot(self) -> Any:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("canvas").get_snapshot()

    def get_snapshot_for_workspace(self, workspace_id: str) -> Any:
        """Return a registered workspace document without changing the active workspace."""
        return self.module_registry.require("canvas").get_snapshot_for_workspace(workspace_id)

    def replace_mindmap_projection(
        self,
        workspace_id: str,
        *,
        blocks: tuple[Any, ...],
        connectors: tuple[Any, ...],
    ) -> None:
        """Atomically reconcile only Mind Map-managed records in one workspace."""
        return self.module_registry.require('canvas').replace_mindmap_projection(
            workspace_id,
            blocks=blocks,
            connectors=connectors,
        )

    def list_text_blocks(self) -> list[Any]:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("canvas").list_text_blocks()

    def list_connectors(self) -> list[Any]:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("canvas").list_connectors()

    def list_send_operations(self) -> list[Any]:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("canvas").list_send_operations()

    def can_undo(self) -> bool:
        """Return whether this running Canvas session has a reversible edit."""
        return self.module_registry.require("canvas").can_undo()

    def subscribe(self, listener: Callable[[dict[str, object]], None]) -> Callable[[], None]:
        """Subscribe to completed Canvas mutations and return an unsubscribe callback."""
        return self.module_registry.require("canvas").subscribe(listener)

    def undo_last_change(self) -> Any | None:
        """Restore the previous complete Canvas state for this session."""
        return self.module_registry.require("canvas").undo_last_change()

    def get_change_set(self) -> Any:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("canvas").get_change_set()

    def build_context_preview(
        self,
        *,
        context_mode: str = 'viewport',
        visible_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_connector_ids: list[str] | tuple[str, ...] | set[str] = (),
        branch_root_id: str | None = None,
        ancestor_depth: int = 8,
        descendant_depth: int = 2,
        peer_depth: int = 1,
        token_budget: int = 6000,
    ) -> Any:
        """Build a target-focused preview without calling an LLM."""
        return self.module_registry.require('canvas').build_context_preview(
            context_mode=context_mode,
            visible_object_ids=visible_object_ids,
            selected_object_ids=selected_object_ids,
            selected_connector_ids=selected_connector_ids,
            branch_root_id=branch_root_id,
            ancestor_depth=ancestor_depth,
            descendant_depth=descendant_depth,
            peer_depth=peer_depth,
            token_budget=token_budget,
        )

    def set_root_object(self, object_id: str | None) -> Any:
        """Persist the default central/root block used by Canvas traversal."""
        return self.module_registry.require("canvas").set_root_object(object_id)

    def mark_current_state_sent(self) -> Any:
        """Record the current semantic state as the last successful send."""
        return self.module_registry.require("canvas").mark_current_state_sent()

    def commit_amadeus_response(
        self,
        *,
        context_package: Any,
        response_text: str,
        instruction: str = '',
        process_run_id: str = '',
        model_name: str = '',
        prompt_text: str = '',
    ) -> tuple[Any, Any | None, Any]:
        """Atomically add an AMADEUS response and advance the sent baseline."""
        return self.module_registry.require('canvas').commit_amadeus_response(
            context_package=context_package,
            response_text=response_text,
            instruction=instruction,
            process_run_id=process_run_id,
            model_name=model_name,
            prompt_text=prompt_text,
        )

    def create_text_block(
        self,
        *,
        text: str,
        position_x: float = 0.0,
        position_y: float = 0.0,
        width: float = 320.0,
        height: float = 180.0,
        title: str = '',
        comment: str = '',
        comment_anchor_degrees: float = 315.0,
        comment_width: float = 190.0,
        comment_height: float = 74.0,
        created_by: str = 'dato',
    ) -> Any:
        """Forward this operation to its registered owner."""
        return self.module_registry.require('canvas').create_text_block(
            text=text,
            position_x=position_x,
            position_y=position_y,
            width=width,
            height=height,
            title=title,
            comment=comment,
            comment_anchor_degrees=comment_anchor_degrees,
            comment_width=comment_width,
            comment_height=comment_height,
            created_by=created_by,
        )

    def update_text_block(self, object_id: str, **changes: Any) -> Any:
        """Forward only supplied fields so the owner retains its unset semantics."""
        return self.module_registry.require("canvas").update_text_block(object_id, **changes)

    def create_connector(self, *, source_object_id: str, target_object_id: str, **fields: Any) -> Any:
        """Forward this operation to its registered owner."""
        return self.module_registry.require('canvas').create_connector(
            source_object_id=source_object_id,
            target_object_id=target_object_id,
            **fields,
        )

    def update_connector(self, connector_id: str, **changes: Any) -> Any:
        """Forward only supplied fields so the owner retains its unset semantics."""
        return self.module_registry.require("canvas").update_connector(connector_id, **changes)

    def delete_items(
        self,
        *,
        object_ids: list[str] | tuple[str, ...] | set[str] = (),
        connector_ids: list[str] | tuple[str, ...] | set[str] = (),
    ) -> tuple[int, int]:
        """Delete selected blocks/connectors atomically and remove orphans."""
        return self.module_registry.require('canvas').delete_items(
            object_ids=object_ids,
            connector_ids=connector_ids,
        )

    def delete_items_in_workspace(
        self,
        workspace_id: str,
        *,
        object_ids: list[str] | tuple[str, ...] | set[str] = (),
        connector_ids: list[str] | tuple[str, ...] | set[str] = (),
    ) -> tuple[int, int]:
        """Delete source records in their owning workspace without changing the active workspace."""
        return self.module_registry.require('canvas').delete_items_in_workspace(
            workspace_id,
            object_ids=object_ids,
            connector_ids=connector_ids,
        )

    def delete_objects(self, object_ids: list[str] | tuple[str, ...] | set[str]) -> int:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("canvas").delete_objects(object_ids)

    def delete_connectors(self, connector_ids: list[str] | tuple[str, ...] | set[str]) -> int:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("canvas").delete_connectors(connector_ids)

    def is_read_only_workspace(self, workspace_id: str | None=None) -> bool:
        """Return whether a workspace is owned by a managed projection."""
        return self.module_registry.require("canvas").is_read_only_workspace(workspace_id)


class HabitRoutes:
    """Route public habit_tracker operations through Core registration."""

    def __init__(self, module_registry: ModuleRegistry) -> None:
        self.module_registry = module_registry

    def add_routine_task(
        self,
        title: str,
        repeat_type: str = 'daily',
        description: str | None = None,
        days_of_week: str | None = None,
        every_other_day_start: str | None = None,
    ) -> int:
        """Forward this operation to its registered owner."""
        return self.module_registry.require('habit_tracker').add_routine_task(
            title,
            repeat_type,
            description,
            days_of_week,
            every_other_day_start,
        )

    def day_overview(self, selected_date: str | Any | Any) -> dict[str, Any]:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").day_overview(selected_date)

    def set_routine_completion(self, task_id: int, selected_date: str, is_completed: bool) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require('habit_tracker').set_routine_completion(
            task_id,
            selected_date,
            is_completed,
        )

    def archive_routine_task(self, task_id: int) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").archive_routine_task(task_id)

    def add_one_time_task(self, title: str, task_date: str, description: str | None=None) -> int:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").add_one_time_task(title, task_date, description)

    def set_one_time_completion(self, task_id: int, is_completed: bool) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").set_one_time_completion(task_id, is_completed)

    def delete_one_time_task(self, task_id: int) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").delete_one_time_task(task_id)

    def add_calendar_event(
        self,
        title: str,
        event_date: str,
        description: str | None = None,
        event_time: str | None = None,
    ) -> int:
        """Forward this operation to its registered owner."""
        return self.module_registry.require('habit_tracker').add_calendar_event(
            title,
            event_date,
            description,
            event_time,
        )

    def delete_calendar_event(self, event_id: int) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").delete_calendar_event(event_id)

    def calendar_dates(self) -> set[str]:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").calendar_dates()

    def add_matrix_task(self, title: str, description: str | None=None, quadrant: str='unsorted') -> int:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").add_matrix_task(title, description, quadrant)

    def update_matrix_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        quadrant: str | None = None,
        scheduled_date: str | None = None,
        scheduled_time: str | None = None,
    ) -> None:
        """Update supplied Eisenhower fields while preserving omitted values."""
        return self.module_registry.require('habit_tracker').update_matrix_task(
            task_id,
            title=title,
            description=description,
            quadrant=quadrant,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
        )

    def set_matrix_completion(self, task_id: int, is_completed: bool) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").set_matrix_completion(task_id, is_completed)

    def matrix_tasks(self) -> list[dict[str, Any]]:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").matrix_tasks()

    def delete_matrix_task(self, task_id: int) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").delete_matrix_task(task_id)

    def create_timer(self, title: str, minutes: int) -> int:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").create_timer(title, minutes)

    def create_alarm(self, title: str, target_datetime: str) -> int:
        """Create one explicit local alarm at a validated ISO-like local timestamp."""
        return self.module_registry.require("habit_tracker").create_alarm(title, target_datetime)

    def active_alarms(self) -> list[dict[str, Any]]:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").active_alarms()

    def due_alarms(self) -> list[dict[str, Any]]:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").due_alarms()

    def deactivate_alarm(self, alarm_id: int) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").deactivate_alarm(alarm_id)

    def delete_alarm(self, alarm_id: int) -> None:
        """Forward this operation to its registered owner."""
        return self.module_registry.require("habit_tracker").delete_alarm(alarm_id)
