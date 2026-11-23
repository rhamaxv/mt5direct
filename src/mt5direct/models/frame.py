from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Frame:
    """One decrypted server message."""

    cmd: int
    status: int
    payload: bytes
