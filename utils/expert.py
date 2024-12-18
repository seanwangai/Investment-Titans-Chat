from utils.quota import check_quota, use_quota, get_quota_display  # 使用新的函数名
from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError
from openai import AsyncOpenAI  # 改用异步客户端
import logging
import time
import tiktoken
import asyncio
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import backoff  # 添加到导入列表
from datetime import datetime, timedelta
import sys
import os
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import random

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 在文件开头添加更详细的日志格式设置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# X-AI API 配置
client = AsyncOpenAI(  # 改用异步客户端
    api_key=st.secrets.get("XAI_API_KEY", ""),
    base_url=st.secrets.get("XAI_API_BASE", "https://api.x.ai/v1")
)

# 创建线程池
executor = ThreadPoolExecutor(max_workers=10)

# 获取 token 计数器
encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 使用的编码器

MAX_TOKENS = 131072  # Grok 最大 token 限制
SYSTEM_PROMPT_TEMPLATE = """你是著名的投资专家 {name}。
以下是你的投资理念和知识库内容。请始终基于这些内容来回答问题，确保每个回答都体现出你独特的投资思维和方法论：

{knowledge}

回答要求：
1. 每个回答都必须体现出你的核心投资理念
2. 用具体的投资案例或经验来支持你的观点
3. 保持你独特的思维方式和表达风格
4. 回答要简洁明了，突出重点
5. 如果问题超出你的专业范围或与你的投资理念不符，请诚实地说明
6. 分析 thesis 时，请：
   - 指出潜在的问题和风险
   - 提供具体的改进建议
   - 分享类似案例的经验
   - 建议可行的解决方案

"""


def truncate_text(text, max_tokens):
    """截断文本以确保不超过最大 token 限制"""
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text

    # 计算需要保留的中间部分的 token 数量
    middle_tokens = max_tokens

    # 计算开始和结束的位置
    total_tokens = len(tokens)
    remove_tokens = total_tokens - middle_tokens

    # 前面保留更多内容（70%），后面少一些（30%）
    remove_front = int(remove_tokens * 0.3)
    remove_back = remove_tokens - remove_front

    # 保留中间部分的 tokens
    start_idx = remove_front
    end_idx = total_tokens - remove_back

    # 记录截断信息
    logger.info(f"文本被截断：总tokens={total_tokens}, "
                f"保留tokens={middle_tokens}, "
                f"前面删除={remove_front}, "
                f"后面删除={remove_back}")

    # 返回截断后的文本
    return (
        f"...[前面已省略 {remove_front} tokens]...\n\n" +
        encoding.decode(tokens[start_idx:end_idx]) +
        f"\n\n...[后面已省略 {remove_back} tokens]..."
    )


logger = logging.getLogger(__name__)


# 添加请求限制管理
class RateLimiter:
    def __init__(self, requests_per_second=1):
        self.requests_per_second = requests_per_second
        self.last_request_time = None
        self._lock = None

    @property
    def lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self):
        async with self.lock:
            now = datetime.now()
            if self.last_request_time is not None:
                time_since_last = (
                    now - self.last_request_time).total_seconds()
                if time_since_last < 1/self.requests_per_second:
                    wait_time = 1/self.requests_per_second - time_since_last
                    await asyncio.sleep(wait_time)
            self.last_request_time = datetime.now()


# 创建全局限速器实例
rate_limiter = RateLimiter(requests_per_second=1)


class ExpertAgent:
    def __init__(self, name, knowledge_base, avatar=None):
        self.name = name
        self.original_knowledge = knowledge_base  # 保存原始知识库
        self.avatar = avatar or "🤖"
        self.chat_history = []  # 保存对话历史
        self.max_history = 5  # 保存最近的5轮对话
        self.history_tokens = 0  # 追踪历史对话使用的 tokens

        # 计算系统提示的基本 token 数量（不包含知识库内容）
        base_prompt = SYSTEM_PROMPT_TEMPLATE.format(name=name, knowledge="")
        base_tokens = len(encoding.encode(base_prompt))

        # 计算每轮对话预留的 token 数（包括问题和回答）
        self.tokens_per_turn = 2000

        # 为知识库内容预留的最大 token 数
        self.base_tokens = base_tokens
        self.adjust_knowledge_base()

    def count_tokens(self, text):
        """计算文本的 token 数量"""
        return len(encoding.encode(text))

    def adjust_knowledge_base(self):
        """根据对话历史动态调整知识库大小"""
        # 计算可用于知识库的 tokens
        available_tokens = (MAX_TOKENS - self.base_tokens -
                            self.history_tokens - self.tokens_per_turn)

        # 确保至少保留一定比例的知识库内容
        min_knowledge_tokens = min(
            80000, available_tokens)  # 提高最小保留量到80k tokens
        max_knowledge_tokens = max(min_knowledge_tokens, available_tokens)

        # 截断知识库内容
        self.knowledge_base = truncate_text(
            self.original_knowledge, max_knowledge_tokens)

        # 记录调整信息
        logger.info(f"知识库调整：历史tokens={self.history_tokens}, "
                    f"可用tokens={available_tokens}, "
                    f"分配给知识库tokens={max_knowledge_tokens}")

    def get_system_prompt(self):
        """获取当前的系统提示词"""
        return SYSTEM_PROMPT_TEMPLATE.format(
            name=self.name,
            knowledge=self.knowledge_base
        )

    def update_chat_history(self, question, answer):
        """更新对话历史"""
        # 计算新对话的 tokens
        new_qa_tokens = self.count_tokens(f"Q: {question}\nA: {answer}")

        # 如果需要移除旧对话
        while (self.history_tokens + new_qa_tokens > MAX_TOKENS * 0.3 and  # 历史最多占用30%
               self.chat_history):
            # 移除最早的对话并减少 token 计数
            old_q, old_a = self.chat_history.pop(0)
            removed_tokens = self.count_tokens(f"Q: {old_q}\nA: {old_a}")
            self.history_tokens -= removed_tokens
            logger.info(f"移除旧对话，释放 {removed_tokens} tokens")

        # 添加新对话
        self.chat_history.append((question, answer))
        self.history_tokens += new_qa_tokens

        logger.info(f"添加新对话，使用 {new_qa_tokens} tokens，"
                    f"当前历史总计 {self.history_tokens} tokens")

        self.adjust_knowledge_base()  # 重新调整知识库大小

    # 修改装饰器
    @retry(
        retry=retry_if_exception_type(
            (APIConnectionError, APITimeoutError, RateLimitError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3)
    )
    async def get_response(self, prompt):
        """获取专家回应"""
        try:
            logger.info(f"开始处理专家 {self.name} 的回应")

            # 安全地获取当前模型
            current_model = getattr(
                st.session_state, 'current_model', 'grok-beta')

            if current_model in ["gemini-2.0-flash-exp", "gemini-1.5-flash"]:
                from .gemini_handler import generate_gemini_response
                expert_prompt = f"你现在扮演 {self.name}。请基于以下投资理念回答问题：\n\n{self.knowledge_base}\n\n问题：{prompt}"
                logger.info(
                    f"发送到 {current_model} 的提示词: {expert_prompt[:200]}...")

                # 在线程池中运行同步的 Gemini 请求
                loop = asyncio.get_event_loop()
                answer = await loop.run_in_executor(
                    None,
                    lambda: generate_gemini_response(
                        expert_prompt, current_model)
                )
            else:
                # 等待速率限制（只对 Grok 应用）
                await rate_limiter.acquire()

                # 直接调用 API，不使用 create_task
                response = await client.chat.completions.create(
                    model="grok-beta",
                    messages=[
                        {"role": "system", "content": self.get_system_prompt()},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                answer = response.choices[0].message.content

            self.update_chat_history(prompt, answer)
            return answer

        except Exception as e:
            logger.error(f"{self.name} 处理失败: {str(e)}")
            raise


async def get_responses_async(experts, prompt):
    start_time = time.time()
    logger.info(f"开始并发处理所有专家回应，时间: {start_time}")

    async def get_expert_response(expert):
        try:
            response = await expert.get_response(prompt)
            return expert, response, time.time()
        except Exception as e:
            logger.error(f"专家 {expert.name} 处理失败: {str(e)}")
            return expert, f"抱歉，生成回应时出现错误: {str(e)}", time.time()

    # 创建所有任务并立即开始执行
    tasks = [asyncio.create_task(get_expert_response(expert))
             for expert in experts]

    # 使用 as_completed 按完成顺序获取结果
    for response_task in asyncio.as_completed(tasks):
        expert, response, finish_time = await response_task
        logger.info(
            f"专家 {expert.name} 响应完成，耗时: {finish_time - start_time:.2f}秒")
        yield expert, response

    # 收集所有响应用于生成总结
    all_responses = []
    for task in tasks:
        result = await task
        all_responses.append(result)

    responses = [resp for _, resp, _ in all_responses]

    # 生成总结
    summary = await generate_summary(prompt, responses, experts)
    yield st.session_state.titans, summary


async def generate_summary(prompt, responses, experts):
    """生成总结"""
    logger.info("开始生成总结...")

    # 动态构建专家回应列表
    expert_responses = []
    for expert, response in zip(experts, responses):
        expert_responses.append(f"{expert.name}：{response}")
        logger.info(f"整合 {expert.name} 的回应到总结中")

    summary_prompt = f"""作为 Investment Masters，你的任务是总结和整合各位投资大师的观点。

以下是各位大师对这个 thesis 的分析和建议：

{chr(10).join(expert_responses)}

请你：
1. 总结各位大师发现的主要问题
2. 归纳他们提出需要多深入研究什麼
3. 找出专家们的共识和分歧
4. 提供一个整合的行动建议
"""

    logger.info(f"生成总结的提示词: {summary_prompt[:200]}...")

    try:
        # 使用异步 API 调用
        summary_response = await client.chat.completions.create(
            model="grok-beta",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.7
        )
        summary = summary_response.choices[0].message.content
        return summary
    except Exception as e:
        error_msg = "生成总结时出错"
        logger.error(error_msg)
        logger.exception(e)
        return "抱歉，无法生成总结。"

__all__ = ['ExpertAgent', 'get_responses_async', 'generate_summary']
