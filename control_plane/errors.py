from __future__ import annotations


class ControlPlaneError(Exception):
    """A user-visible, structured control-plane validation error."""

    def __init__(self, message: str, *, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.code = code


class ProjectNotFound(ControlPlaneError):
    def __init__(self, project_id: str) -> None:
        super().__init__(f"unknown project: {project_id}", code="project_not_found")


class RequirementNotFound(ControlPlaneError):
    def __init__(self, requirement_id: str) -> None:
        super().__init__(f"unknown requirement: {requirement_id}", code="requirement_not_found")


class SessionNotFound(ControlPlaneError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"unknown session: {session_id}", code="session_not_found")


class ProjectConflict(ControlPlaneError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="project_conflict")


class UnsafePath(ControlPlaneError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="unsafe_path")


class GateConflict(ControlPlaneError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="gate_conflict")
