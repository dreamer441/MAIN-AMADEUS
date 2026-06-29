"""
AMADEUS V2 - permission_guard.py

Purpose:
    Provide basic action permission checks for AMADEUS V2 Core.

Responsibilities:
    - Define high-level action categories.
    - Automatically allow safe read-only actions.
    - Block risky action categories by default.
    - Return explicit permission decisions.

Must NOT:
    - Silently approve risky actions.
    - Execute filesystem, command, or system changes.
    - Replace future user consent flows.

Connected systems:
    - core_controller.py
    - core_services.py
    - router.py
"""

from dataclasses import dataclass
from enum import Enum
from typing import Set, Union


class ActionCategory(Enum):
    """
    High-level categories for actions requested through Core.

    It exists so permissions are based on clear risk classes instead of vague strings.
    It controls the vocabulary used by PermissionGuard.
    It must not control actual action execution or module feature behavior.
    """

    READ_ONLY = "READ_ONLY"
    WRITE_FILE = "WRITE_FILE"
    DELETE_FILE = "DELETE_FILE"
    RUN_COMMAND = "RUN_COMMAND"
    SYSTEM_CHANGE = "SYSTEM_CHANGE"


@dataclass(frozen=True)
class PermissionDecision:
    """
    Result of a PermissionGuard check.

    It exists so callers receive both a boolean decision and the reason.
    It controls only permission-check output data.
    It must not execute, approve later, or modify the requested action.
    """

    allowed: bool
    category: ActionCategory
    reason: str


class PermissionGuard:
    """
    Basic safety gate for Core actions.

    It exists to make risky action handling explicit from the beginning.
    It controls whether broad action categories are allowed automatically.
    It must not execute actions, prompt users, edit files, run commands, or change the system.
    """

    def __init__(self) -> None:
        """
        Input:
            None.
        Output:
            None.
        Side effects:
            Creates the default allow-list for safe automatic actions.
        """
        self._automatic_allow_categories: Set[ActionCategory] = {ActionCategory.READ_ONLY}

    def can_perform(
        self,
        category: Union[ActionCategory, str],
        action_name: str = "",
    ) -> PermissionDecision:
        """
        Input:
            category: ActionCategory or matching string.
            action_name: Optional human-readable action name.
        Output:
            PermissionDecision explaining whether the action is allowed.
        Side effects:
            None.
        """
        normalized_category = self._normalize_category(category)
        readable_action = action_name or "unnamed action"

        if normalized_category in self._automatic_allow_categories:
            return PermissionDecision(
                allowed=True,
                category=normalized_category,
                reason=f"Allowed safe read-only action: {readable_action}.",
            )

        return PermissionDecision(
            allowed=False,
            category=normalized_category,
            reason=(
                "Blocked risky action by default: "
                f"{readable_action} requires explicit PermissionGuard approval."
            ),
        )

    def require(
        self,
        category: Union[ActionCategory, str],
        action_name: str = "",
    ) -> PermissionDecision:
        """
        Input:
            category: ActionCategory or matching string.
            action_name: Optional human-readable action name.
        Output:
            PermissionDecision when the action is allowed.
        Side effects:
            Raises PermissionError when the action is blocked.
        """
        decision = self.can_perform(category=category, action_name=action_name)
        if not decision.allowed:
            raise PermissionError(decision.reason)

        return decision

    def _normalize_category(self, category: Union[ActionCategory, str]) -> ActionCategory:
        """
        Input:
            category: ActionCategory or matching string.
        Output:
            Normalized ActionCategory value.
        Side effects:
            Raises ValueError when the category is unknown.
        """
        if isinstance(category, ActionCategory):
            return category

        try:
            return ActionCategory[str(category).upper()]
        except KeyError as error:
            raise ValueError(f"Unknown action category: {category}") from error
