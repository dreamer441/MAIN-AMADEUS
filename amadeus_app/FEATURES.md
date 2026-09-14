# Application composition Features

- Constructs all public owner services once, connects their dependencies, and returns the named registry to Core.
- composition.py constructs the dependency graph; __init__.py is the lightweight package boundary.
