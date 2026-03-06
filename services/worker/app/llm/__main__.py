"""Allow running ``python -m app.llm`` to trigger LLM processing.

Flags
-----
    python -m app.llm                  # story extraction (default)
    python -m app.llm --stories        # story extraction (explicit)
    python -m app.llm --embeddings     # embedding backfill
    python -m app.llm --topics         # topic assignment
"""

import sys

# Check for mode flags BEFORE argparse in sub-modules parses
if "--topics" in sys.argv:
    sys.argv.remove("--topics")
    from app.llm.assign_topics import main
elif "--embeddings" in sys.argv:
    sys.argv.remove("--embeddings")
    from app.llm.compute_embeddings import main
else:
    # --stories is optional (it's the default now)
    if "--stories" in sys.argv:
        sys.argv.remove("--stories")
    from app.llm.extract_stories import main

main()
