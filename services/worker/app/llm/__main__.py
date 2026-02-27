"""Allow running ``python -m app.llm`` to trigger LLM processing.

Flags
-----
    python -m app.llm                  # story extraction (default)
    python -m app.llm --stories        # story extraction (explicit)
    python -m app.llm --embeddings     # embedding backfill
    python -m app.llm --topics         # topic assignment
    python -m app.llm --embed-actions  # embed desired actions
    python -m app.llm --match-actions  # match stories against desired actions
"""

import sys

# Check for mode flags BEFORE argparse in sub-modules parses
if "--match-actions" in sys.argv:
    sys.argv.remove("--match-actions")
    from app.llm.match_actions import main
elif "--embed-actions" in sys.argv:
    sys.argv.remove("--embed-actions")
    from app.llm.embed_desired_actions import main
elif "--topics" in sys.argv:
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
