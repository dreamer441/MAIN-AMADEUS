"""Side Panel foundation module for AMADEUS.

The Side Panel module owns panel payload/state concepts only. It does not read
files, manage memory, or create traces. Those responsibilities stay in their
own modules and send display payloads to the GUI through Core.
"""

from side_panel.side_panel_payload import SidePanelPayload
from side_panel.side_panel_state import SidePanelState

__all__ = ["SidePanelPayload", "SidePanelState"]
