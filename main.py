import sys
import os
import datetime
import shlex
import logging
from logging.handlers import RotatingFileHandler

# 配置日志系统
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        RotatingFileHandler(
            'logs/mysql_ai.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

from src.db_manager import DatabaseManager
from src.exporter import ExcelExporter
from src.schema_loader import SchemaLoader
from src.llm_client import LLMClient
from src.sql_safety import validate_sql, detect_intent
from src.preview_renderer import should_render_html
from src.knowledge import KnowledgeLoader
from src.intent import IntentRecognizer
from src.executor import OperationExecutor
from src.monitoring import MetricsCollector, AlertManager, setup_structured_logging, LogNotifier

def print_welcome():
    print("=" * 60)
    print("🚗 漕河泾停车云数据导出工具 v3.0 (AI Enhanced + Smart Operations)")
    print("=" * 60)
    print("✨ 新功能：智能业务操作")
    print("  现在可以直接使用业务语言，系统会自动识别并执行操作：")
    print("  '下发车牌 沪ABC1234 到 国际商务中心'")
    print("  '查询车牌 沪A12345'")
    print("  '查看30天内到期的车牌'")
    print("-" * 60)
    print("📝 命令列表：")
    print("  list tables       - 列出所有表")
    print("  desc <table>      - 查看表结构")
    print("  help [operation]  - 查看帮助或操作详情")
    print("  operations        - 列出所有可用操作")
    print("  exit / quit       - 退出程序")
    print("-" * 60)
    print("💡 也可以直接输入自然语言或 SQL 语句")
    print("=" * 60)

def main():
    logger.info("应用程序启动")
    try:
        print("正在连接数据库...")
        db = DatabaseManager()
        exporter = ExcelExporter()
        logger.info("数据库连接成功")
        print("✅ 数据库连接成功！")

        print("正在加载业务知识库...")
        knowledge_loader = KnowledgeLoader(db_manager=db)
        logger.info(f"知识库加载成功，共 {len(knowledge_loader.get_all_operations())} 个操作模板")
        print(f"✅ 知识库加载成功！({len(knowledge_loader.get_all_operations())} 个操作模板)")

        print("正在加载 AI 模块...")
        llm = LLMClient()
        schema_loader = SchemaLoader(db_manager=db)
        schema_context = schema_loader.get_schema_context()

        # 初始化意图识别器和操作执行器
        intent_recognizer = IntentRecognizer(llm, knowledge_loader)
        operation_executor = OperationExecutor(db, knowledge_loader)
        logger.info("AI 模块加载成功")
        print("✅ AI 模块加载成功！")

        # 初始化监控和告警系统
        print("正在初始化监控系统...")
        metrics_collector = MetricsCollector(window_size=300)  # 5 分钟窗口
        operation_logger = setup_structured_logging("operation")

        # 创建告警管理器（使用日志通知器）
        alert_manager = AlertManager(
            metrics_collector=metrics_collector,
            error_rate_threshold=0.1,  # 10% 错误率
            avg_duration_threshold=5.0,  # 5 秒执行时间
            cooldown_period=60,  # 60 秒冷却期
            notifiers=[LogNotifier(operation_logger=operation_logger)]
        )
        logger.info("监控系统初始化成功")
        print("✅ 监控系统初始化成功！")

    except Exception as e:
        logger.error(f"初始化失败: {e}")
        print(f"❌ 初始化失败: {e}")
        return

    print_welcome()

    while True:
        try:
            user_input = input("\n[MySQL/AI] > ").strip()

            if not user_input:
                continue

            # ========== 内置命令处理 ==========

            if user_input.lower() in ('exit', 'quit'):
                logger.info("用户退出应用程序")
                print("👋 再见！")
                break

            if user_input.lower() == 'list tables':
                tables = db.get_all_tables()
                print("\n📊 数据库中的表：")
                for i, t in enumerate(tables):
                    print(f"  {i+1}. {t}")
                continue

            if user_input.lower().startswith('desc '):
                table_name = user_input.split()[1]
                try:
                    schema = db.get_table_schema(table_name)
                    print(f"\n📋 表 {table_name} 结构：")
                    print(f"{'字段名':<20} {'类型':<15} {'注释'}")
                    print("-" * 50)
                    for col in schema:
                        print(f"{col['name']:<20} {col['type']:<15} {col['comment']}")
                except Exception as e:
                    print(f"❌ 获取表结构失败: {e}")
                continue

            # 新增：help 命令
            if user_input.lower() == 'help' or user_input.lower() == 'help ':
                print_welcome()
                print("\n📖 详细帮助：")
                print("  使用 'operations' 查看所有可用操作")
                print("  使用 'help <操作名>' 查看操作详情，如 'help plate_distribute'")
                continue

            if user_input.lower().startswith('help '):
                op_name = user_input[5:].strip()
                help_text = intent_recognizer.get_operation_help(op_name)
                print(f"\n{help_text}")
                continue

            # 新增：operations 命令
            if user_input.lower() == 'operations':
                ops_text = intent_recognizer.list_available_operations()
                print(f"\n{ops_text}")
                continue

            # ========== 智能意图识别 ==========

            # Check if it looks like SQL
            first_word = user_input.lower().split()[0] if user_input else ""
            is_sql = first_word in ['select', 'show', 'describe', 'desc', 'explain', 'update', 'delete', 'insert', 'drop', 'alter', 'truncate']

            if not is_sql:
                # 尝试智能意图识别
                print("🔍 正在识别操作意图...")
                intent_result = intent_recognizer.recognize(user_input)

                # 高置信度匹配到操作模板
                if intent_result.is_matched and intent_result.confidence >= 0.7:
                    print(f"✅ 识别为「{intent_result.operation_name}」操作 (置信度: {intent_result.confidence:.0%})")

                    # 显示提取的参数
                    if intent_result.params:
                        print("📋 提取的参数:")
                        for key, value in intent_result.params.items():
                            print(f"   {key}: {value}")

                    # 检查是否有缺失参数
                    if intent_result.missing_params:
                        print(f"⚠️  缺少参数: {', '.join(intent_result.missing_params)}")

                        # 尝试从枚举中推荐值
                        operation = knowledge_loader.get_operation(intent_result.operation_id)
                        if operation:
                            for param_name in intent_result.missing_params:
                                param = operation.get_param(param_name)
                                if param and param.enum_from:
                                    values = knowledge_loader.get_enum_values_flat(param.enum_from)
                                    if values:
                                        print(f"   💡 {param.description} 可选值: {', '.join(values[:5])}...")

                        # 让用户补充参数
                        for param_name in intent_result.missing_params:
                            operation = knowledge_loader.get_operation(intent_result.operation_id)
                            param = operation.get_param(param_name) if operation else None
                            prompt = f"请输入 {param_name}"
                            if param:
                                prompt += f" ({param.description})"
                            prompt += " > "
                            value = input(prompt).strip()
                            if value:
                                intent_result.params[param_name] = value

                        # 重新检查缺失参数
                        intent_result.missing_params = [
                            p for p in intent_result.missing_params
                            if p not in intent_result.params
                        ]

                        if intent_result.missing_params:
                            print(f"❌ 仍缺少必需参数，操作取消")
                            continue

                    # 显示建议
                    for suggestion in intent_result.suggestions:
                        print(f"💡 {suggestion}")

                    # 预览操作
                    print("\n📊 正在生成预览...")
                    start_time = datetime.datetime.now()
                    exec_result = operation_executor.execute_operation(
                        operation_id=intent_result.operation_id,
                        params=intent_result.params,
                        preview_only=True
                    )
                    duration = (datetime.datetime.now() - start_time).total_seconds()

                    # 记录操作指标
                    metrics_collector.record_operation(
                        operation_type="query" if intent_result.operation_id.startswith("query_") else "mutation",
                        success=exec_result.success,
                        duration=duration,
                        operation_id=intent_result.operation_id,
                        error=exec_result.error if not exec_result.success else None
                    )

                    if not exec_result.success:
                        print(f"❌ 预览失败: {exec_result.error}")
                        continue

                    # 显示预览
                    print(operation_executor.format_preview_output(exec_result))

                    # 确认执行
                    operation = knowledge_loader.get_operation(intent_result.operation_id)
                    if operation and operation.is_mutation():
                        confirm = input("\n❓ 确认执行此操作？(y/n) > ")
                        if confirm.lower() != 'y':
                            print("❌ 操作已取消")
                            continue

                        # 执行操作
                        print("⏳ 正在执行...")
                        start_time = datetime.datetime.now()
                        exec_result = operation_executor.execute_operation(
                            operation_id=intent_result.operation_id,
                            params=intent_result.params,
                            preview_only=False,
                            auto_commit=True
                        )
                        duration = (datetime.datetime.now() - start_time).total_seconds()

                        # 记录操作指标
                        metrics_collector.record_operation(
                            operation_type="mutation",
                            success=exec_result.success,
                            duration=duration,
                            operation_id=intent_result.operation_id,
                            error=exec_result.error if not exec_result.success else None
                        )

                        if exec_result.success:
                            print(f"✅ {exec_result.summary}")
                        else:
                            print(f"❌ 执行失败: {exec_result.error}")
                    else:
                        # 查询操作，导出结果
                        if exec_result.previews and exec_result.previews[0].after:
                            df_data = exec_result.previews[0].after
                            import pandas as pd
                            df = pd.DataFrame(df_data)

                            if not df.empty:
                                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                                filename = f"{intent_result.operation_id}_{timestamp}"
                                print(f"💾 正在导出到 Excel...")
                                filepath = exporter.export(df, filename, sheet_name=intent_result.operation_name)
                                print(f"🎉 导出完成：{filepath}")
                            else:
                                print("⚠️  查询结果为空")
                    continue

                # 没有匹配操作模板，但有 fallback SQL
                elif intent_result.fallback_sql:
                    print("🔄 未匹配到操作模板，使用 LLM 生成 SQL")
                    print(f"💡 推理: {intent_result.reasoning}")
                    sql_to_execute = intent_result.fallback_sql
                    base_filename = "query_result"
                    export_sheet_name = "Sheet1"

                # 完全没有匹配，回退到原有 LLM 流程
                else:
                    if not llm.api_key:
                        print("❌ 未配置 API Key，无法使用自然语言查询。请在 .env 中设置 DASHSCOPE_API_KEY。")
                        continue

                    print("🧠 正在思考您的需求...")
                    try:
                        result = llm.generate_sql(user_input, schema_context)
                        print("-" * 30)
                        print(f"🤖 生成的 SQL:\n{result['sql']}")
                        print(f"💡 思考过程: {result.get('reasoning', '无')}")
                        print("-" * 30)

                        confirm = input("❓ 是否执行此查询？(y/n) > ")
                        if confirm.lower() != 'y':
                            continue

                        sql_to_execute = result['sql']
                        base_filename = result.get('filename', 'query_result')
                        export_sheet_name = result.get('sheet_name', 'Sheet1')

                    except Exception as e:
                        print(f"❌ AI 生成失败: {e}")
                        llm.add_error_to_history(user_input, str(e))
                        continue
            else:
                # 直接 SQL 输入
                intent = detect_intent(user_input)
                is_valid, reason = validate_sql(user_input)
                if not is_valid:
                    print(f"❌ 危险操作，拒绝执行: {reason}")
                    continue

                sql_to_execute = user_input
                base_filename = None
                export_sheet_name = "Sheet1"

            # ========== 执行查询 ==========
            print("⏳ 正在查询...")
            start_time = datetime.datetime.now()

            try:
                df = db.execute_query(sql_to_execute)
                duration = (datetime.datetime.now() - start_time).total_seconds()
                print(f"✅ 查询成功！耗时 {duration:.2f}秒，共 {len(df)} 行数据。")

                # 记录操作指标
                metrics_collector.record_operation(
                    operation_type="query",
                    success=True,
                    duration=duration,
                    operation_id="sql_query"
                )

                # 定期检查告警（每 10 次操作检查一次）
                stats = metrics_collector.get_stats()
                if stats["total_operations"] % 10 == 0:
                    alerts = alert_manager.check_and_alert()
                    if alerts:
                        print(f"⚠️  检测到 {len(alerts)} 条告警，请查看日志详情")

                if not df.empty:
                    if not base_filename:
                        filename_part = "query_result"
                        tokens = sql_to_execute.lower().split()
                        if 'from' in tokens:
                            try:
                                idx = tokens.index('from') + 1
                                if idx < len(tokens):
                                    filename_part = tokens[idx].replace('`', '').replace(';', '')
                            except:
                                pass
                        base_filename = filename_part

                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    export_filename = f"{base_filename}_{timestamp}"

                    print(f"💾 正在导出到 Excel...")
                    filepath = exporter.export(df, export_filename, sheet_name=export_sheet_name)
                    print(f"🎉 导出完成：{filepath}")
                else:
                    print("⚠️  查询结果为空，未生成文件。")

            except Exception as e:
                print(f"❌ 查询执行失败: {e}")
                if not is_sql:
                    llm.add_error_to_history(user_input, str(e))

                # 记录失败的操作指标
                duration = (datetime.datetime.now() - start_time).total_seconds()
                metrics_collector.record_operation(
                    operation_type="query",
                    success=False,
                    duration=duration,
                    operation_id="sql_query",
                    error=str(e)
                )

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生未知错误: {e}")

if __name__ == "__main__":
    main()
