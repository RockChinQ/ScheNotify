import time
import datetime
import asyncio

from pkg.core import entities as core_entities
from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类


# 注册插件
@register(name="ScheNotify", description="使用自然语言计划日程", version="0.1", author="RockChinQ")
class MyPlugin(BasePlugin):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        pass

    # 异步初始化
    async def initialize(self):
        async def check_loop():
            while True:
                await self.check_loop()
                await asyncio.sleep(60)

        asyncio.create_task(check_loop())

    async def check_loop(self):
        
        now = datetime.datetime.now()
        self.ap.logger.info(f"check_loop: {now}")
        self.ap.logger.info(f"scheduled_event: {self.scheduled_event}")
        for event in self.scheduled_event:
            if now >= event["time"]:
                await self.ap.platform_mgr.adapters[0].send_message(
                    event["session_type"],
                    event["session_id"],
                    '[Notify]'+event["message"]
                )
                self.scheduled_event.remove(event)

    scheduled_event: list[dict[str,str]] = []
    """[
    {
        "time": datetime.datetime(),
        "message": "吃饭",
        "session_type": "person",
        "session_id": 123456
    }
    ]"""

    async def sche_notify(self, date: datetime.datetime, message: str, session_type: str, session_id: str):
        self.scheduled_event.append({
            "time": date,
            "message": message,
            "session_type": session_type,
            "session_id": session_id
        })

    async def get_scheduled_event(self, session_type: str, session_id: str):
        return [
            event for event in self.scheduled_event if event["session_type"] == session_type and event["session_id"] == session_id
        ]
    
    async def delete_scheduled_event(self, event: dict):
        self.scheduled_event.remove(event)
    
    @llm_func("get_current_time_str")
    async def get_current_time_str(self, query):
        """这个函数可以获取当前时间的字符串
        以下情况时调用：
        - 用户直接询问当前时间时
        - 每次用户让你计划一个日程提醒时，都先调用这个函数获取当前时间，再传递计划时间给schedule_notify函数

        Returns:
            str: 当前时间的字符串
        """
        # 返回UTC+8时间
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @llm_func("schedule_notify")
    async def schedule_notify(self, query: core_entities.Query, time_str: str, message: str):
        """这个函数可以让你计划一个日程提醒，调用这个函数之前，必须先调用get_current_time_str获取最新的当前时间。
        回复用户时不需要精确到秒，因为程序是每分钟检查一次的，只要精确到分钟即可。

        Args:
            time_str(str): 时间字符串，格式为"%Y-%m-%d %H:%M:%S"
            message(str): 提醒内容

        Returns:
            str: 计划成功的提示语，或者计划失败的报错
        """
        # 将时间字符串转换为时间戳
        time_stamp = time.mktime(time.strptime(time_str, "%Y-%m-%d %H:%M:%S"))
        # 计算当前时间戳
        current_time_stamp = time.time()
        
        # 如果计划时间已经过去，则返回错误
        if time_stamp <= current_time_stamp:
            return "计划时间已经过去"

        real_date = datetime.datetime.fromtimestamp(time_stamp)
        
        # 计划时间未来，调用异步函数
        await self.sche_notify(real_date, message, query.session.launcher_type.value, query.session.launcher_id)
        return f"计划成功:\n将在{real_date}提醒您：{message}"

    @handler(GroupCommandSent)
    @handler(PersonCommandSent)
    async def on_command_sent(self, ctx: EventContext):
        if ctx.event.command == 'sche':
            ctx.prevent_default()

            scheduled_events = await self.get_scheduled_event(ctx.event.launcher_type, ctx.event.launcher_id)

            reply = ''

            if scheduled_events is None or len(scheduled_events) == 0:
                reply = '[Notify]没有计划中的提醒'
            else:
                reply = '[Notify]计划中的提醒：\n'
                index = 1
                for event in scheduled_events:
                    reply += f'#{index} {event["time"]}：{event["message"]}\n'
                    index += 1

            ctx.add_return(
                'reply',
                [
                    reply
                ]
            )
        elif ctx.event.command == 'dsche':
            ctx.prevent_default()

            if len(ctx.event.params) == 0:
                ctx.add_return(
                    'reply',
                    [
                        '[Notify]命令格式!dsche <index>，例如!dsche 1。请先使用!sche查看计划中的提醒'
                    ]
                )
                return

            index = int(ctx.event.params[0]) - 1

            scheduled_events = await self.get_scheduled_event(ctx.event.launcher_type, ctx.event.launcher_id)

            if index < 0 or index >= len(scheduled_events):
                ctx.add_return(
                    'reply',
                    [
                        '[Notify]索引超出范围'
                    ]
                )
                return
            
            event = scheduled_events[index]

            await self.delete_scheduled_event(event)

            ctx.add_return(
                'reply',
                [
                    f'[Notify]已删除提醒：{event["time"]} {event["message"]}'
                ]
            )

    # 插件卸载时触发
    def __del__(self):
        pass
