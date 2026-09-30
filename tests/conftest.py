"""Hypothesis profiles. Pick one with HYPOTHESIS_PROFILE=<name> (default: fast).

fast      - everyday runs after a change
thorough  - before a commit or a result you report
"""

import os

from hypothesis import settings

settings.register_profile("fast", max_examples=50, deadline=None)
settings.register_profile("thorough", max_examples=1000, deadline=None)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "fast"))
