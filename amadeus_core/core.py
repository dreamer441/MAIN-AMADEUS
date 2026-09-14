"""Public AMADEUS Core entry point.

This module deliberately exposes only the stable Core type. Explicit request forwarding lives in
``core_coordinator``. Application composition lives in ``amadeus_app`` and
feature workflows remain in their owning modules.
"""

from amadeus_core.core_coordinator import CoreCoordinator


class AmadeusCore(CoreCoordinator):
    """Stable application coordinator exposed to the GUI and application shell."""
