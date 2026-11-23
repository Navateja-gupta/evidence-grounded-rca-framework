"""Independent, reusable analysis modules.

Each module must depend only on rca.core and shared data models - never on another
module or on a specific telemetry backend - so it can be reused, tested and evaluated
in isolation. Orchestration across modules belongs in rca.pipeline.
"""
