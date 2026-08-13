"""Cross-project delivery control-plane primitives.

The package stores delivery metadata and audit events only. Business project
source code and full conversation transcripts stay in their execution planes.
"""

from .errors import ControlPlaneError
from .service import ControlPlaneService

__all__ = ["ControlPlaneError", "ControlPlaneService"]
