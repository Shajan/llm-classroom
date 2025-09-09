"""Deprecated legacy MCPManager module.

This file is retained only to avoid import errors in older notebooks or
references. The functionality has been replaced by `mcp_client_adapter.py`.
Any attempt to import from here should guide users to the new manager.
"""

raise ImportError(
    "mcp_core.py has been deprecated. Use MCPAdapter from mcp_client_adapter.py instead."
)
