# MCP工具映射模块
# 提供工具名称和函数名的映射关系，用于在MCP工具集成中执行工具函数。

# 新增工具定义：get_internet_data
GetInternetData = {
    "type": "function",
    "function": {
        "name": "get_internet_data",
        "description": "从互联网搜索并整理指定主题的数据，返回结构化内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                }
            },
            "required": ["query"]
        },
        "return": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "description": "是否成功获取并整理数据"
                },
                "message": {
                    "type": "string",
                    "description": "操作结果的消息描述"
                },
                "content": {
                    "type": "string",
                    "description": "整理后的结构化内容"
                }
            }
        }
    }
}

# 工具映射
ALL_TOOLS_MAP = {
    "get_internet_data": "get_internet_data"
}

# 所有工具列表
ALL_TOOLS = [GetInternetData]
