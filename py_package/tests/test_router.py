"""Unit tests for the Smart Auto-Pilot Router of everyai-core.

Verifies that preset routing modes resolve to the correct chain configurations
and unrecognized routing modes raise the appropriate exception.
"""

import pytest
from everyai_core.routing import resolve_routing_chain, ROUTING_PRESETS


def test_resolve_routing_chain_presets():
    """Test resolving recognized preset routing chains."""
    fastest_chain = resolve_routing_chain("fastest")
    assert fastest_chain == ROUTING_PRESETS["fastest"]
    assert len(fastest_chain) > 0
    assert fastest_chain[0]["provider"] == "groq"
    assert fastest_chain[0]["model"] == "llama3-8b-8192"

    smartest_chain = resolve_routing_chain("smartest")
    assert smartest_chain == ROUTING_PRESETS["smartest"]
    assert smartest_chain[0]["provider"] == "groq"
    assert smartest_chain[0]["model"] == "llama3-70b-8192"

    balanced_chain = resolve_routing_chain("balanced")
    assert balanced_chain == ROUTING_PRESETS["balanced"]


def test_resolve_routing_chain_case_and_whitespace():
    """Test case insensitivity and whitespace stripping during resolution."""
    chain = resolve_routing_chain("  FaStEsT  ")
    assert chain == ROUTING_PRESETS["fastest"]


def test_resolve_routing_chain_invalid():
    """Test resolving an unrecognized mode raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        resolve_routing_chain("ultra-intelligence")
    assert "Unsupported routing mode: 'ultra-intelligence'" in str(exc_info.value)
