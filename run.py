import asyncio
from app.core.AsyncMastControl import MastControl

if __name__ == '__main__':
    md_path = r'D:\pythonproject\Ai_Blogger\Md'
    playwright_driver_data = r'D:\pythonproject\Ai_Blogger\driver\playwright_data'
    mast_control = MastControl(md_path=md_path, playwright_driver_data=playwright_driver_data)

    # 运行模式选择：
    # - "monitor": 监控热榜变化并自动发布
    # - "publish": 发布测试内容
    asyncio.run(mast_control.run(mode="monitor"))
