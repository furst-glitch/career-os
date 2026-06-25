"""
AI Gateway — Central execution layer for all AI capabilities.
See: docs/ai-gateway-spec-v1.md
"""

from app.gateway.gateway import AIGateway
from app.gateway.schemas import GatewayRequest, GatewayResponse

__all__ = ["AIGateway", "GatewayRequest", "GatewayResponse"]
