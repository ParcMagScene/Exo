"""Prevent multiple instances of the same EXO microservice."""

import logging
import socket
import sys

log = logging.getLogger("exo.singleton")


def ensure_single_instance(port: int, service_name: str) -> None:
    """Exit cleanly if another process is already listening on *port*.

    Call this **before** loading heavy models to avoid wasting RAM
    on a duplicate that will fail to bind anyway.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
        except (ConnectionRefusedError, OSError, TimeoutError):
            return  # port free — OK to proceed
    # If we reach here, something is already listening
    log.warning(
        "%s: port %d already in use — duplicate prevented, exiting.",
        service_name,
        port,
    )
    sys.exit(0)
