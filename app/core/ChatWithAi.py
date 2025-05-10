import json
import os
from typing import Generator

import requests.exceptions


class ChatWithAi:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.deepseek.com/chat/completions"
        self.default_params = {
            "model": "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 2000,
        }

    def handle_normal_response(self, response: requests.Response) -> str:
        """处理普通响应"""
        try:
            response_data = response.json()
            if "choices" in response_data and response_data["choices"]:
                # 提取回复信息
                content = response_data["choices"][0]["message"]["content"]
                return content
            return "未收到有效响应"
        except Exception as e:
            print(f"响应处理失败: {e}")
            return ""

    def chat_completion(self, prompt: str, stream: bool = False) -> str:
        """调用DeepSeek API进行聊天"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        data = json.dumps({
            **self.default_params,
            "stream": stream,
            "messages": [
                {
                    "role": "system",
                    "content": """# 智能助手提示词：幽默的知乎热榜回复博主

                                    ## 定位
                                    - 擅长用幽默手法解构知乎热榜严肃议题
                                    - 保持专业性与趣味性的黄金分割比例
                                    - 打造「笑着读完，突然顿悟」的内容体验

                                    ## 核心能力
                                    1. **幽默元素适配器**
                                       - 谐音梗/夸张类比/神转折自动生成模块
                                       - 学术概念趣味降维系统（例：量子力学→相亲观察者效应）
                                    2. **热榜话题整容术**
                                       - 将热点事件转化为「如果...会怎样」脑洞模式
                                       - 冷知识弹药库智能匹配当前话题
                                    3. **互动埋梗设计**
                                       - 段子接龙触发式结尾（预留UGC创作空间）
                                       - 彩蛋评论自动生成（5种热门梗模板）
                                    4. **擅长使用一些符号或者图片**
                                       - 使用一些小符号使得文章生动形象
                                       - 吸引读者阅读兴趣

                                    ## 知识储备
                                    - 全网脱口秀剧本结构数据库（含callback技巧）
                                    - 知乎年度神回复TOP100幽默模式分析
                                    - 跨学科冷笑话生成公式（涵盖38个专业领域）
                                    - 幽默安全校验库（规避地域/性别/年龄敏感点）

                                    ## 使用方法
                                    - 用户将提供给你一个热榜问题
                                    - 请你编写回复
                                    - 输出时： 文章格式优美，且用户可以直接复制粘贴
                                """
                },
                {
                    "content": f"{prompt}",
                    "role": "user"
                }
            ]
        })

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                data=data,
                stream=stream,
                timeout=120
            )
            response.raise_for_status()

            if stream:
                return self.handle_stream_response(response)
            return self.handle_normal_response(response)

        except requests.exceptions.RequestException as e:
            print(f"API请求失败: {e}")
            return ""

    def run(self, input):
        return self.chat_completion(input)


if __name__ == '__main__':
    chat = ChatWithAi(api_key="sk-af0cc0ea7d764e4093ce7eca05f07d0b")
    input = "中日经济高层对话达成二十项重要共识，包括加强养老服务、护理等领域务实合作等，还有哪些信息值得关注？"
    print(chat.run(input))
