#!/usr/bin/env python3
"""
测试 LLM 提示词打印功能
"""
import sys
import os

# 确保能导入 core 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm import LLMMessage, LLMConfig, DeepSeekProvider

def test_print_functionality():
    """
    测试打印功能（不实际调用 API）
    我们直接调用 _print_llm_prompt 函数
    """
    
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
    
    print("测试 LLM 提示词打印功能...\n")
    print("=" * 80)
    print("测试 1: 普通调用提示词")
    print("=" * 80)
    _print_llm_prompt(test_messages, test_config, is_stream=False)
    
    print("\n\n" + "=" * 80)
    print("测试 2: 流式调用提示词")
    print("=" * 80)
    _print_llm_prompt(test_messages, test_config, is_stream=True)
    
    print("\n✅ 提示词打印功能测试完成！")
    print("\n现在每次调用 LLM 时，系统会自动打印完整的提示词。")


if __name__ == "__main__":
    test_print_functionality()

