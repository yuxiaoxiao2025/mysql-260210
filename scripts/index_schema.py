"""
数据库 Schema 向量索引脚本

运行此脚本将从数据库提取所有表和字段的元数据，
生成向量嵌入，并存储到 ChromaDB 向量数据库。

使用方法：
    python scripts/index_schema.py [--env dev|prod] [--batch-size 10] [--force]

参数：
    --env         环境名称 (默认: dev)
    --batch-size  批量处理大小 (默认: 10)
    --force       强制重新索引（清除现有索引）
"""

import argparse
import io
import logging
import sys
from pathlib import Path

# 设置控制台 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='数据库 Schema 向量索引')
    parser.add_argument('--env', default='dev', choices=['dev', 'prod'],
                        help='环境名称 (默认: dev)')
    parser.add_argument('--batch-size', type=int, default=10,
                        help='批量处理大小 (默认: 10)')
    parser.add_argument('--force', action='store_true',
                        help='强制重新索引（清除现有索引）')
    args = parser.parse_args()

    print("=" * 60)
    print("数据库 Schema 向量索引工具")
    print("=" * 60)
    print(f"环境: {args.env}")
    print(f"批量大小: {args.batch_size}")
    print(f"强制重建: {args.force}")
    print("-" * 60)

    # 导入依赖
    from src.db_manager import DatabaseManager
    from src.metadata.schema_indexer import SchemaIndexer
    from src.metadata.graph_store import GraphStore

    # 初始化组件
    print("\n正在初始化...")
    try:
        db_manager = DatabaseManager()
        indexer = SchemaIndexer(
            db_manager=db_manager,
            env=args.env
        )
        print("✅ 初始化成功")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return 1

    # 检查现有索引
    progress = indexer.get_progress()
    if progress.status == "completed" and not args.force:
        print(f"\n索引已存在: {progress.indexed_tables}/{progress.total_tables} 表已索引")
        print("使用 --force 参数强制重新索引")
        return 0

    # 强制重建时清除现有数据
    if args.force:
        print("\n清除现有索引...")
        indexer.clear_progress()
        graph_store = GraphStore(env=args.env)
        graph_store.clear_all()
        print("✅ 清除完成")

    # 执行索引
    print(f"\n开始索引数据库表...")
    print("-" * 60)

    try:
        result = indexer.index_all_tables(batch_size=args.batch_size)
    except Exception as e:
        print(f"\n❌ 索引失败: {e}")
        logger.exception("索引过程出错")
        return 1

    # 输出结果
    print("\n" + "=" * 60)
    print("索引完成")
    print("=" * 60)
    print(f"状态: {'成功 ✅' if result.success else '部分失败 ⚠️'}")
    print(f"总表数: {result.total_tables}")
    print(f"已索引: {result.indexed_tables}")
    print(f"耗时: {result.elapsed_seconds:.2f} 秒")

    if result.failed_tables:
        print(f"\n失败的表 ({len(result.failed_tables)}):")
        for table in result.failed_tables:
            print(f"  - {table}")

    # 验证索引结果
    print("\n" + "-" * 60)
    print("验证索引结果...")

    graph_store = GraphStore(env=args.env)
    stats = graph_store.get_stats()

    print(f"表向量数: {stats.get('tables', 0)}")
    print(f"字段向量数: {stats.get('fields', 0)}")

    # 检查知识图谱文件
    graph_file = Path(f"data/{args.env}/table_graph.json")
    if graph_file.exists():
        import json
        with open(graph_file, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        print(f"知识图谱: ✅ ({len(graph_data.get('tables', []))} 表)")
    else:
        print("知识图谱: ❌ 文件不存在")

    print("\n" + "=" * 60)
    print("索引完成！现在可以使用语义搜索功能。")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())