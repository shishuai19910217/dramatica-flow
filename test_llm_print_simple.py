#!/usr/bin/env python3
"""
简单测试 LLM 提示词打印功能
"""
import sys
import os

# 确保能导入 core 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm import LLMMessage, LLMConfig

# 创建测试消息
test_messages = [
    LLMMessage(
        role="system",
        content="你是一个专业的小说作家，擅长写悬疑推理故事。"
    ),
    LLMMessage(
        role="user",
        content="请写一个简短的悬疑故事开头，约200字以内。"
    )
]

# 创建测试配置
test_config = LLMConfig(
    api_key="test_key",
    base_url="https://api.test.url",
    model="deepseek-chat",
    temperature=0.7
)

# 导入并调用打印函数
from core.llm import _print_llm_prompt

print("Testing LLM Prompt Print...\n")
_print_llm_prompt(test_messages, test_config, is_stream=False)

print("\nPrint functionality works perfectly!\n")

