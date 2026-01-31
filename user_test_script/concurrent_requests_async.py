"""
并发发送20条消息到OpenAI兼容API的示例
使用 asyncio + AsyncOpenAI 实现异步并发
"""

import asyncio
import time
from openai import AsyncOpenAI

# 初始化异步客户端
client = AsyncOpenAI(
    base_url="http://127.0.0.1:8045/v1",
    api_key="sk-174d582f879f42e297a08aad2f9d7547"
)


async def send_message_async(message_id: int, content: str = "Hello") -> dict:
    """
    异步发送单条消息并返回结果
    
    Args:
        message_id: 消息编号
        content: 发送的消息内容
    
    Returns:
        包含消息ID和响应内容的字典
    """
    try:
        response = await client.chat.completions.create(
            model="gemini-3-pro-high",
            messages=[{"role": "user", "content": content}]
        )
        return {
            "id": message_id,
            "status": "success",
            "content": response.choices[0].message.content
        }
    except Exception as e:
        return {
            "id": message_id,
            "status": "error",
            "error": str(e)
        }


async def run_concurrent_requests_async(
    num_requests: int = 20,
    messages: list = None,
    semaphore_limit: int = 20
):
    """
    异步并发执行多个API请求
    
    Args:
        num_requests: 请求数量
        messages: 自定义消息列表
        semaphore_limit: 信号量限制（控制最大并发数）
    """
    # 如果没有提供消息列表，生成默认消息
    if messages is None:
        messages = [f"Hello, this is message #{i+1}" for i in range(num_requests)]
    
    print(f"开始异步并发发送 {num_requests} 条消息...")
    print(f"最大并发数: {semaphore_limit}")
    print("-" * 50)
    
    start_time = time.time()
    
    # 使用信号量控制并发数（可选，防止过载）
    semaphore = asyncio.Semaphore(semaphore_limit)
    
    async def limited_send(msg_id, content):
        async with semaphore:
            return await send_message_async(msg_id, content)
    
    # 创建所有任务
    tasks = [
        limited_send(i, messages[i])
        for i in range(num_requests)
    ]
    
    # 并发执行所有任务
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # 打印结果
    success_count = 0
    error_count = 0
    
    for result in results:
        if isinstance(result, Exception):
            error_count += 1
            print(f"[✗] 异常: {result}")
        elif result["status"] == "success":
            success_count += 1
            print(f"[✓] 消息 #{result['id']+1}: {result['content'][:50]}...")
        else:
            error_count += 1
            print(f"[✗] 消息 #{result['id']+1}: {result['error']}")
    
    print("-" * 50)
    print(f"完成！总耗时: {elapsed:.2f} 秒")
    print(f"成功: {success_count}, 失败: {error_count}")
    print(f"平均每条消息: {elapsed/num_requests:.2f} 秒")
    
    return results


# ============================================================
# 另一种写法：使用 asyncio.TaskGroup (Python 3.11+)
# ============================================================

async def run_with_task_group(num_requests: int = 20):
    """
    使用 Python 3.11+ 的 TaskGroup 实现并发
    """
    messages = [f"Hello #{i+1}" for i in range(num_requests)]
    results = []
    
    print(f"使用 TaskGroup 发送 {num_requests} 条消息...")
    start_time = time.time()
    
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(send_message_async(i, messages[i]))
            for i in range(num_requests)
        ]
    
    results = [task.result() for task in tasks]
    
    elapsed = time.time() - start_time
    print(f"完成！总耗时: {elapsed:.2f} 秒")
    
    return results


if __name__ == "__main__":
    # 运行异步并发请求
    asyncio.run(run_concurrent_requests_async(num_requests=20))
