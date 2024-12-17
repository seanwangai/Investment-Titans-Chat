import os
import PyPDF2
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from .expert import ExpertAgent
import logging
import base64
import requests
from io import BytesIO
import streamlit as st

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 检查是否在 Streamlit Cloud 环境运行
IS_CLOUD = st.secrets.get("DEPLOY_ENV") == "cloud"


def download_file(url):
    """从 Dropbox 下载文件"""
    try:
        # 构建正确的 Dropbox 下载链接
        base_url = url.split('?')[0]  # 移除所有参数
        if '/file/' not in base_url:
            base_url = base_url.replace('/scl/fo/', '/scl/fo/file/')
        direct_url = f"{base_url}?dl=1"
        logger.info(f"尝试下载: {direct_url}")
        response = requests.get(direct_url)
        response.raise_for_status()
        return BytesIO(response.content)
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        return None


def get_expert_folders():
    """获取专家文件夹列表"""
    try:
        return ["Warren Buffett", "Charlie Munger", "Ray Dalio"]  # 硬编码专家列表
    except Exception as e:
        logger.error(f"获取专家列表失败: {str(e)}")
        return None


def read_pdf(file_path):
    """读取 PDF 文件内容"""
    try:
        if IS_CLOUD:
            # file_path 已经是 BytesIO 对象
            if not file_path:
                return ''
            reader = PyPDF2.PdfReader(file_path)
        else:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)

        text = ''
        for page in reader.pages:
            text += page.extract_text() + '\n'
        return text
    except Exception as e:
        logger.error(f"读取 PDF 文件出错: {str(e)}")
        return ''


def read_epub(file_path):
    """读取 EPUB 文件内容"""
    try:
        book = epub.read_epub(file_path)
        text = ''
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text += soup.get_text() + '\n'
        return text
    except Exception as e:
        logger.error(f"读取 EPUB 文件出错 {file_path}: {str(e)}")
        return ''


def load_document(file_path):
    """加载单个文档"""
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == '.pdf':
        with open(file_path, 'rb') as f:
            return read_pdf(BytesIO(f.read()))
    elif file_extension == '.epub':
        with open(file_path, 'rb') as f:
            return read_epub(BytesIO(f.read()))
    else:
        logger.warning(f"不支持的文件格式: {file_path}")
        return ''


def load_image_as_base64(image_path):
    """加载图片并转换为 base64"""
    try:
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()
            return f"data:image/png;base64,{encoded}"
    except Exception as e:
        logger.error(f"加载头像图片失败 {image_path}: {str(e)}")
        return None


def load_experts():
    """
    从data目录加载专家数据
    """
    experts = []
    try:
        # 从data目录读取所有专家文件夹
        data_dir = "./data"
        if os.path.exists(data_dir):
            expert_folders = [f for f in os.listdir(
                data_dir) if os.path.isdir(os.path.join(data_dir, f))]

            for folder in expert_folders:
                expert_path = os.path.join(data_dir, folder)
                # 尝试加载头像
                avatar_path = os.path.join(expert_path, "head.png")
                if os.path.exists(avatar_path):
                    avatar = load_image_as_base64(avatar_path)
                else:
                    avatar = f"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>"

                # 读取专家信息
                try:
                    expert = ExpertAgent(
                        name=folder,
                        knowledge_base=expert_path,
                        avatar=avatar
                    )
                    experts.append(expert)
                except Exception as e:
                    logger.error(f"加载专家 {folder} 时出错: {str(e)}")
                    continue
    except Exception as e:
        logger.error(f"加载专家数据时出错: {str(e)}")

    return experts


def get_file_type(file_path):
    """获取文件类型"""
    # 使用文件扩展名来判断类型
    extension = os.path.splitext(file_path)[1].lower()
    if extension in ['.txt', '.md']:
        return 'text'
    elif extension in ['.pdf']:
        return 'pdf'
    elif extension in ['.doc', '.docx']:
        return 'word'
    else:
        return 'unknown'
