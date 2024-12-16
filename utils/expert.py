from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError
import logging
import time
import tiktoken
import asyncio
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import backoff  # 添加到导入列表

# X-AI API 配置
client = OpenAI(
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


class RateLimiter:
    def __init__(self, requests_per_second=1):
        self.requests_per_second = requests_per_second
        self.last_request_time = 0

    def wait(self):
        """等待直到可以发送下一个请求"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        time_to_wait = (1.0 / self.requests_per_second) - \
            time_since_last_request

        if time_to_wait > 0:
            time.sleep(time_to_wait)

        self.last_request_time = time.time()


# 创建全局速率限制器
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

    # 定义重试装饰器
    @backoff.on_exception(
        backoff.expo,
        (APIConnectionError, APITimeoutError),
        max_tries=3,
        max_time=30
    )
    def get_response(self, prompt):
        """获取专家回应"""
        try:
            # 等待速率限制
            rate_limiter.wait()

            # 计算当前系统提示的 tokens
            system_prompt = self.get_system_prompt()
            system_tokens = self.count_tokens(system_prompt)
            prompt_tokens = self.count_tokens(prompt)

            logger.info(f"当前请求 tokens 统计：系统={system_tokens}, "
                        f"问题={prompt_tokens}, 历史={self.history_tokens}")

            response = client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            answer = response.choices[0].message.content
            self.update_chat_history(prompt, answer)
            return answer

        except APIConnectionError as e:
            error_msg = f"连接到 API 服务器失败: {str(e)}\n详细信息: {e.__dict__}"
            logger.error(error_msg)
            return "🔌 Connection lost... Let me try to reconnect and get back to you."

        except RateLimitError as e:
            error_msg = f"触发速率限制: {str(e)}\n详细信息: {e.__dict__}"
            logger.error(error_msg)
            return "⏳ The server is quite busy. Please give me a moment to catch up."

        except APITimeoutError as e:
            error_msg = f"API 请求超时: {str(e)}\n详细信息: {e.__dict__}"
            logger.error(error_msg)
            return "⌛ Taking longer than expected... Let me speed things up."

        except APIError as e:
            error_msg = f"API 错误: {str(e)}\n状态码: {e.status_code}\n响应: {e.response}\n详细信息: {e.__dict__}"
            logger.error(error_msg)
            return "🔧 Oops! Something went wrong. I'll fix it and try again."

        except Exception as e:
            error_msg = f"未预期的错误: {str(e)}\n类型: {type(e)}\n详细信息: {e.__dict__}"
            logger.error(error_msg)
            return "🎯 Unexpected issue. I'll recalibrate and get back on track."


async def get_responses_async(experts, prompt):
    """异步获取所有专家的回应"""
    loop = asyncio.get_event_loop()

    # 记录开始时间
    start_time = time.time()

    # 创建任务列表，同时保存专家信息
    tasks_info = []
    for expert in experts:
        task = loop.run_in_executor(
            executor,
            expert.get_response,
            prompt
        )
        tasks_info.append((expert, task))

    # 使用 as_completed 处理完成的任务
    pending = [task for _, task in tasks_info]
    while pending:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED)

        for future in done:
            try:
                # 找到对应的专家
                expert = next(
                    exp for exp, task in tasks_info if task == future)
                response = await future
                yield expert, response
            except Exception as e:
                logger.error(f"处理专家响应时出错: {str(e)}")
                continue

    # 记录完成时间
    end_time = time.time()
    logger.info(f"所有专家回应完成，耗时: {end_time - start_time:.2f} 秒")


async def generate_summary(prompt, responses, experts):
    """生成总结"""
    summary_prompt = f"""作为 Investment Masters，你的任务是总结和整合各位投资大师的观点。

以下是各位大师对这个 thesis 的分析和建议：

{chr(10).join([f"{expert.name}：{response}" for expert, response in zip(experts, responses)])}

请你：
1. 总结各位大师发现的主要问题
2. 归纳他们提出需要多深入研究什麼
"""

    try:
        summary_response = client.chat.completions.create(
            model="grok-beta",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.7
        )
        return summary_response.choices[0].message.content
    except Exception as e:
        logger.error(f"生成总结时出错: {str(e)}")
        return "抱歉，无法生成总结。"

__all__ = ['ExpertAgent', 'get_responses_async', 'generate_summary']
