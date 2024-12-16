import os
import PyPDF2
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from .expert import ExpertAgent
import logging
import base64

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_pdf(file_path):
    """读取 PDF 文件内容"""
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                text += page.extract_text() + '\n'
            return text
    except Exception as e:
        logger.error(f"读取 PDF 文件出错 {file_path}: {str(e)}")
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
        return read_pdf(file_path)
    elif file_extension == '.epub':
        return read_epub(file_path)
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
    """加载所有专家的知识库"""
    experts = []
    data_dir = "data"

    # 确保data目录存在
    if not os.path.exists(data_dir):
        logger.warning(f"数据目录 {data_dir} 不存在")
        return experts

    # 遍历专家文件夹
    for expert_folder in os.listdir(data_dir):
        expert_path = os.path.join(data_dir, expert_folder)
        if os.path.isdir(expert_path):
            logger.info(f"正在处理专家: {expert_folder}")

            # 加载头像
            avatar_path = os.path.join(expert_path, "head.png")
            avatar = load_image_as_base64(
                avatar_path) if os.path.exists(avatar_path) else "🤖"

            # 收集所有文档内容
            knowledge_base = []
            for file_name in os.listdir(expert_path):
                if file_name == "head.png":  # 跳过头像文件
                    continue
                file_path = os.path.join(expert_path, file_name)
                content = load_document(file_path)
                if content:
                    knowledge_base.append(content)

            if not knowledge_base:
                logger.warning(f"专家 {expert_folder} 没有可用的文档")
                continue

            # 合并所有文档内容
            full_knowledge = "\n\n".join(knowledge_base)

            # 创建专家代理
            expert = ExpertAgent(
                name=expert_folder,
                knowledge_base=full_knowledge,
                avatar=avatar
            )
            experts.append(expert)
            logger.info(f"专家 {expert_folder} 初始化完成")

    return experts
