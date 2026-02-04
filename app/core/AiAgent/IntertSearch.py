import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures
import time
import re

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream",
    "Authorization": "Bearer b15c3f72b90f465e4513a9cfc5cafbc5:MWY5ZTFjZTAyNjY2ZTJkYTI3OTVhYmJk",
}


def xunfei_internet_search(query, max_retries=3):
    for attempt in range(max_retries):
        data = {
            "flow_id": "7393201966309593089",
            "uid": "123",
            "parameters": {"AGENT_USER_INPUT": query},
            "ext": {"bot_id": "adjfidjf", "caller": "workflow"},
            "stream": False,
        }

        try:
            response = requests.post(
                "https://xingchen-api.xf-yun.com/workflow/v1/chat/completions",
                json=data,
                headers=HEADERS,
                verify=True  # 默认为 True，表示验证 SSL 证书
            )

            if response.status_code == 200:
                json_response = response.json()
                try:
                    result = json_response["choices"][0]["delta"]["content"]
                    # 检查结果是否为空
                    if result and result.strip():
                        return result
                    else:
                        print(f"第 {attempt + 1} 次尝试：搜索结果为空")
                        if attempt < max_retries - 1:  # 不是最后一次尝试
                            time.sleep(2 ** attempt)  # 指数退避
                except (KeyError, json.JSONDecodeError) as e:
                    print(f"第 {attempt + 1} 次尝试：JSON解析错误: {str(e)}")
                    if attempt < max_retries - 1:  # 不是最后一次尝试
                        time.sleep(2 ** attempt)  # 指数退避
            else:
                print(f"第 {attempt + 1} 次尝试：HTTP错误: {response.status_code}")
                if attempt < max_retries - 1:  # 不是最后一次尝试
                    time.sleep(2 ** attempt)  # 指数退避

        except requests.exceptions.RequestException as e:
            print(f"第 {attempt + 1} 次尝试：请求异常: {str(e)}")
            if attempt < max_retries - 1:  # 不是最后一次尝试
                time.sleep(2 ** attempt)  # 指数退避

    print(f"已达到最大重试次数 ({max_retries})，搜索失败")
    return "无"


def internet_search(query):
    """
    使用讯飞星辰的互联网搜索功能进行搜索

    :param
    query: 搜索关键词

    :return:
    搜索结果列表，每个元素包含summary和content字段
    """
    result = []
    response = xunfei_internet_search(query)
    response = json.loads(response)
    if response:
        documents = response["output"]
        for document in documents:
            summary = document.get("summary", "空")  # 如果不存在则返回空字符串
            content = document.get("content", "空")  # 如果不存在则返回None
            re_ = {"summary": summary, "content": content}
            result.append(re_)
        return result
    else:
        response = "无"

    return response


if __name__ == '__main__':
    print(internet_search("诸葛亮"))
