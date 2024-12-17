import streamlit as st
from datetime import datetime, timedelta
import threading
import logging

# 设置日志
logger = logging.getLogger(__name__)

# 配额锁，用于并发控制
quota_lock = threading.Lock()

# 定义每个模型的配额设置
MODEL_QUOTAS = {
    "gemini-2.0-flash-exp": {
        "limit_per_min": 10,  # 每分钟限制
        "requests_per_conversation": 5  # 每次对话消耗的请求数（4个专家 + 1个总结）
    },
    "grok-beta": {
        "limit_per_min": 60,
        "requests_per_conversation": 5
    },
    "gemini-1.5-flash": {
        "limit_per_min": 10,
        "requests_per_conversation": 5
    }
}


def get_default_quota(model_name):
    """获取默认的配额结构"""
    model_config = MODEL_QUOTAS[model_name]
    return {
        "limit": model_config["limit_per_min"],  # 每分钟的请求限制
        "requests": []  # 存储请求时间戳列表
    }


def initialize_quota():
    """初始化配额信息"""
    if "quota_info" not in st.session_state:
        logger.info("初始化配额信息")
        st.session_state.quota_info = {
            model_name: get_default_quota(model_name)
            for model_name in MODEL_QUOTAS
        }

    # 确保所有模型都有正确的配额结构
    for model_name in MODEL_QUOTAS:
        if model_name not in st.session_state.quota_info:
            logger.info(f"为模型 {model_name} 添加配额信息")
            st.session_state.quota_info[model_name] = get_default_quota(
                model_name)

        # 确保所有必要的字段都存在
        quota = st.session_state.quota_info[model_name]
        if "requests" not in quota:
            logger.info(f"重置模型 {model_name} 的请求记录")
            quota["requests"] = []
        if "reset_time" not in quota:
            quota["reset_time"] = None


def clean_old_requests(requests, window_seconds=60):
    """清理旧的请求记录"""
    if not requests:  # 如果 requests 为 None 或空列表
        return []
    now = datetime.now()
    cutoff = now - timedelta(seconds=window_seconds)
    return [req for req in requests if req > cutoff]


def get_current_rpm(model_name):
    """获取当前每分钟请求数"""
    initialize_quota()
    quota = st.session_state.quota_info[model_name]

    with quota_lock:
        # 清理旧请求
        quota["requests"] = clean_old_requests(quota.get("requests", []))
        return len(quota["requests"])


def check_quota(model_name, required_quota=1):
    """检查是否有足够的配额"""
    initialize_quota()
    quota = st.session_state.quota_info[model_name]
    model_config = MODEL_QUOTAS[model_name]

    with quota_lock:
        now = datetime.now()

        # 清理旧请求并计算当前使用量
        old_requests = len(quota["requests"])
        quota["requests"] = clean_old_requests(quota.get("requests", []))
        new_requests = len(quota["requests"])

        if old_requests != new_requests:
            logger.info(f"检查配额时清理了 {old_requests - new_requests} 个过期请求")

        current_requests = len(quota["requests"])
        available_requests = model_config["limit_per_min"] - current_requests

        logger.info(
            f"配额检查 - 当前使用: {current_requests}, 需要: {required_quota}, 可用: {available_requests}")

        # 检查是否有足够的配额
        has_enough = available_requests >= required_quota
        if not has_enough:
            logger.warning(
                f"配额不足 - 需要 {required_quota} 个，但只剩 {available_requests} 个")

        return has_enough


def use_quota(model_name):
    """使用一个配额"""
    initialize_quota()
    quota = st.session_state.quota_info[model_name]
    model_config = MODEL_QUOTAS[model_name]

    with quota_lock:
        now = datetime.now()

        # 清理一分钟前的请求
        old_requests = len(quota["requests"])
        quota["requests"] = clean_old_requests(quota.get("requests", []))
        new_requests = len(quota["requests"])

        if old_requests != new_requests:
            logger.info(f"🧹 清理了 {old_requests - new_requests} 个过期请求")

        # 检查当前一分钟内的请求数
        current_requests = len(quota["requests"])
        logger.info(
            f"📊 当前一分钟内的请求数: {current_requests}/{model_config['limit_per_min']}")

        # 检查是否超过每分钟限制
        if current_requests >= model_config["limit_per_min"]:
            logger.warning(f"⚠️ 模型 {model_name} 达到每分钟请求限制!")
            return False

        # 添加新请求
        quota["requests"].append(now)
        logger.info(f"➕ 添加新请求，当前一分钟内总数: {len(quota['requests'])}")

        return True


def get_quota_display(model_name):
    """获取配额显示信息"""
    initialize_quota()
    quota = st.session_state.quota_info[model_name]
    model_config = MODEL_QUOTAS[model_name]

    with quota_lock:
        now = datetime.now()

        # 清理过期请求
        old_requests = len(quota["requests"])
        quota["requests"] = clean_old_requests(quota.get("requests", []))
        new_requests = len(quota["requests"])

        if old_requests != new_requests:
            logger.info(f"🧹 显示时清理了 {old_requests - new_requests} 个过期请求")

        # 计算当前一分钟内的使用情况
        current_requests = len(quota["requests"])
        remaining_requests = model_config["limit_per_min"] - current_requests

        # 计算可进行的对话次数（每次对话需要 requests_per_conversation 个请求）
        conversations = remaining_requests // model_config["requests_per_conversation"]
        total_conversations = model_config["limit_per_min"] // model_config["requests_per_conversation"]

        # 如果有请求记录，显示最早请求的重置时间
        if quota["requests"]:
            oldest_request = min(quota["requests"])
            reset_time = oldest_request + timedelta(minutes=1)
            time_left = max(0, int((reset_time - now).total_seconds()))
            time_text = f"{time_left}秒后重置一个配额"
        else:
            time_text = "每分钟重置"

        # 添加最早请求时间到返回值
        oldest_request_time = min(
            quota["requests"]) if quota["requests"] else None

        logger.info(f"""
🎯 配额状态更新:
   模型: {model_name}
   当前一分钟内使用: {current_requests}/{model_config['limit_per_min']}
   剩余请求数: {remaining_requests}
   可进行对话数: {conversations}/{total_conversations}
   重置信息: {time_text}
""")

        return {
            "remaining": conversations,
            "limit": total_conversations,
            "time_text": time_text,
            "progress": conversations / total_conversations if total_conversations > 0 else 0,
            "current_rpm": current_requests,
            "requests_per_conversation": model_config["requests_per_conversation"],
            "requests": quota["requests"],  # 添加请求列表
            "oldest_request_time": oldest_request_time  # 添加最早请求时间
        }
