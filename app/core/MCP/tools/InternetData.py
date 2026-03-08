from app.core.AiAgent.IntertSearch import internet_search, internet_search_async
from app.core.AiAgent.llm import LLM

SYSTEM_PROMPT = """
**角色定位**
你是一位严谨的信息整理专家。你的唯一任务是对用户提供的原始信息进行**零创作、零增删**的清洗、归类和结构化重组，确保输出内容与输入材料在事实、观点和数据上完全一致。你只整理，不创作、不解读、不提供建议。

---

### **核心工作原则**
1.  **绝对忠实**：所有输出内容必须严格基于输入信息。不添加任何原文未明确提及的结论、观点或预测。
2.  **极致客观**：以中立态度呈现信息，包括其中的矛盾、争议或多方观点。不使用倾向性语言。
3.  **结构清晰**：将杂乱信息按内在逻辑重新组织，使其层次分明、易于检索和理解。
4.  **来源透明**：尽可能保留或关联信息来源，方便追溯与验证。

---

### **工作流程与指令**

#### **第一步：信息清洗与提取**
*   移除明显的广告、无关链接、重复语句等噪声。
*   直接提取原文中的核心事实、数据、观点、定义和事件。

#### **第二步：结构化重组**
请严格按照以下维度对信息进行归类与组织：

1.  **信息概览**
    *   **主题**：用1-2句话概括所有信息的核心主题。
    *   **来源类型**：标注信息主要来自（如：学术论文、新闻报道、行业报告、论坛讨论等）。

2.  **事实与数据清单**
    *   以条目形式列出所有客观事实、统计数据、事件时间点等。
    *   格式：`- [数据/事实]：直接引用或精确转述（若可追溯，标注来源编号）`

3.  **观点与论述归纳**
    *   中立地归纳原文中出现的不同观点、立场或理论。
    *   格式：`- [观点持有方/理论名称]：其核心主张是...（直接归纳原文）`

4.  **核心概念与术语表**
    *   提取并定义信息中出现的专业术语、缩写、专有名词。
    *   格式：`- **[概念A]**：原文中的定义或解释。`

5.  **时间线与关系梳理**（若信息适用）
    *   按时间顺序排列关键事件。
    *   或梳理人物、组织、概念之间的相互关系（如隶属、因果、对立）。

6.  **冲突与存疑标注**
    *   明确指出信息中存在的**数据矛盾、观点对立、逻辑断层**之处。
    *   明确指出信息中**缺失的关键部分**或未解答的疑问。

#### **第三步：输出格式——“结构化知识档案”**
请将整理结果以如下格式输出：

```
### 📚 信息整理报告： [核心主题]

#### 一、概览
*   **整理主题**：[主题]
*   **来源特征**：[例如：3篇行业报告，5篇新闻，2份用户调研]

#### 二、事实与数据
1.  [事实1]
2.  [数据1，标明数值与单位]
3.  ...

#### 三、观点归纳
*   **观点A**：[主张简述]
*   **观点B**：[主张简述]
*   ...

#### 四、关键概念
*   **[概念1]**：[定义]
*   **[概念2]**：[定义]
*   ...

#### 五、逻辑/时间脉络
*   [以时间线、步骤或因果链形式简要描述]

#### 六、不一致与缺口
*   **矛盾**：[例如：A来源称X数据为10%，B来源称其为15%]
*   **缺口**：[例如：缺少关于Y事件的具体原因分析；Z技术的未来影响未提及]
```

---

### **您的使用方式**
1.  您只需将待整理的原始文本/链接发送给我。
2.  我严格遵循以上流程，输出一份**纯粹、结构化、无衍生**的知识档案。
3.  该档案可直接用于存档、分析、或作为AI学习新知识的精准材料。

---
"""


class InternetData:
    """
    互联网数据获取与整理
    """

    def __init__(self, client, model_name="deepseek-chat"):
        self.client = client
        self.llm = LLM()
        self.model_name = model_name

    def get_internet_data(self, query):
        """
        获取互联网数据

        Args:
            query (str): 查询关键词

        Returns:
            dict: 包含整理后的内容及状态信息
                  {
                      "success": bool,
                      "message": str,
                      "content": str
                  }
        """
        try:
            internet_data = internet_search(query)
            if not internet_data:
                return {"success": False, "message": "未找到相关数据", "content": ""}

            internet_data = self.__parse_internet_data(internet_data)
            if not internet_data:
                return {"success": False, "message": "数据解析失败", "content": ""}

            content, new_msg_history = self.llm.get_response_from_llm(
                user_prompt=internet_data,
                client=self.client,
                model=self.model_name,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.7
            )

            return {"success": True, "message": "操作成功", "content": content}

        except Exception as e:
            return {"success": False, "message": f"操作失败: {str(e)}", "content": ""}

    async def get_internet_data_async(self, query):
        """
        获取互联网数据（异步版本）

        Args:
            query (str): 查询关键词

        Returns:
            dict: 包含整理后的内容及状态信息
        """
        try:
            internet_data = await internet_search_async(query)
            if not internet_data:
                return {"success": False, "message": "未找到相关数据", "content": ""}

            internet_data = self.__parse_internet_data(internet_data)
            if not internet_data:
                return {"success": False, "message": "数据解析失败", "content": ""}

            # 【关键修改】使用异步方法
            content, new_msg_history = await self.llm.get_response_from_llm_async(
                user_prompt=internet_data,
                client=self.client,
                model=self.model_name,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.7
            )

            return {"success": True, "message": "操作成功", "content": content}

        except Exception as e:
            return {"success": False, "message": f"操作失败：{str(e)}", "content": ""}

    def __parse_internet_data(self, internet_data: list[dict], max_articles: int = 3):
        """
        解析互联网数据

        :param internet_data: 互联网数据 [{"summary": "xxx", "content": "xxx}]
        :param max_articles: 最大解析的文章数量，默认为None（不限制）
        :return: 整理后的内容
        """
        result_data = ""
        # 如果指定了最大文章数，则截取前max_articles篇
        data_to_parse = internet_data[:max_articles] if max_articles else internet_data

        for index, item in enumerate(data_to_parse, start=1):
            summary = item.get("content", "")
            result_data += f"## 第{index}篇:\n {summary}\n"
        return result_data


if __name__ == '__main__':
    llm = LLM()
    client = llm.create_client("deepseek-chat")
    InternetData = InternetData(client, "deepseek-chat")
    content = InternetData.get_internet_data("中国covid19")
    print(content)
