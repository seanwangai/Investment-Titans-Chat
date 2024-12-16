import random
import streamlit as st
from utils.expert import ExpertAgent, get_responses_async, generate_summary
from utils.document_loader import load_experts
import os
import asyncio
import logging

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
    /* 覆盖 Streamlit 默认的头像样式 */
    .st-emotion-cache-1v0mbdj > img,
    .st-emotion-cache-1v0mbdj > svg {
        width: 200px !important;
        height: 200px !important;
        border-radius: 100px !important;
        object-fit: cover !important;
        background-color: white !important;
        border: 3px solid rgba(0,0,0,0.1) !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
    }
    
    /* 调整对话消息中的头像大小 */
    .st-emotion-cache-p4micv {
        width: 10rem !important;
        height: 10rem !important;
    }
    
    /* 确保头像内的图片也跟随调整 */
    .st-emotion-cache-p4micv > img,
    .st-emotion-cache-p4micv > svg {
        width: 100% !important;
        height: 100% !important;
        object-fit: cover !important;
    }
    
    /* 适应深色主题 */
    .chat-message {
        padding: 20px !important;
        border-radius: 15px !important;
        margin: 10px 0 !important;
        color: #1A1A1A !important;  /* 深色文字 */
    }
    
    /* 放大专家名字 */
    .expert-name {
        font-size: 28px !important;
        font-weight: bold !important;
        margin-bottom: 10px !important;
        color: #1A1A1A !important;  /* 深色文字 */
    }
    
    /* 美化分隔线 */
    .divider {
        margin: 10px 0 !important;
        border: none !important;
        height: 2px !important;
        background: linear-gradient(to right, rgba(0,0,0,0.1), rgba(0,0,0,0.3), rgba(0,0,0,0.1)) !important;
    }
    
    /* Titans 特殊样式 */
    .masters-message {
        background: linear-gradient(135deg, #f6d365 0%, #fda085 100%) !important;
        border: 2px solid #f6d365 !important;
    }
    
    /* 专家画廊头像样式 */
    .expert-avatar {
        background-color: white !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
    }
    
    /* 确保深色主题下的文字可见性 */
    [data-theme="dark"] .chat-message,
    [data-theme="dark"] .expert-name {
        color: #1A1A1A !important;
    }
    
    /* 调整底部输入区域 */
    .stBottomBlockContainer {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* 调整输入框样式 */
    .stTextArea textarea {
        height: 100px !important;
        font-size: 1.1rem !important;
        padding: 1rem !important;
        border-radius: 15px !important;
    }
    
    /* 调整输入区域的提示文字 */
    .stTextArea label {
        font-size: 1.1rem !important;
        font-weight: 500 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 移除底部区域的额外空间 */
    .stBottomBlockContainer > div {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 思考中动画 */
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


def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "experts" not in st.session_state:
        st.session_state.experts = load_experts()
        # 为每个专家分配一个固定的背景颜色
        if "expert_colors" not in st.session_state:
            st.session_state.expert_colors = {
                expert.name: color
                for expert, color in zip(st.session_state.experts, EXPERT_COLORS)
            }


def display_chat_history():
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            expert_color = st.session_state.expert_colors.get(
                message["role"], "#F0F0F0")
            with st.chat_message(message["role"], avatar=message.get("avatar")):
                st.markdown(
                    f"""
                    <div style="background-color: {expert_color};" class="chat-message">
                        <div class="expert-name">{message["role"]}</div>
                        <div class="divider"></div>
                        {message["content"]}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def display_experts_gallery():
    """显示所有专家的画廊"""
    st.markdown("### 🎯 Titans")

    # 对专家进行排序：英文名字优先
    def sort_key(expert):
        # Warren Buffett 永远排在第一位
        if expert.name.lower() == "warren buffett":
            return (0, "")
        # 检查名字是否以英文字母开头
        return (1 if not expert.name[0].isascii() else 0, expert.name.lower())

    sorted_experts = sorted(st.session_state.experts, key=sort_key)

    # 使用列布局来展示专家
    cols = st.columns(4)  # 每行4个专家

    for idx, expert in enumerate(sorted_experts):
        with cols[idx % 4]:
            expert_color = st.session_state.expert_colors.get(
                expert.name, "#F0F0F0")
            st.markdown(
                f"""
                <div style="
                    background-color: {expert_color};
                    padding: 30px;
                    border-radius: 20px;
                    text-align: center;
                    margin: 15px 5px;
                    color: #1A1A1A;
                ">
                    <div style="
                        width: 150px;
                        height: 150px;
                        margin: 0 auto;
                        border-radius: 75px;
                        overflow: hidden;
                        background-color: white;
                        border: 3px solid rgba(0,0,0,0.1);
                        class="expert-avatar"
                    ">
                        <img src="{expert.avatar if expert.avatar.startswith('data:') else ''}" 
                             style="width: 100%; height: 100%; object-fit: cover;"
                             onerror="this.style.backgroundColor='white'; this.innerHTML='{expert.avatar}'">
                    </div>
                    <div style="
                        font-size: 24px;
                        font-weight: bold;
                        margin-top: 15px;
                    ">
                        {expert.name}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


def main():
    st.title("Investment Titans Chat")

    initialize_session_state()

    # 对专家进行排序：英文名字优先
    def sort_key(expert):
        # Warren Buffett 永远排在第一位
        if expert.name.lower() == "warren buffett":
            return (0, "")
        # 检查名字是否以英文字母开头
        return (1 if not expert.name[0].isascii() else 0, expert.name.lower())

    sorted_experts = sorted(st.session_state.experts, key=sort_key)

    # 添加总结专家到专家列表
    if "titans" not in st.session_state:
        st.session_state.titans = ExpertAgent(
            name="Investment Masters",
            knowledge_base="",  # 不需要知识库
            avatar="masters_logo.png"  # 使用logo作为头像
        )

    # 显示专家画廊
    display_experts_gallery()

    # 添加分隔线
    st.markdown("---")

    # 显示聊天历史
    display_chat_history()

    # 用户输入
    if user_input := st.chat_input("Share your thesis for analysis..."):
        # 构建完整的提示词
        prompt = f"""你看完我以下的thesis後，你會提出什麼問題，說出thesis裡不夠深入需要加強的？並以說出你過去的經驗，要怎樣才能投資，提出一個解決方案。以關鍵問題group： 

{user_input}"""

        try:
            # 添加用户消息
            st.session_state.messages.append({
                "role": "user",
                "content": user_input  # 保存原始输入，不包含提示词
            })

            # 显示用户消息
            with st.chat_message("user"):
                st.write(user_input)  # 显示原始输入，不包含提示词

            # 添加自动滚动 JavaScript
            st.markdown("""
                <script>
                    function scroll() {
                        var elements = window.parent.document.getElementsByClassName('stChatMessage');
                        if (elements.length > 0) {
                            var lastElement = elements[elements.length - 1];
                            lastElement.scrollIntoView({ behavior: 'smooth' });
                        }
                    }
                    setTimeout(scroll, 100);
                </script>
                """, unsafe_allow_html=True)

            # 创建占位符
            response_placeholders = {}
            for expert in st.session_state.experts:
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

            # 创建新的事件循环
            async def run_async():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    await process_responses()
                finally:
                    loop.close()

            async def process_responses():
                async for expert, response in get_responses_async(st.session_state.experts, prompt):
                    expert_color = st.session_state.expert_colors.get(
                        expert.name, "#F0F0F0")
                    # 更新对应专家的占位符
                    response_placeholders[expert.name].markdown(
                        f"""
                        <div style="background-color: {expert_color};" class="chat-message">
                            <div class="expert-name">{expert.name}</div>
                            <div class="divider"></div>
                            {response}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    # 每次更新后添加滚动
                    st.markdown("""
                        <script>
                            function scroll() {
                                var elements = window.parent.document.getElementsByClassName('stChatMessage');
                                if (elements.length > 0) {
                                    var lastElement = elements[elements.length - 1];
                                    lastElement.scrollIntoView({ behavior: 'smooth' });
                                }
                            }
                            setTimeout(scroll, 100);
                        </script>
                        """, unsafe_allow_html=True)

                    # 保存到会话状态
                    st.session_state.messages.append({
                        "role": expert.name,
                        "content": response,
                        "avatar": expert.avatar
                    })
                    responses.append(response)

                    # 如果有足够的回答，生成总结
                    if len(responses) >= 2:  # 至少有两个专家回答后就开始生成总结
                        try:
                            titans_response = await generate_summary(
                                prompt,
                                responses,
                                sorted_experts[:len(responses)]  # 使用已排序的专家列表
                            )
                            titans_placeholder.markdown(
                                f"""
                                <div style="background-color: #f6d365;" class="chat-message masters-message">
                                    <div class="expert-name">Investment Masters Summary</div>
                                    <div class="divider"></div>
                                    {titans_response}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            # 总结更新后也添加滚动
                            st.markdown("""
                                <script>
                                    function scroll() {
                                        var elements = window.parent.document.getElementsByClassName('stChatMessage');
                                        if (elements.length > 0) {
                                            var lastElement = elements[elements.length - 1];
                                            lastElement.scrollIntoView({ behavior: 'smooth' });
                                        }
                                    }
                                    setTimeout(scroll, 100);
                                </script>
                                """, unsafe_allow_html=True)
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


if __name__ == "__main__":
    main()
