"""FORJA backend: no Qt, voice, or application-global configuration."""
from .runtime import ForgeRuntime

Runtime = ForgeRuntime
__all__ = ['ForgeRuntime', 'Runtime']
