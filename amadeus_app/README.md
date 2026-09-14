# Application composition

Constructs all public owner services once, connects their dependencies, and returns the named registry to Core.

## Files

composition.py constructs the dependency graph; __init__.py is the lightweight package boundary.

See `docs/ARCHITECTURE.md` for cross-module ownership.
