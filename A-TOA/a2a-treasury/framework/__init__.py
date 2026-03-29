"""framework/__init__.py

Agentic Commerce Framework (ACF) — core registry and bootstrap layer.

Exposes a central registry for negotiation protocols and settlement
providers, enabling discovery, compatibility checks, and routing.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from framework.interfaces import (
    NegotiationProtocol,
    SettlementProvider,
)


class FrameworkRegistry:
    """In-memory registry of protocols and settlement providers."""

    _protocols: Dict[str, NegotiationProtocol] = {}
    _settlement_providers: Dict[str, SettlementProvider] = {}

    @classmethod
    def register_protocol(cls, protocol: NegotiationProtocol) -> None:
        cls._protocols[protocol.get_protocol_id()] = protocol

    @classmethod
    def get_protocol(cls, protocol_id: str) -> Optional[NegotiationProtocol]:
        return cls._protocols.get(protocol_id)

    @classmethod
    def list_protocols(cls) -> List[Dict]:
        items: List[Dict] = []
        for key, proto in cls._protocols.items():
            capabilities = getattr(proto, "get_capabilities", None)
            caps_dict = capabilities().__dict__ if callable(capabilities) else {}
            items.append({"id": key, "capabilities": caps_dict})
        return items

    @classmethod
    def register_settlement_provider(cls, provider: SettlementProvider) -> None:
        cls._settlement_providers[provider.get_provider_id()] = provider

    @classmethod
    def get_settlement_provider(
        cls,
        provider_id: str,
    ) -> Optional[SettlementProvider]:
        return cls._settlement_providers.get(provider_id)

    @classmethod
    def list_settlement_providers(cls) -> List[Dict]:
        items: List[Dict] = []
        for key, provider in cls._settlement_providers.items():
            capabilities = getattr(provider, "get_capabilities", None)
            caps_dict = capabilities().__dict__ if callable(capabilities) else {}
            items.append({"id": key, "capabilities": caps_dict})
        return items


__all__ = ["FrameworkRegistry"]

