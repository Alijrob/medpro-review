"""
schema — Medical Professionals Review canonical schema package.

Current version: v1

Usage:
    from schema.v1 import CanonicalProviderProfile, NppesRecord, AuditEvent
    from schema.registry import registry
"""

from .registry import CURRENT_VERSION, registry

__all__ = ["registry", "CURRENT_VERSION"]
