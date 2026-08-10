"""Legacy compatibility imports for the format now named Testmaker."""
from __future__ import annotations

from .testmaker import *  # noqa: F403
from .testmaker import TestmakerFormatError, parse_testmaker

# Preserve existing integrations while new code uses the Testmaker names.
MCQerFormatError = TestmakerFormatError
parse_mcqer = parse_testmaker
