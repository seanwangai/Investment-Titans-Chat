import random
import streamlit as st
from utils.expert import ExpertAgent, get_responses_async, generate_summary
from utils.quota import (
    check_quota,
    use_quota,
    get_quota_display,
    initialize_quota,
    MODEL_QUOTAS,
    calculate_conversation_quota
)
from utils.document_loader import load_experts
import os
import asyncio
import logging
from utils.dropbox_handler import download_and_extract_dropbox
from datetime import datetime, timedelta
import time

# 设置日志
logger = logging.getLogger(__name__)

# 为每个专家分配一个固定的背景颜色
EXPERT_COLORS = [
    "#FFE4E1",  # 浅粉红
    "#E0FFFF",  # 浅青色
    "#F0FFF0",  # 蜜瓜色
    "#FFF0F5",  # 淡紫色
    "#F5F5DC",  # 米色
    "#F0F8FF",  # 爱丽丝蓝
    "#F5FFFA",  # 薄荷色
    "#FAEBD7",  # 古董白
    "#FFE4B5",  # 莫卡辛色
    "#E6E6FA"   # 淡紫色
]

st.set_page_config(
    page_title="Investment Titans Chat",
    page_icon="💭",
    layout="wide"
)

# 自定义 CSS 样式
st.markdown("""
    <style>
    /* 聊天消息容器样式 */
    .stChatMessage {
        display: flex !important;
        align-items: flex-start !important;
        gap: 1rem !important;
        padding: 1rem !important;
        margin-bottom: 1rem !important;
    }
    
    /* 头像样式 */
    .stChatMessage > img,
    .stChatMessage > svg {
        width: 10rem !important;
        height: 10rem !important;
        border-radius: 5rem !important;
        object-fit: cover !important;
        flex-shrink: 0 !important;
    }
    
    /* 消息内容样式 */
    .stChatMessage > div:last-child {
        flex-grow: 1 !important;
        min-width: 0 !important;
        margin-left: 1rem !important;
    }
    
    /* 确保聊天容器可以滚动 */
    .stChatMessageContainer {
        overflow-y: auto !important;
        max-height: calc(100vh - 200px) !important;
        scroll-behavior: smooth !important;
    }
    
    /* 调整消息框样式 */
    .chat-message {
        padding: 20px !important;
        border-radius: 15px !important;
        margin: 0 !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    
    /* 专家名字样式 */
    .expert-name {
        font-size: 24px !important;
        font-weight: bold !important;
        margin-bottom: 10px !important;
    }
    
    /* 分隔线样式 */
    .divider {
        margin: 10px 0 !important;
        border: none !important;
        height: 2px !important;
        background: linear-gradient(to right, rgba(0,0,0,0.1), rgba(0,0,0,0.3), rgba(0,0,0,0.1)) !important;
    }
    
    /* 用户消息特殊样式 */
    .stChatMessage[data-testid="chat-message-user"] {
        justify-content: flex-end !important;
    }
    
    /* Streamlit 默认样式覆盖 */
    .st-emotion-cache-1v0mbdj > img,
    .st-emotion-cache-1v0mbdj > svg {
        width: 10rem !important;
        height: 10rem !important;
        border-radius: 5rem !important;
    }
    
    /* 输入框容器样式 */
    .stChatInputContainer {
        padding: 1rem !important;
        background: white !important;
        position: sticky !important;
        bottom: 0 !important;
        z-index: 100 !important;
    }
    
    /* 确保主容器正确显示 */
    .main.css-uf99v8.ea3mdgi5 {
        overflow-y: auto !important;
        scroll-behavior: smooth !important;
    }
    
    /* 思考动画样式保持不变 */
    .thinking-animation {
        font-style: italic;
        color: #666;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    
    .thinking-dots {
        display: inline-flex;
        gap: 2px;
    }
    
    .thinking-dots span {
        width: 4px;
        height: 4px;
        background-color: #666;
        border-radius: 50%;
        display: inline-block;
        animation: bounce 1.4s infinite ease-in-out;
    }
    
    .thinking-dots span:nth-child(1) { animation-delay: 0s; }
    .thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
    .thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
    
    @keyframes bounce {
        0%, 80%, 100% { 
            transform: translateY(0);
        }
        40% { 
            transform: translateY(-6px);
        }
    }
    </style>
    """, unsafe_allow_html=True)


def add_model_selector():
    """添加模型选择器"""
    models = {
        "Grok": "grok-beta",
        "Gemini": "gemini-1.5-flash"
    }

    # 在右上角添加模型选择器
    with st.sidebar:
        selected_model = st.selectbox(
            "选择模型",
            options=list(models.keys()),
            format_func=lambda x: x,
            key="model_selector"
        )
        st.session_state.current_model = models[selected_model]


def get_expert_color(expert_name, index):
    """根据专家名称和索引生成颜色"""
    # 预定义的柔和色彩列表
    colors = [
        "#FFE4E1",  # 浅玫瑰色
        "#E0FFFF",  # 浅青色
        "#F0FFF0",  # 蜜瓜色
        "#FFF0F5",  # 浅紫色
        "#F5F5DC",  # 米色
        "#F0F8FF",  # 爱丽丝蓝
        "#FAFAD2",  # 浅金菊黄
        "#E6E6FA",  # 淡紫色
        "#F5F5F5",  # 白烟色
        "#E8F4F8",  # 浅蓝灰色
    ]

    # 为 Investment Masters Summary 保留特定颜色
    if expert_name == "Investment Masters Summary":
        return "#f6d365"

    # 使用索引循环选择颜色
    return colors[index % len(colors)]


def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "experts" not in st.session_state:
        st.session_state.experts = load_experts()
    if "expert_colors" not in st.session_state:
        # 动态为每个专家分配颜色
        st.session_state.expert_colors = {
            expert.name: get_expert_color(expert.name, idx)
            for idx, expert in enumerate(st.session_state.experts)
        }
        # 添加总结专家的颜色
        st.session_state.expert_colors["Investment Masters Summary"] = "#f6d365"
    if "current_model" not in st.session_state:
        st.session_state.current_model = "gemini-2.0-flash-exp"  # 默认使用 Gemini 2.0
    if "quota_info" not in st.session_state:
        st.session_state.quota_info = {
            "gemini-2.0-flash-exp": {"limit": 10, "remaining": 10, "reset_time": None},
            "grok-beta": {"limit": 60, "remaining": 60, "reset_time": None},
            "gemini-1.5-flash": {"limit": 10, "remaining": 10, "reset_time": None}
        }
    # 添加总结专家到会话状态
    if "titans" not in st.session_state:
        st.session_state.titans = ExpertAgent(
            name="Investment Masters",
            knowledge_base="",  # 不需要知识库
            avatar="masters_logo.png"  # 使用logo作为头像
        )


def display_chat_history():
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            expert_color = st.session_state.expert_colors.get(
                message["role"], "#F0F0F0")
            with st.chat_message(message["role"], avatar=message.get("avatar")):
                # 清理消息内容中的HTML标签
                content = message["content"]
                content = content.replace('</div>', '')
                content = content.replace('<div>', '')
                content = content.replace('<code>', '')
                content = content.replace('</code>', '')
                content = content.replace('<span>', '')
                content = content.replace('</span>', '')

                st.markdown(
                    f"""<div style="background-color: {expert_color};" class="chat-message">
                        <div class="expert-name">{message["role"]}</div>
                        <div class="divider"></div>
                        {content}
                    </div>""".strip(),
                    unsafe_allow_html=True
                )


def display_experts_gallery():
    """显示所有专家的画廊"""
    st.markdown("""
        <style>
        .expert-avatar img {
            background: transparent !important;
        }
        .expert-card {
            transition: transform 0.2s;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .expert-card:hover {
            transform: scale(1.05);
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("### 🎯 Titans")

    # 对专家进行排序
    def sort_key(expert):
        if expert.name.lower() == "warren buffett":
            return (0, "")
        return (1 if not expert.name[0].isascii() else 0, expert.name.lower())

    sorted_experts = sorted(st.session_state.experts, key=sort_key)
    total_experts = len(sorted_experts)

    # 计算布局
    max_per_row = 6
    num_rows = (total_experts + max_per_row - 1) // max_per_row  # 向上取整

    # 为每行创建列
    for row in range(num_rows):
        # 计算当前行的专家数量
        start_idx = row * max_per_row
        end_idx = min(start_idx + max_per_row, total_experts)
        experts_in_row = sorted_experts[start_idx:end_idx]
        num_experts_in_row = len(experts_in_row)

        # 创建列
        cols = st.columns(num_experts_in_row)

        # 在每列中显示专家
        for col, expert in zip(cols, experts_in_row):
            with col:
                expert_color = st.session_state.expert_colors.get(
                    expert.name, "#F0F0F0")
                st.markdown(
                    f"""
                    <div class="expert-card" style="
                        background-color: {expert_color};
                        padding: 20px;
                        border-radius: 20px;
                        text-align: center;
                        margin: 10px 5px;
                        color: #1A1A1A;
                        height: 100%;
                    ">
                        <div style="
                            width: 100%;
                            padding-bottom: 100%;
                            position: relative;
                            margin-bottom: 15px;
                        ">
                            <div class="expert-avatar" style="
                                position: absolute;
                                top: 0;
                                left: 0;
                                right: 0;
                                bottom: 0;
                                overflow: hidden;
                                background-color: transparent;
                            ">
                                <img src="{expert.avatar if expert.avatar.startswith('data:') else ''}" 
                                     style="width: 100%; height: 100%; object-fit: contain; background: transparent;"
                                     onerror="this.style.backgroundColor='transparent';">
                            </div>
                        </div>
                        <div style="
                            font-size: 1.2vw;
                            font-weight: bold;
                            margin-top: 10px;
                            word-wrap: break-word;
                        ">
                            {expert.name}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def add_auto_scroll():
    """添加自动滚动 JavaScript"""
    st.markdown("""
        <script>
            function scrollToBottom() {
                // 立即滚动整个页面
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
                
                // 滚动所有可能的容器
                const containers = [
                    '.stChatMessageContainer',
                    '.main.css-uf99v8.ea3mdgi5',
                    '.st-emotion-cache-1v0mbdj',
                    '.element-container'
                ];
                
                containers.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(element => {
                        element.scrollTop = element.scrollHeight;
                    });
                });
            }

            // 立即执行
            scrollToBottom();
            
            // 延迟执行几次以确保内容加载
            [100, 300, 500, 1000].forEach(delay => {
                setTimeout(scrollToBottom, delay);
            });

            // 创建观察器
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.addedNodes.length || mutation.type === 'childList') {
                        scrollToBottom();
                    }
                });
            });

            // 观察整个文档的变化
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true
            });
        </script>
    """, unsafe_allow_html=True)


def display_quota_info():
    """显示API配额信息"""
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.title("Investment Titans Chat")

    with col2:
        # 添加模型选择器
        models = {
            "Gemini 2.0": {"name": "gemini-2.0-flash-exp", "limit": 10},
            "Grok": {"name": "grok-beta", "limit": 60},
            "Gemini 1.5": {"name": "gemini-1.5-flash", "limit": 15}
        }
        selected_model = st.selectbox(
            "选择模型",
            options=list(models.keys()),
            format_func=lambda x: x,
            key="model_selector",
            index=0
        )
        model_info = models[selected_model]
        st.session_state.current_model = model_info["name"]

    with col3:
        # 使用 st.empty() 创建一个容器
        quota_container = st.empty()

        # 获取配额信息
        quota_info = get_quota_display(st.session_state.current_model)

        # 添加自动刷新脚本
        st.markdown("""
            <script>
                function updateQuotaDisplay() {
                    const now = new Date();
                    const quotaElements = document.querySelectorAll('.quota-time');
                    quotaElements.forEach(element => {
                        const resetTime = new Date(element.getAttribute('data-reset-time'));
                        const timeLeft = Math.max(0, Math.floor((resetTime - now) / 1000));
                        if (timeLeft > 0) {
                            element.textContent = `${timeLeft}秒后重置一个配额`;
                        } else {
                            element.textContent = '每分钟重置';
                        }
                    });
                }
                
                // 每秒更新一次
                setInterval(updateQuotaDisplay, 1000);
                
                // 每5秒重新加载页面以获取最新配额
                setInterval(() => {
                    window.parent.document.querySelector('iframe').contentWindow.location.reload();
                }, 5000);
            </script>
        """, unsafe_allow_html=True)

        # 显示配额信息
        if quota_info["requests"] and quota_info["oldest_request_time"]:
            reset_time = quota_info["oldest_request_time"] + \
                timedelta(minutes=1)
            time_left = max(
                0, int((reset_time - datetime.now()).total_seconds()))
            time_display = f"""<span class="quota-time" data-reset-time="{reset_time.isoformat()}">{time_left}秒后重置一个配额</span>"""
        else:
            time_display = """<span class="quota-time">每60秒重置</span>"""

        quota_container.markdown(
            f"""<div style="text-align: right; font-size: 0.8em;">
                每分鐘问题数: {quota_info['remaining']}/{quota_info['limit']}<br>
                {time_display}
            </div>""",
            unsafe_allow_html=True
        )


def main():
    # 先初始化会话状态
    initialize_session_state()

    # 再显示配额信息
    display_quota_info()

    # 显示专家画廊
    display_experts_gallery()
    st.markdown("---")
    display_chat_history()

    # 用户输入
    if user_input := st.chat_input("Share your thesis for analysis..."):
        # 添加用户消息到历史记录并显示
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        # 显示用户消息
        with st.chat_message("user"):
            st.write(user_input)
            add_auto_scroll()

        current_model = st.session_state.current_model
        total_experts = len(st.session_state.experts)
        required_quota = calculate_conversation_quota(total_experts)

        logger.info(f"当前专家数量: {total_experts}, 需要配额: {required_quota}")

        # 检查配额并显示警告（但不阻止请求）
        if not check_quota(current_model, required_quota):
            quota_info = get_quota_display(current_model)

            # 获取下一个配额重置的时间
            if quota_info["oldest_request_time"]:
                reset_time = quota_info["oldest_request_time"] + \
                    timedelta(minutes=1)
                time_left = max(
                    0, int((reset_time - datetime.now()).total_seconds()))
                warning_message = f"""⚠️ 已超出每分钟问答限制
- 等待 {time_left} 秒后将重置一个配额
- 或切换到其他模型继续对话
- 需要 {required_quota} 个配额，当前剩余 {quota_info['remaining']} 个"""
            else:
                warning_message = f"""⚠️ 已超出每分钟问答限制
- 请等待配额重置后再试
- 或切换到其他模型继续对话
- 需要 {required_quota} 个配额，当前剩余 {quota_info['remaining']} 个"""

            st.warning(warning_message)
            add_auto_scroll()

            # 显示其他可用模型的建议
            available_models = []
            for model_name in MODEL_QUOTAS:
                if model_name != current_model and check_quota(model_name, required_quota):
                    model_info = get_quota_display(model_name)
                    available_models.append(
                        f"- {model_name}: 剩余 {model_info['remaining']} 次对话")

            if available_models:
                st.info("💡 以下模型当前可用：\n" + "\n".join(available_models))
                add_auto_scroll()

        # 记录配额使用（不管是否超限）
        for _ in range(required_quota):
            use_quota(current_model)

        logger.info(f"记录配额使用：{required_quota} 个（专家: {total_experts}, 总结: 1）")

        # 对专家进行排序
        def sort_key(expert):
            if expert.name.lower() == "warren buffett":
                return (0, "")
            return (1 if not expert.name[0].isascii() else 0, expert.name.lower())

        sorted_experts = sorted(st.session_state.experts, key=sort_key)

        # 构建完整的提示词
        prompt = f"""你看完我以下的thesis後，你會提出什麼問題，說出thesis裡不夠深入需要加強的？並以說出你過去的經驗，要怎樣才能投資，提出一個解決方案。以關鍵問題group：  （如果沒有輸入thesis就根據先前閱讀的資料純聊天就好）

{user_input}"""

        try:
            # 创建占位符
            response_placeholders = {}
            for expert in sorted_experts:  # 使用排序后的专家列表
                expert_color = st.session_state.expert_colors.get(
                    expert.name, "#F0F0F0")
                with st.chat_message(expert.name, avatar=expert.avatar):
                    # 为每个专家创建一个占位符
                    response_placeholders[expert.name] = st.empty()
                    # 显示加载消息
                    response_placeholders[expert.name].markdown(
                        f"""
                        <div style="background-color: {expert_color};" class="chat-message">
                            <div class="expert-name">{expert.name}</div>
                            <div class="divider"></div>
                            <div class="thinking-animation">
                                Thinking
                                <div class="thinking-dots">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            # 创建总结专家的占位符
            with st.chat_message("Investment Masters", avatar=st.session_state.titans.avatar):
                titans_placeholder = st.empty()
                titans_placeholder.markdown(
                    f"""
                    <div style="background-color: #f6d365;" class="chat-message masters-message">
                        <div class="expert-name">Investment Masters Summary</div>
                        <div class="divider"></div>
                        <div class="thinking-animation">
                            Waiting for experts
                            <div class="thinking-dots">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # 异步获取和显示回答
            responses = []
            final_sorted_experts = sorted_experts  # 保存排序后的专家列表供异步函数使用

            # 创建新的事件循环
            async def run_async():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    await process_responses(final_sorted_experts)  # 传入排序后的专家列表
                finally:
                    loop.close()

            async def process_responses(sorted_experts):  # 接收排序后的专家列表作为参数
                responses = []
                experts_responded = set()

                # 使用排序后的专家列表
                async for expert, response in get_responses_async(sorted_experts, prompt):
                    expert_color = st.session_state.expert_colors.get(
                        expert.name, "#F0F0F0")
                    # 更新对应专家的占位符
                    response_placeholders[expert.name].markdown(
                        f"""<div style="background-color: {expert_color};" class="chat-message">
                            <div class="expert-name">{expert.name}</div>
                            <div class="divider"></div>
                            {response.replace('</div>', '').replace('<div>', '')}
                        </div>""".strip(),
                        unsafe_allow_html=True
                    )
                    add_auto_scroll()

                    # 保存到会话状态
                    st.session_state.messages.append({
                        "role": expert.name,
                        "content": response,
                        "avatar": expert.avatar
                    })
                    responses.append(response)
                    experts_responded.add(expert.name)

                    # 只有在所有专家都回答完后才生成总结
                    if len(experts_responded) == len(sorted_experts):
                        try:
                            titans_response = await generate_summary(
                                prompt,
                                responses,
                                sorted_experts  # 使用所有专家
                            )
                            titans_placeholder.markdown(
                                f"""<div style="background-color: #f6d365;" class="chat-message masters-message">
                                    <div class="expert-name">Investment Masters Summary</div>
                                    <div class="divider"></div>
                                    {titans_response.replace('</div>', '').replace('<div>', '')}
                                </div>""".strip(),
                                unsafe_allow_html=True
                            )
                            add_auto_scroll()
                        except Exception as e:
                            logger.error(f"生成总结时出错: {str(e)}")
                            titans_placeholder.markdown(
                                f"""
                                <div style="background-color: #f6d365;" class="chat-message masters-message">
                                    <div class="expert-name">Investment Masters Summary</div>
                                    <div class="divider"></div>
                                    <i>抱歉，生成总结时出现错误，请稍后再试。</i>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

            try:
                asyncio.run(run_async())
            except Exception as e:
                st.error(f"处理请求时发生错误: {str(e)}")
                logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)

        except Exception as e:
            st.error(f"处理请求时发生错误: {str(e)}")
            logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)


# 在应用启动时下载并解压文件
@st.cache_resource
def initialize_data():
    dropbox_url = st.secrets["DROPBOX_DATA_URL"]
    success = download_and_extract_dropbox(dropbox_url)
    if not success:
        st.error("无法从Dropbox下载数据")
    return success


# 在应用的主要部分调用这个函数
if initialize_data():
    # 继续应用的其他逻辑
    pass


if __name__ == "__main__":
    main()
