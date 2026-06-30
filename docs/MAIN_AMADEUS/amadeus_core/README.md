# AMADEUS Core

Core is the lightweight coordinator for AMADEUS.

It registers modules and routes user requests to the correct module. Core should stay small and should not contain feature logic that belongs inside modules.

Core now also loads the Identity Module and injects AMADEUS's global identity into Chat. This keeps identity global while still allowing future reasoning profiles to temporarily change thinking style.
