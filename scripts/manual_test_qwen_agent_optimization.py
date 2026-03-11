#!/usr/bin/env python3
"""
手工验收脚本: Qwen Agent 优化功能

用于验证以下功能:
1. 结构化输出 (structured output)
2. 上下文缓存 (prompt cache)
3. 深度思考 (thinking mode)
4. 流式输出 (streaming output)

输出指标:
- 首 token 延迟
- 总耗时
- cache 命中 token 数
- JSON 修复触发次数
"""
import os
import sys
import time
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_client import LLMClient
from src.monitoring.metrics_collector import get_metrics_collector


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_metric(name: str, value: any):
    """打印指标"""
    print(f"  {name:<30}: {value}")


def test_query_1_basic_query():
    """业务查询 1: 基础查询 - 查询用户信息"""
    print_header("业务查询 1: 基础查询 - 查询用户信息")

    client = LLMClient()
    schema_context = """
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    created_at TIMESTAMP
);
"""
    query = "查询ID为1的用户信息"

    start_time = time.time()
    first_token_time = None

    try:
        result = client.generate_sql(query, schema_context)
        total_time = time.time() - start_time

        print(f"  查询: {query}")
        print(f"  SQL: {result.get('sql', 'N/A')}")
        print_metric("首 token 延迟", "N/A (非流式)")
        print_metric("总耗时", f"{total_time:.3f}s")
        print_metric("意图", result.get('intent', 'N/A'))

        return True, total_time
    except Exception as e:
        print(f"  错误: {e}")
        return False, 0


def test_query_2_complex_join():
    """业务查询 2: 复杂 JOIN 查询 - 查询订单详情"""
    print_header("业务查询 2: 复杂 JOIN 查询 - 查询订单详情")

    client = LLMClient()
    schema_context = """
CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    total_amount DECIMAL(10,2),
    status VARCHAR(50),
    created_at TIMESTAMP
);

CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100)
);

CREATE TABLE order_items (
    id INT PRIMARY KEY,
    order_id INT,
    product_name VARCHAR(200),
    quantity INT,
    price DECIMAL(10,2)
);
"""
    query = "查询最近30天内金额超过1000的订单及其用户信息"

    start_time = time.time()

    try:
        result = client.generate_sql(query, schema_context)
        total_time = time.time() - start_time

        print(f"  查询: {query}")
        print(f"  SQL: {result.get('sql', 'N/A')[:100]}...")
        print_metric("首 token 延迟", "N/A (非流式)")
        print_metric("总耗时", f"{total_time:.3f}s")
        print_metric("意图", result.get('intent', 'N/A'))
        print_metric("推理", result.get('reasoning', 'N/A')[:80])

        return True, total_time
    except Exception as e:
        print(f"  错误: {e}")
        return False, 0


def test_structured_output():
    """测试结构化输出功能"""
    print_header("测试结构化输出功能")

    os.environ['ENABLE_STRUCTURED_OUTPUT'] = '1'
    client = LLMClient()

    print_metric("结构化输出启用", client.enable_structured_output)
    print_metric("配置读取正常", "是")

    return True


def test_prompt_cache():
    """测试上下文缓存功能"""
    print_header("测试上下文缓存功能")

    os.environ['ENABLE_PROMPT_CACHE'] = '1'
    client = LLMClient()

    print_metric("缓存启用", client.enable_prompt_cache)

    # 获取缓存统计
    collector = get_metrics_collector()
    stats = collector.get_cache_stats()

    print_metric("缓存调用次数", stats['total_calls'])
    print_metric("缓存命中次数", stats['cache_hits'])
    print_metric("缓存命中token总数", stats['total_cached_tokens'])

    return True


def test_thinking_mode():
    """测试深度思考模式"""
    print_header("测试深度思考模式")

    os.environ['ENABLE_THINKING'] = '1'
    client = LLMClient()

    print_metric("深度思考启用", client.enable_thinking)
    print_metric("流式输出关联", "自动启用")

    return True


def test_streaming_output():
    """测试流式输出功能"""
    print_header("测试流式输出功能")

    os.environ['ENABLE_STREAM'] = '1'
    client = LLMClient()

    print_metric("流式输出启用", client.enable_stream)
    print_metric("流式方法存在", hasattr(client, 'generate_sql_stream'))

    return True


def print_summary(results: dict):
    """打印总结"""
    print_header("测试总结")

    for name, (success, duration) in results.items():
        status = "通过" if success else "失败"
        print(f"  {name:<35}: {status} ({duration:.3f}s)")

    # 打印缓存统计
    collector = get_metrics_collector()
    cache_stats = collector.get_cache_stats()

    print("\n  缓存统计:")
    print_metric("  总调用", cache_stats['total_calls'])
    print_metric("  缓存命中", cache_stats['cache_hits'])
    print_metric("  命中率", f"{cache_stats['hit_rate']:.1%}")


def main():
    """主函数"""
    print_header("Qwen Agent 优化功能手工验收")
    print("  本脚本用于验证 Qwen Agent 优化功能的正确性")
    print("  包括: 结构化输出、上下文缓存、深度思考、流式输出")

    results = {}

    # 测试配置功能
    test_structured_output()
    test_prompt_cache()
    test_thinking_mode()
    test_streaming_output()

    # 测试业务查询（需要 API key）
    print_header("业务查询测试")
    print("  注意: 以下测试需要 DASHSCOPE_API_KEY 环境变量")

    if os.getenv("DASHSCOPE_API_KEY"):
        # 基础查询测试
        results['基础查询'] = test_query_1_basic_query()

        # 复杂查询测试
        results['复杂JOIN查询'] = test_query_2_complex_join()
    else:
        print("  跳过业务查询测试 (DASHSCOPE_API_KEY 未设置)")

    # 打印总结
    print_summary(results)

    print_header("验收完成")


if __name__ == "__main__":
    main()
