import asyncio
import logging
import requests
from datetime import datetime, timedelta
import streamlit as st

# 设置日志
logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, requests_per_minute=10):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    def can_make_request(self):
        now = datetime.now()
        self.requests = [req_time for req_time in self.requests
                         if now - req_time < timedelta(minutes=1)]

        if len(self.requests) < self.requests_per_minute:
            self.requests.append(now)
            return True
        return False


# 创建速率限制器实例
rate_limiter = RateLimiter(requests_per_minute=10)


async def generate_gemini_response(prompt, model_name, max_tokens=1000):
    """使用 Gemini API 直接生成回复"""
    try:
        if not rate_limiter.can_make_request():
            raise Exception("已达到每分钟请求限制，请稍后再试")

        # 构建 API 请求
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": st.secrets["GOOGLE_API_KEY"]
        }
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max_tokens
            }
        }

        # 添加重试机制
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()

                if 'candidates' in result:
                    text = result['candidates'][0]['content']['parts'][0]['text']
                    return text
                else:
                    raise Exception("响应格式不正确")

            except Exception as e:
                if attempt == 2:  # 最后一次尝试
                    raise e
                await asyncio.sleep(1)  # 等待1秒后重试
                continue

    except Exception as e:
        logger.error(f"Gemini API 调用失败: {str(e)}")
        if "503" in str(e):
            raise Exception("Gemini 服务暂时不可用，请稍后再试或切换到其他模型")
        raise e
