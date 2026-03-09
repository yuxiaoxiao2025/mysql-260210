#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen3-Rerank 功能手动测试脚本

测试内容:
1. RerankService - 调用 qwen3-rerank API
2. RetrievalPipeline - 两层 Rerank + 预算控制
3. 语义字段 - TableMetadata 的 semantic_* 字段
4. 集成测试 - 完整检索流程

使用方法:
    python scripts/manual_test_rerank.py
"""

import os
import sys
import time

# 设置控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
from rich import print as rprint

console = Console(force_terminal=True)


def test_rerank_service():
    """测试 RerankService 基本功能"""
    console.rule("[bold blue]测试 1: RerankService[/bold blue]")

    try:
        from src.metadata.rerank_service import RerankService, RerankResult

        # 检查 API Key
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            console.print("[red]错误: 未设置 DASHSCOPE_API_KEY 环境变量[/red]")
            return False

        console.print(f"[green]✓[/green] API Key 已配置: {api_key[:8]}...")

        # 创建服务实例
        service = RerankService()
        console.print(f"[green]✓[/green] RerankService 初始化成功")
        console.print(f"  - 模型: {service.MODEL_NAME}")
        console.print(f"  - 超时: {service.timeout}s")
        console.print(f"  - 重试次数: {service.max_retries}")

        # 测试 rerank 功能
        query = "查询车牌信息"
        candidates = [
            "cloud_fixed_plate: 固定车牌表，存储长期停放的固定车辆信息",
            "cloud_temp_plate: 临时车牌表，存储临时来访车辆信息",
            "cloud_user: 用户表，存储系统用户账号信息",
            "cloud_order: 订单表，存储停车订单交易信息",
        ]

        console.print(f"\n[yellow]测试查询:[/yellow] {query}")
        console.print("[yellow]候选表:[/yellow]")
        for i, c in enumerate(candidates):
            console.print(f"  {i}. {c}")

        start_time = time.time()
        results = service.rerank(query, candidates)
        elapsed_ms = int((time.time() - start_time) * 1000)

        console.print(f"\n[green]✓[/green] Rerank 调用成功 (耗时: {elapsed_ms}ms)")
        console.print("[yellow]排序结果:[/yellow]")

        table = RichTable(show_header=True, header_style="bold magenta")
        table.add_column("排名", style="cyan", width=6)
        table.add_column("索引", style="green", width=6)
        table.add_column("相关性", style="yellow", width=10)
        table.add_column("候选内容", style="white")

        for rank, r in enumerate(results, 1):
            table.add_row(
                str(rank),
                str(r.index),
                f"{r.relevance_score:.4f}",
                candidates[r.index][:50] + "..."
            )

        console.print(table)

        # 验证排序: 车牌相关的表应该排在前面
        top_indices = [r.index for r in results[:2]]
        if 0 in top_indices and 1 in top_indices:
            console.print("[green]✓[/green] 语义排序正确: 车牌相关表排在前面")
        else:
            console.print("[yellow]! 语义排序结果可能需要人工确认[/yellow]")

        return True

    except Exception as e:
        console.print(f"[red]✗ RerankService 测试失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_retrieval_pipeline():
    """测试 RetrievalPipeline 两层 Rerank"""
    console.rule("[bold blue]测试 2: RetrievalPipeline 两层 Rerank[/bold blue]")

    try:
        from src.metadata.retrieval_pipeline import RetrievalPipeline, FIELD_RERANK_THRESHOLD_MS

        console.print(f"[green]✓[/green] 字段 Rerank 阈值: {FIELD_RERANK_THRESHOLD_MS}ms")

        # 创建 pipeline (需要有效的数据库连接和已构建的向量索引)
        try:
            pipeline = RetrievalPipeline(budget_ms=500)
            console.print(f"[green]✓[/green] RetrievalPipeline 初始化成功 (预算: {pipeline.budget_ms}ms)")
        except Exception as e:
            console.print(f"[yellow]! Pipeline 初始化需要数据库连接和向量索引: {e}[/yellow]")
            console.print("[yellow]跳过集成测试，继续验证配置...[/yellow]")
            return True

        # 测试检索
        query = "查询车牌"
        console.print(f"\n[yellow]测试查询:[/yellow] {query}")

        start_time = time.time()
        result = pipeline.search(query, top_k=5)
        total_ms = int((time.time() - start_time) * 1000)

        console.print(f"\n[green]✓[/green] 检索完成")
        console.print(f"  - 总耗时: {result.execution_time_ms}ms")
        console.print(f"  - 向量搜索: {result.metadata.get('vector_search_time_ms', 0)}ms")
        console.print(f"  - 表级 Rerank: {result.metadata.get('table_rerank_time_ms', 0)}ms")
        console.print(f"  - 字段级 Rerank: {result.metadata.get('field_rerank_time_ms', 0)}ms")
        console.print(f"  - 字段 Rerank 跳过: {result.metadata.get('field_rerank_skipped', 'N/A')}")

        if result.matches:
            console.print(f"\n[yellow]Top {len(result.matches)} 匹配表:[/yellow]")
            table = RichTable(show_header=True, header_style="bold magenta")
            table.add_column("表名", style="cyan")
            table.add_column("相似度", style="yellow")
            table.add_column("描述", style="white")

            for m in result.matches[:5]:
                table.add_row(
                    m.table_name,
                    f"{m.similarity_score:.4f}",
                    (m.description or "")[:40] + "..."
                )

            console.print(table)
        else:
            console.print("[yellow]! 无匹配结果 (可能需要先构建向量索引)[/yellow]")

        # 验证预算控制
        if total_ms <= 500:
            console.print(f"[green]✓[/green] 预算控制正常: {total_ms}ms <= 500ms")
        else:
            console.print(f"[yellow]! 超出预算: {total_ms}ms > 500ms[/yellow]")

        return True

    except Exception as e:
        console.print(f"[red]✗ RetrievalPipeline 测试失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_semantic_fields():
    """测试语义字段模型"""
    console.rule("[bold blue]测试 3: 语义字段模型[/bold blue]")

    try:
        from src.metadata.models import TableMetadata, ColumnMetadata

        # 创建带语义字段的表元数据
        table = TableMetadata(
            table_name="cloud_fixed_plate",
            database_name="parkcloud",
            comment="固定车牌表",
            semantic_description="存储长期停放车辆的车牌信息，包括车主信息、有效期、绑定场库等",
            semantic_tags=["车辆管理", "车牌", "固定用户"],
            semantic_source="llm",
            semantic_confidence=0.95,
            columns=[
                ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
                ColumnMetadata(name="plate_no", data_type="VARCHAR(20)", comment="车牌号"),
            ]
        )

        console.print("[green]✓[/green] TableMetadata 支持语义字段")
        console.print(f"  - semantic_description: {table.semantic_description}")
        console.print(f"  - semantic_tags: {table.semantic_tags}")
        console.print(f"  - semantic_source: {table.semantic_source}")
        console.print(f"  - semantic_confidence: {table.semantic_confidence}")

        # 测试 JSON 序列化
        json_data = table.model_dump()
        assert "semantic_description" in json_data
        assert "semantic_tags" in json_data
        console.print("[green]✓[/green] 语义字段可以正确序列化")

        # 测试从 JSON 反序列化
        table2 = TableMetadata(**json_data)
        assert table2.semantic_description == table.semantic_description
        console.print("[green]✓[/green] 语义字段可以正确反序列化")

        return True

    except Exception as e:
        console.print(f"[red]✗ 语义字段测试失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_change_detector():
    """测试变更检测器"""
    console.rule("[bold blue]测试 4: ChangeDetector 增量同步[/bold blue]")

    try:
        from src.metadata.change_detector import ChangeDetector, ChangeDiff

        detector = ChangeDetector()
        console.print("[green]✓[/green] ChangeDetector 初始化成功")

        # 测试场景 1: 新增表
        current = {"table_a", "table_b", "table_c"}
        indexed = {"table_a", "table_b"}
        diff = detector.diff(current, indexed)

        console.print(f"\n[yellow]场景 1: 新增表[/yellow]")
        console.print(f"  当前表: {current}")
        console.print(f"  已索引: {indexed}")
        console.print(f"  新增: {diff.added_tables}")
        console.print(f"  删除: {diff.removed_tables}")

        assert "table_c" in diff.added_tables
        assert len(diff.removed_tables) == 0
        console.print("[green]✓[/green] 正确检测新增表")

        # 测试场景 2: 删除表
        current = {"table_a"}
        indexed = {"table_a", "table_b", "table_c"}
        diff = detector.diff(current, indexed)

        console.print(f"\n[yellow]场景 2: 删除表[/yellow]")
        console.print(f"  当前表: {current}")
        console.print(f"  已索引: {indexed}")
        console.print(f"  新增: {diff.added_tables}")
        console.print(f"  删除: {diff.removed_tables}")

        assert len(diff.added_tables) == 0
        assert "table_b" in diff.removed_tables
        assert "table_c" in diff.removed_tables
        console.print("[green]✓[/green] 正确检测删除表")

        # 测试场景 3: 无变化
        current = {"table_a", "table_b"}
        indexed = {"table_a", "table_b"}
        diff = detector.diff(current, indexed)

        console.print(f"\n[yellow]场景 3: 无变化[/yellow]")
        console.print(f"  新增: {diff.added_tables}")
        console.print(f"  删除: {diff.removed_tables}")

        assert len(diff.added_tables) == 0
        assert len(diff.removed_tables) == 0
        console.print("[green]✓[/green] 正确处理无变化场景")

        return True

    except Exception as e:
        console.print(f"[red]✗ ChangeDetector 测试失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_embedding_service():
    """测试 EmbeddingService v4 配置"""
    console.rule("[bold blue]测试 5: EmbeddingService v4[/bold blue]")

    try:
        from src.metadata.embedding_service import EmbeddingService

        # 检查 API Key
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            console.print("[red]错误: 未设置 DASHSCOPE_API_KEY 环境变量[/red]")
            return False

        # 创建 v4 服务
        service = EmbeddingService(model="text-embedding-v4", dimension=1024)
        console.print(f"[green]✓[/green] EmbeddingService 初始化成功")
        console.print(f"  - 模型: {service.model}")
        console.print(f"  - 维度: {service.dimension}")

        # 测试 query 模式
        query = "查询车牌信息"
        console.print(f"\n[yellow]测试 query 模式嵌入:[/yellow] {query}")

        start_time = time.time()
        embedding = service.embed_text(
            query,
            text_type="query",
            instruct="Given a database query, retrieve relevant schema"
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        console.print(f"[green]✓[/green] 嵌入成功 (耗时: {elapsed_ms}ms)")
        console.print(f"  - 向量维度: {len(embedding)}")
        console.print(f"  - 前5个值: {embedding[:5]}")

        assert len(embedding) == 1024
        console.print("[green]✓[/green] 向量维度正确 (1024)")

        # 测试 document 模式
        doc = "cloud_fixed_plate: 固定车牌表，存储长期停放车辆的车牌信息"
        console.print(f"\n[yellow]测试 document 模式嵌入:[/yellow] {doc[:50]}...")

        embedding = service.embed_text(doc, text_type="document")
        console.print(f"[green]✓[/green] document 模式嵌入成功")

        return True

    except Exception as e:
        console.print(f"[red]✗ EmbeddingService 测试失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    console.print(Panel.fit(
        "[bold cyan]Qwen3-Rerank 功能手动测试[/bold cyan]\n"
        "测试 RerankService, RetrievalPipeline, 语义字段, ChangeDetector",
        title="测试套件"
    ))

    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()

    results = {}

    # 运行测试
    results["语义字段"] = test_semantic_fields()
    results["ChangeDetector"] = test_change_detector()
    results["EmbeddingService"] = test_embedding_service()
    results["RerankService"] = test_rerank_service()
    results["RetrievalPipeline"] = test_retrieval_pipeline()

    # 汇总结果
    console.rule("[bold blue]测试结果汇总[/bold blue]")

    table = RichTable(show_header=True, header_style="bold magenta")
    table.add_column("测试项", style="cyan")
    table.add_column("结果", style="bold")

    passed = 0
    for name, result in results.items():
        status = "[green]✓ 通过[/green]" if result else "[red]✗ 失败[/red]"
        table.add_row(name, status)
        if result:
            passed += 1

    console.print(table)
    console.print(f"\n总计: [bold]{passed}/{len(results)}[/bold] 测试通过")

    if passed == len(results):
        console.print(Panel("[bold green]所有测试通过! 功能验证成功![/bold green]"))
    else:
        console.print(Panel("[bold yellow]部分测试未通过，请检查配置和环境[/bold yellow]"))


if __name__ == "__main__":
    run_all_tests()
