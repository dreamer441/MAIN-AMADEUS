# Application composition Features

- Configures the separate Inner Brain client for bounded JSON analysis with thinking disabled, temperature zero, and a 30-second timeout. Primary model configuration is unchanged.

- Constructs all public owner services once, connects their dependencies, and returns the named registry to Core.
- composition.py constructs the dependency graph; __init__.py is the lightweight package boundary.
