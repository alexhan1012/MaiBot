import asyncio
import time
from maim_message import MessageServer

from src.common.remote import TelemetryHeartBeatTask
from src.manager.async_task_manager import async_task_manager
from src.chat.utils.statistic import OnlineTimeRecordTask, StatisticOutputTask
from src.chat.emoji_system.emoji_manager import get_emoji_manager
from src.chat.message_receive.chat_stream import get_chat_manager
from src.config.config import global_config
from src.chat.message_receive.bot import chat_bot
from src.common.logger import get_logger
from src.common.server import get_global_server, Server
from src.mood.mood_manager import mood_manager
from src.chat.knowledge import lpmm_start_up
from rich.traceback import install
from src.migrate_helper.migrate import check_and_run_migrations
# from src.api.main import start_api_server

# 导入新的插件管理器
from src.plugin_system.core.plugin_manager import plugin_manager

# 导入消息API和traceback模块
from src.common.message import get_global_api

# 插件系统现在使用统一的插件加载器

install(extra_lines=3)

logger = get_logger("main")


class MainSystem:
    def __init__(self):
        # 使用消息API替代直接的FastAPI实例
        self.app: MessageServer = get_global_api()
        self.server: Server = get_global_server()

    async def initialize(self):
        """初始化系统组件"""
        logger.info(f"正在唤醒{global_config.bot.nickname}......")

        # 其他初始化任务
        await asyncio.gather(self._init_components())

        logger.info(f"""
--------------------------------
全部系统初始化完成，{global_config.bot.nickname}已成功唤醒
--------------------------------
如果想要自定义{global_config.bot.nickname}的功能,请查阅：https://docs.mai-mai.org/manual/usage/
或者遇到了问题，请访问我们的文档:https://docs.mai-mai.org/
--------------------------------
如果你想要编写或了解插件相关内容，请访问开发文档https://docs.mai-mai.org/develop/
--------------------------------
如果你需要查阅模型的消耗以及麦麦的统计数据，请访问根目录的maibot_statistics.html文件
""")

    async def _init_components(self):
        """初始化其他组件"""
        init_start_time = time.time()

        # 添加在线时间统计任务（记录机器人的在线运行时间,每60秒向数据库写入一次时间戳，用于统计机器人总运行时长）
        await async_task_manager.add_task(OnlineTimeRecordTask())

        # 添加统计信息输出任务（ 定期生成运行统计报告，每5分钟生成HTML格式的统计报告）
        await async_task_manager.add_task(StatisticOutputTask())

        # 添加遥测心跳任务（向远程服务器发送心跳包，监控系统健康状态。定期上报系统运行状态，便于远程监控和故障诊断）
        await async_task_manager.add_task(TelemetryHeartBeatTask())

        # 启动API服务器
        # start_api_server()
        # logger.info("API服务器启动成功")

        # 启动LPMM（启动Large Persona Memory Model，机器人的知识库系统）
        lpmm_start_up()

        # 加载所有actions，包括默认的和插件的（扫描并加载所有插件，包括内置和自定义插件）
        plugin_manager.load_all_plugins()

        # 初始化表情管理器（管理表情包识别、生成和发送）
        get_emoji_manager().initialize()
        logger.info("表情包管理器初始化成功")

        # 启动情绪管理器（管理机器人的情绪状态和个性表现）
        await mood_manager.start()
        logger.info("情绪管理器初始化成功")

        # 初始化聊天管理器（管理所有聊天流和消息上下文）
        await get_chat_manager()._initialize()
        asyncio.create_task(get_chat_manager()._auto_save_task())

        logger.info("聊天管理器初始化成功")

        # # 根据配置条件性地初始化记忆系统
        # if global_config.memory.enable_memory:
        #     if self.hippocampus_manager:
        #         self.hippocampus_manager.initialize()
        #         logger.info("记忆系统初始化成功")
        # else:
        #     logger.info("记忆系统已禁用，跳过初始化")

        # await asyncio.sleep(0.5) #防止logger输出飞了

        # 将bot.py中的chat_bot.message_process消息处理函数注册到api.py的消息处理基类中
        self.app.register_message_handler(chat_bot.message_process)
        self.app.register_custom_message_handler("message_id_echo", chat_bot.echo_message_process)

        await check_and_run_migrations() # 检查并执行数据库结构更新

        # 触发 ON_START 事件 （触发插件系统的ON_START事件：通知所有插件系统已启动完成，允许插件执行启动后的初始化逻辑。）
        from src.plugin_system.core.events_manager import events_manager
        from src.plugin_system.base.component_types import EventType

        await events_manager.handle_mai_events(event_type=EventType.ON_START)
        # logger.info("已触发 ON_START 事件")
        try:
            init_time = int(1000 * (time.time() - init_start_time))
            logger.info(f"初始化完成，神经元放电{init_time}次")
        except Exception as e:
            logger.error(f"启动大脑和外部世界失败: {e}")
            raise

    async def schedule_tasks(self):
        """调度定时任务"""
        while True:
            tasks = [
                get_emoji_manager().start_periodic_check_register(),
                self.app.run(),
                self.server.run(),
            ]

            await asyncio.gather(*tasks)

    # async def forget_memory_task(self):
    #     """记忆遗忘任务"""
    #     while True:
    #         await asyncio.sleep(global_config.memory.forget_memory_interval)
    #         logger.info("[记忆遗忘] 开始遗忘记忆...")
    #         await self.hippocampus_manager.forget_memory(percentage=global_config.memory.memory_forget_percentage)  # type: ignore
    #         logger.info("[记忆遗忘] 记忆遗忘完成")


async def main():
    """主函数"""
    system = MainSystem()
    await asyncio.gather(
        system.initialize(),
        system.schedule_tasks(),
    )


if __name__ == "__main__":
    asyncio.run(main())
