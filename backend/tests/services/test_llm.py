"""
Tests for LLM service.
"""
import pytest

from app.services.llm import get_llm_client
from app.services.llm.mock_client import MockLLMClient


@pytest.mark.asyncio
async def test_mock_client_generate():
    """Test mock client generates responses."""
    client = MockLLMClient()
    
    response = await client.generate("Test prompt")
    
    assert response.content
    assert response.provider == "mock"
    assert response.model == "mock-model"


@pytest.mark.asyncio
async def test_mock_client_buy_rationale():
    """Test mock client generates buy rationale."""
    client = MockLLMClient()
    
    response = await client.generate("Generate recommendation rationale for BUY action")
    
    assert response.content
    assert len(response.content) > 20


@pytest.mark.asyncio
async def test_mock_client_sell_rationale():
    """Test mock client generates sell rationale."""
    client = MockLLMClient()
    
    response = await client.generate("Generate recommendation rationale for SELL action")
    
    assert response.content


@pytest.mark.asyncio
async def test_generate_recommendation_rationale():
    """Test generating recommendation rationale."""
    client = MockLLMClient()
    
    rationale = await client.generate_recommendation_rationale(
        card_name="Black Lotus",
        action="BUY",
        metrics={
            "current_price": 50000,
            "price_change_pct_7d": 5.5,
            "spread_pct": 15,
        },
    )
    
    assert rationale
    assert len(rationale) > 20


def test_get_llm_client_returns_mock_without_keys():
    """Test factory returns mock client when no API keys configured."""
    # Clear cache first
    from app.services.llm.factory import clear_llm_client_cache
    clear_llm_client_cache()
    
    client = get_llm_client("mock")
    assert isinstance(client, MockLLMClient)

