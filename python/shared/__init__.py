"""EXO shared modules — v9.1 observability, resilience, security."""

from .base_service import json_loads, json_dumps  # noqa: F401
from .hardening import (  # noqa: F401
    install_global_excepthook,
    preflight_file,
    preflight_port_free,
    preflight_port_listen,
    preflight_model_gguf,
    preflight_binary,
    preflight_dependencies,
    safe_json_loads,
    safe_json_dumps,
    with_timeout,
    debounce_async,
    RateLimiter,
    PreflightReport,
)
from .ws_resilient import (  # noqa: F401
    WsBackoff,
    parse_ws_message,
    safe_send_json,
    make_reconnect_loop,
)
from .config_validator import (  # noqa: F401
    ConfigValidationReport,
    validate_config_file,
)

# Hardening 2026 : capture systématique des exceptions non rattrapées
# dès qu'un service importe quoi que ce soit du package partagé.
install_global_excepthook()
