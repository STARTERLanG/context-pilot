"""引擎层单测：不依赖 QApplication，可在无 GUI 环境运行。"""

import asyncio

import pytest

from context_pilot.core.models import EnhancedPrompt
from context_pilot.core.pipeline import Pipeline


def test_enhance_returns_enhanced_prompt_with_objective():
    result = asyncio.run(Pipeline().enhance("修一下订单接口"))

    assert isinstance(result, EnhancedPrompt)
    assert result.original_prompt == "修一下订单接口"
    assert "## Objective" in result.enhanced_prompt
    assert "修一下订单接口" in result.enhanced_prompt
    assert result.context == []
    assert result.warnings == []


def test_enhance_empty_prompt_raises_value_error():
    with pytest.raises(ValueError):
        asyncio.run(Pipeline().enhance("   "))
