"""Allow running ``python -m app`` to trigger the full pipeline.

Usage
-----
    python -m app                  # full pipeline (default)
    python -m app --limit 10      # forward limit to all stages
    python -m app --stop-on-error  # abort on first failure
"""

from app.main import run_pipeline

run_pipeline()
