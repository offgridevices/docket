"""docket — schema-driven, auditable decision records with a deterministic kernel."""

KERNEL_VERSION = "0.1.0"
KERNEL_ACTOR = {"actorType": "kernel", "actorId": f"docket-kernel/{KERNEL_VERSION}"}

__all__ = ["KERNEL_VERSION", "KERNEL_ACTOR"]
