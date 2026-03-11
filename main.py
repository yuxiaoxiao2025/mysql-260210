import sys
import os
import datetime
import shlex
import logging
import argparse
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

def _configure_stdio_encoding():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            continue

from src.db_manager import DatabaseManager
from src.exporter import ExcelExporter
from src.schema_loader import SchemaLoader
from src.llm_client import LLMClient
from src.sql_safety import validate_direct_query_sql
from src.preview_renderer import should_render_html
from src.knowledge import KnowledgeLoader
from src.intent import IntentRecognizer
from src.executor import OperationExecutor, get_operation_executor
from src.monitoring import MetricsCollector, AlertManager, setup_structured_logging, LogNotifier
from src.context import SlotTracker, QueryRewriter
from src.cli.preview import CLIPreview
from src.cli.interaction import Interaction
from src.feedback.intent_parser import FeedbackParser
from src.memory.concept_store import ConceptStoreService
from src.memory.context_memory import ContextMemoryService
from src.dialogue.startup_wizard import StartupWizard
from src.dialogue.dialogue_engine import DialogueEngine, DialogueState
from src.agents.orchestrator import Orchestrator
from src.agents.impl.review_agent import ReviewAgent
from src.agents.config import ReviewAgentConfig

def print_welcome(agent_mode=False):
    print("=" * 60)
    print("MySQL Export Tool v3.0 (AI Enhanced + Smart Operations)")
    print("=" * 60)
    if agent_mode:
        print("运行模式: Agent Mode (使用 Orchestrator)")
    print("新功能：智能业务操作")
    print("  现在可以直接使用业务语言，系统会自动识别并执行操作：")
    print("  '下发车牌 沪ABC1234 到 国际商务中心'")
    print("  '查询车牌 沪A12345'")
    print("  '查看30天内到期的车牌'")
    print("-" * 60)
    print("命令列表：")
    print("  list tables       - 列出所有表")
    print("  desc <table>      - 查看表结构")
    print("  help [operation]  - 查看帮助或操作详情")
    print("  operations        - 列出所有可用操作")
    print("  index schema      - 索引所有数据库的表结构")
    print("  chat              - 进入智能对话模式（推荐）")
    print("  exit / quit       - 退出程序")
    print("-" * 60)
    print("也可以直接输入自然语言或 SQL 语句")
    print("=" * 60)

def check_and_sync_schema(db_manager):
    """检查并同步表结构变化"""
    from src.metadata.schema_indexer import SchemaIndexer

    try:
        # Pass the existing db_manager to SchemaIndexer to reuse connection context
        indexer = SchemaIndexer(db_manager=db_manager)
        result = indexer.incremental_sync()

        if result.indexed_tables > 0:
            print(f"[INFO] 已同步 {result.indexed_tables} 个表的结构变化")
        elif result.success:
            print("[INFO] 表结构无变化")
        else:
            print(f"[WARN] 同步失败: {result.failed_tables}")
    except Exception as e:
        logger.error(f"增量同步失败: {e}")
        print(f"[WARN] 增量同步失败: {e}")

def main():
    _configure_stdio_encoding()
    logger.info("应用程序启动")

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="MySQL Export Tool v3.0 (AI Enhanced)")
    parser.add_argument("--agent-mode", action="store_true", help="启用 Agent 模式，使用 Orchestrator 处理请求")
    args = parser.parse_args()

    try:
        print("正在连接数据库...")
        db = DatabaseManager()
        exporter = ExcelExporter()
        logger.info("数据库连接成功")
        print("[OK] 数据库连接成功！")

        print("正在加载业务知识库...")
        knowledge_loader = KnowledgeLoader(db_manager=db)
        logger.info(f"知识库加载成功，共 {len(knowledge_loader.get_all_operations())} 个操作模板")
        print(f"[OK] 知识库加载成功！({len(knowledge_loader.get_all_operations())} 个操作模板)")

        # 初始化记忆系统
        print("正在初始化对话记忆系统...")
        concept_store = ConceptStoreService()
        context_memory = ContextMemoryService()
        logger.info("对话记忆系统初始化成功")
        print("[OK] 对话记忆系统初始化成功！")

        # 检查是否需要启动向导
        wizard = StartupWizard(concept_store, db_manager=db)
        
        # 强制询问是否补充知识库（如果尚未启动向导）
        start_wizard = False
        if wizard.should_start():
            start_wizard = True
        else:
            try:
                response = input("\n是否需要补充知识库？(y/n，默认n): ").strip().lower()
                if response == 'y':
                    start_wizard = True
            except EOFError:
                pass

        if start_wizard:
            print("\n" + "=" * 60)
            print(wizard.get_welcome_message())
            print("=" * 60)
            print("\n让我们开始初始化知识库...")

            try:
                question = wizard.start()
                while question:
                    print(f"\n[向导] {question.question}")
                    if question.options:
                        for i, opt in enumerate(question.options):
                            print(f"  {chr(65+i)}. {opt}")
                    answer = input("你的回答: ").strip()
                    if answer.lower() in ['exit', 'quit', '退出']:
                        print("跳过向导...")
                        break
                    question = wizard.answer(answer)

                print("\n" + wizard.get_completion_message())
            except Exception as e:
                logger.warning(f"启动向导执行出错: {e}")
                print(f"[WARN] 启动向导未能完成，继续主程序...")

        print("正在加载 AI 模块...")
        llm = LLMClient()
        schema_loader = SchemaLoader(db_manager=db)
        schema_context = schema_loader.get_schema_context()

        # 初始化意图识别器和操作执行器
        intent_recognizer = IntentRecognizer(llm, knowledge_loader)
        operation_executor = get_operation_executor(db, knowledge_loader)
        logger.info("AI 模块加载成功")
        print("[OK] AI 模块加载成功！")

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
        print("[OK] 监控系统初始化成功！")

        # 初始化智能检索增强组件
        print("正在初始化智能检索增强组件...")
        slot_tracker = SlotTracker()
        query_rewriter = QueryRewriter()
        cli_preview = CLIPreview()
        interaction = Interaction()
        feedback_parser = FeedbackParser()
        logger.info("智能检索增强组件初始化成功")
        print("[OK] 智能检索增强组件初始化成功！")

        # 初始化对话引擎
        print("正在初始化对话引擎...")
        dialogue_engine = DialogueEngine(concept_store, context_memory)
        logger.info("对话引擎初始化成功")
        print("[OK] 对话引擎初始化成功！")

        # 初始化 Orchestrator (如果启用 agent-mode)
        orchestrator = None
        if args.agent_mode:
            print("正在初始化 Orchestrator...")
            try:
                orchestrator = Orchestrator(
                    llm_client=llm,
                    knowledge_loader=knowledge_loader,
                    review_agent=ReviewAgent(ReviewAgentConfig(name="review"))
                )
                logger.info("Orchestrator 初始化成功")
                print("[OK] Orchestrator 初始化成功！")
            except Exception as e:
                logger.error(f"Orchestrator 初始化失败: {e}")
                print(f"[WARN] Orchestrator 初始化失败: {e}")
                print("将使用传统模式继续运行...")

        # 检查数据库结构变化
        print("正在检查数据库结构变化...")
        check_and_sync_schema(db)

    except Exception as e:
        logger.error(f"初始化失败: {e}")
        print(f"[ERR] 初始化失败: {e}")
        return

    print_welcome(agent_mode=args.agent_mode)
    sql_to_execute = None  # 初始化变量，防止未定义
    while True:
        try:
            user_input = input("\n[MySQL/AI] > ").strip()

            if not user_input:
                continue

            # ========== 内置命令处理 ==========

            if user_input.lower() in ('exit', 'quit'):
                logger.info("用户退出应用程序")
                print("再见！")
                break

            if user_input.lower() == 'list tables':
                tables = db.get_all_tables()
                print("\n数据库中的表：")
                for i, t in enumerate(tables):
                    print(f"  {i+1}. {t}")
                continue

            # 新增：chat 命令 - 进入对话模式
            if user_input.lower() == 'chat':
                print("\n" + "=" * 60)
                print("进入对话模式")
                print("你好，我是你的停车数据库助手，有什么可以帮你？")
                print("输入 'exit' 或 'quit' 退出对话模式")
                print("=" * 60)

                while True:
                    try:
                        chat_input = input("\n[对话] > ").strip()
                        if not chat_input:
                            continue

                        if chat_input.lower() in ['exit', 'quit', '退出']:
                            print("退出对话模式")
                            break

                        # 使用对话引擎处理输入
                        response = dialogue_engine.process_input(chat_input)
                        print(f"\n[助手] {response.message}")

                        if response.options:
                            for i, opt in enumerate(response.options):
                                print(f"  {chr(65+i)}. {opt}")

                        if response.state == DialogueState.EXECUTING:
                            print("[执行中...] 这里将调用实际执行逻辑")
                            # TODO: 集成实际执行逻辑
                            dialogue_engine.reset()

                    except KeyboardInterrupt:
                        print("\n退出对话模式")
                        break
                    except Exception as e:
                        logger.error(f"对话模式错误: {e}")
                        print(f"[ERR] 对话出错: {e}")

                print("=" * 60)
                continue

            if user_input.lower().startswith('desc '):
                table_name = user_input.split()[1]
                try:
                    schema = db.get_table_schema(table_name)
                    print(f"\n表 {table_name} 结构：")
                    print(f"{'字段名':<20} {'类型':<15} {'注释'}")
                    print("-" * 50)
                    for col in schema:
                        print(f"{col['name']:<20} {col['type']:<15} {col['comment']}")
                except Exception as e:
                    print(f"[ERR] 获取表结构失败: {e}")
                continue

            # 新增：help 命令
            if user_input.lower() == 'help' or user_input.lower() == 'help ':
                print_welcome(agent_mode=args.agent_mode)
                print("\n📖 详细帮助：")
                print("  使用 'operations' 查看所有可用操作")
                print("  使用 'help <操作名>' 查看操作详情，如 'help plate_distribute'")
                print("  使用 'index schema [--env dev|prod] [--batch-size N] [--force]' 执行索引")
                print("  使用 'chat' 进入智能对话模式，支持自然语言交互和概念学习")
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

            # 新增：索引命令
            if user_input.lower().startswith('index schema'):
                tokens = shlex.split(user_input)
                env = "dev"
                batch_size = 10
                force = False

                idx = 2
                while idx < len(tokens):
                    token = tokens[idx]
                    if token == "--env" and idx + 1 < len(tokens):
                        env = tokens[idx + 1]
                        idx += 2
                        continue
                    if token == "--batch-size" and idx + 1 < len(tokens):
                        try:
                            batch_size = int(tokens[idx + 1])
                        except ValueError:
                            print("[ERR] --batch-size 必须是整数")
                            batch_size = 10
                        idx += 2
                        continue
                    if token == "--force":
                        force = True
                        idx += 1
                        continue
                    print(f"[ERR] 未识别的参数: {token}")
                    break
                else:
                    if env not in ("dev", "prod"):
                        print("[ERR] --env 仅支持 dev 或 prod")
                        continue

                    from src.metadata.schema_indexer import SchemaIndexer
                    from src.metadata.graph_store import GraphStore

                    print("\n开始索引数据库表...")
                    print(f"环境: {env}, 批量大小: {batch_size}, 强制重建: {force}")

                    indexer = SchemaIndexer(db_manager=db, env=env)
                    if force:
                        print("清除现有索引...")
                        indexer.clear_progress()
                        GraphStore(env=env).clear_all()
                        print("[OK] 清除完成")

                    try:
                        result = indexer.index_all_databases(batch_size=batch_size)
                    except Exception as e:
                        print(f"[ERR] 索引失败: {e}")
                        continue

                    print("\n" + "=" * 60)
                    print("索引完成")
                    print("=" * 60)
                    print(f"状态: {'成功' if result.success else '部分失败'}")
                    print(f"总表数: {result.total_tables}")
                    print(f"已索引: {result.indexed_tables}")
                    print(f"耗时: {result.elapsed_seconds:.2f} 秒")

                    if result.failed_tables:
                        print(f"\n失败的表 ({len(result.failed_tables)}):")
                        for table in result.failed_tables:
                            print(f"  - {table}")

                    continue

            # ========== Agent Mode 处理 ==========

            # 如果启用了 agent-mode，使用 Orchestrator 处理
            if args.agent_mode and orchestrator:
                print("使用 Orchestrator 处理请求...")
                agent_context = orchestrator.process(user_input)

                # 处理需要澄清的情况
                if agent_context.intent and agent_context.intent.need_clarify:
                    print(f"\n[需要澄清] {agent_context.intent.reasoning or '请提供更多细节'}")
                    if agent_context.intent.params:
                        print("已识别的参数:")
                        for key, value in agent_context.intent.params.items():
                            print(f"  {key}: {value}")
                    continue

                # 处理安全检查失败
                if agent_context.is_safe is False:
                    print("安全检查未通过，操作已取消")
                    continue

                # 处理 ReviewAgent 确认分支
                if (
                    hasattr(agent_context.execution_result, "next_action")
                    and agent_context.execution_result.next_action == "ask_user"
                ):
                    print(f"\n[执行确认] {agent_context.execution_result.message}")
                    confirm = input("确认执行此操作？(y/n) > ").strip().lower()
                    if confirm != "y":
                        print("操作已取消")
                        continue
                    agent_context = orchestrator.process(user_input, user_confirmation=True)

                # 显示执行结果
                if agent_context.execution_result:
                    if hasattr(agent_context.execution_result, "__iter__") and not isinstance(
                        agent_context.execution_result, (dict, str, bytes)
                    ):
                        print("\n[流式输出]")
                        for chunk in agent_context.execution_result:
                            if chunk.get("type") == "thinking":
                                print(f"[thinking] {chunk.get('content', '')}", end="", flush=True)
                            elif chunk.get("type") == "content":
                                print(chunk.get("content", ""), end="", flush=True)
                        print()
                    else:
                        print("\n执行结果:")
                        print(f"{agent_context.execution_result}")

                    # 记录操作指标
                    if hasattr(agent_context, 'intent') and agent_context.intent:
                        op_type = agent_context.intent.type if hasattr(agent_context.intent, 'type') else "unknown"
                        metrics_collector.record_operation(
                            operation_type=op_type,
                            success=True,
                            duration=0.0,  # 简化处理
                            operation_id=agent_context.intent.operation_id if hasattr(agent_context.intent, 'operation_id') else "unknown"
                        )
                else:
                    print("未获得执行结果")

                continue

            # ========== 智能意图识别 ==========

            # Check if it looks like SQL
            first_word = user_input.lower().split()[0] if user_input else ""
            is_sql = first_word in ['select', 'show', 'describe', 'desc', 'explain', 'update', 'delete', 'insert', 'drop', 'alter', 'truncate']

            if not is_sql:
                # 使用对话引擎处理输入
                response = dialogue_engine.process_input(user_input)
                
                # 如果不是执行状态，显示消息并继续（等待下一次输入）
                if response.state != DialogueState.EXECUTING:
                    print(f"\n[助手] {response.message}")
                    if response.options:
                        for i, opt in enumerate(response.options):
                            print(f"  {chr(65+i)}. {opt}")
                    continue
                
                # 如果是执行状态，使用澄清后的意图进行执行
                print(f"\n[助手] {response.message}")
                query_to_execute_text = response.intent_description or user_input
                # 解析代词引用 (Double check, although DialogueEngine already did it)
                query_to_execute_text = context_memory.resolve_reference(query_to_execute_text)
                
                print(f"🔄 正在根据意图执行: {query_to_execute_text}")
                
                # 重置对话引擎状态
                dialogue_engine.reset()

                # 尝试智能意图识别
                print("🔍 正在识别操作意图...")
                intent_result = intent_recognizer.recognize(query_to_execute_text)

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
                        sql_to_execute = exec_result.sql if hasattr(exec_result, 'sql') else None
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

                    # 使用 SlotTracker 提取槽位
                    extracted_slots = slot_tracker.extract(query_to_execute_text)
                    if extracted_slots:
                        print(f"📋 提取的槽位: {extracted_slots}")

                    # 使用 QueryRewriter 重写查询（替换代词）
                    # 注意：DialogueEngine 已经做过代词替换，这里可能再次替换，但应该无害
                    rewritten_query = query_rewriter.rewrite(query_to_execute_text, extracted_slots)
                    if rewritten_query != query_to_execute_text:
                        print(f"🔄 查询重写: '{query_to_execute_text}' -> '{rewritten_query}'")
                    
                    try:
                        # 调用 LLMClient.generate_sql 并传入上下文
                        result = llm.generate_sql(
                            user_query=rewritten_query,
                            schema_context=schema_context,
                            context=extracted_slots
                        )

                        # 检查是否有验证错误
                        if result.get('intent') == 'error':
                            print(f"❌ {result.get('reasoning', '查询生成失败')}")
                            if result.get('warnings'):
                                for warning in result['warnings']:
                                    print(f"   ⚠️ {warning}")
                            continue

                        print("-" * 30)
                        print(f"🤖 生成的 SQL:\n{result['sql']}")
                        print(f"💡 思考过程: {result.get('reasoning', '无')}")
                        if result.get('warnings'):
                            print(f"⚠️ 警告:")
                            for warning in result['warnings']:
                                print(f"   - {warning}")
                        print("-" * 30)

                        # 使用 FeedbackParser 处理用户反馈
                        feedback_input = interaction.ask_feedback("❓ 是否执行此查询？(y/n/纠正) > ")
                        feedback = feedback_parser.parse(feedback_input)

                        if feedback.type == "reject":
                            print("❌ 操作已取消")
                            continue
                        elif feedback.type == "correction":
                            # 使用纠正后的查询重新执行
                            corrected_query = feedback.content
                            print(f"🔄 使用纠正后的查询: '{corrected_query}'")
                            try:
                                result = llm.generate_sql(
                                    user_query=corrected_query,
                                    schema_context=schema_context,
                                    error_context=f"Previous query was: {rewritten_query}. User correction: {corrected_query}",
                                    context=extracted_slots
                                )
                                if result.get('intent') == 'error':
                                    print(f"❌ {result.get('reasoning', '查询生成失败')}")
                                    continue
                                print(f"🤖 新生成的 SQL:\n{result['sql']}")
                            except Exception as e:
                                print(f"❌ 纠正查询生成失败: {e}")
                                llm.add_error_to_history(corrected_query, str(e))
                                continue

                        # confirm 或其他情况继续执行
                        sql_to_execute = result['sql']
                        base_filename = result.get('filename', 'query_result')
                        export_sheet_name = result.get('sheet_name', 'Sheet1')

                    except Exception as e:
                        print(f"❌ AI 生成失败: {e}")
                        llm.add_error_to_history(query_to_execute_text, str(e))
                        continue
            else:
                # 直接 SQL 输入
                is_valid, reason = validate_direct_query_sql(user_input)
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
                    # 使用 CLIPreview 显示结果
                    cli_preview.show(df, title="查询结果预览")

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
