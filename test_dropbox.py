import requests
import logging
from bs4 import BeautifulSoup
import json
import os
from zipfile import ZipFile
from io import BytesIO
import streamlit as st

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从 .streamlit/secrets.toml 获取 Dropbox 配置
DROPBOX_DATA_URL = st.secrets["DROPBOX_DATA_URL"]
DROPBOX_ACCESS_TOKEN = st.secrets["DROPBOX_ACCESS_TOKEN"]

# 下载和解压目录
DOWNLOAD_DIR = "downloaded_data"
EXTRACT_DIR = "data"


def download_and_extract():
    """下载并解压 Dropbox 文件夹"""
    try:
        # 创建下载目录
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(EXTRACT_DIR, exist_ok=True)

        # 下载文件
        logger.info("开始下载文件...")
        download_url = DROPBOX_DATA_URL.replace('dl=0', 'dl=1')
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        # 检查是否是 ZIP 文件
        content_type = response.headers.get('Content-Type', '')
        if 'zip' in content_type.lower():
            logger.info("检测到 ZIP 文件，准备解压...")
            # 直接从内存解压
            with ZipFile(BytesIO(response.content)) as zip_ref:
                # 列出所有文件
                logger.info("ZIP 文件内容:")
                for file in zip_ref.namelist():
                    logger.info(f"- {file}")

                # 解压所有文件
                zip_ref.extractall(EXTRACT_DIR)
                logger.info(f"文件已解压到: {EXTRACT_DIR}")
        else:
            # 如果不是 ZIP 文件，保存为普通文件
            logger.info("下载的不是 ZIP 文件，尝试直接保存...")
            save_path = os.path.join(DOWNLOAD_DIR, "downloaded_folder.bin")
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info(f"文件已保存到: {save_path}")

            # 打印文件信息
            logger.info(f"文件类型: {content_type}")
            logger.info(f"文件大小: {os.path.getsize(save_path)} bytes")

        # 列出下载的文件
        logger.info("\n下载目录内容:")
        for root, dirs, files in os.walk(EXTRACT_DIR):
            level = root.replace(EXTRACT_DIR, '').count(os.sep)
            indent = ' ' * 4 * level
            logger.info(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                logger.info(f"{subindent}{f}")

    except Exception as e:
        logger.error(f"下载或解压失败: {str(e)}")


def explore_dropbox_folder():
    """探索 Dropbox 文件夹内容"""
    try:
        # 1. 尝试直接访问文件夹页面
        logger.info("尝试方法 1: 直接访问文件夹页面")
        response = requests.get(DROPBOX_DATA_URL)
        response.raise_for_status()

        # 使用 BeautifulSoup 解析页面
        soup = BeautifulSoup(response.text, 'html.parser')

        # 查找文件列表
        file_list = soup.find_all('div', {'class': 'dig-List-item'})
        for item in file_list:
            logger.info(f"找到项目: {item.text}")

        # 2. 尝试使用 Dropbox API
        logger.info("\n尝试方法 2: 使用 Dropbox API")
        headers = {
            'Authorization': f'Bearer {DROPBOX_ACCESS_TOKEN}',
            'Content-Type': 'application/json',
        }

        # 尝试不同的 API 端点
        api_endpoints = [
            'https://api.dropboxapi.com/2/sharing/get_shared_link_metadata',
            'https://api.dropboxapi.com/2/files/list_folder_from_link',
            'https://api.dropboxapi.com/2/sharing/list_folder'
        ]

        for endpoint in api_endpoints:
            logger.info(f"\n尝试 API 端点: {endpoint}")
            try:
                data = {
                    'url': DROPBOX_DATA_URL
                }
                response = requests.post(endpoint, headers=headers, json=data)
                logger.info(f"状态码: {response.status_code}")
                logger.info(f"响应内容: {response.text}")
            except Exception as e:
                logger.error(f"API 调用失败: {str(e)}")

    except Exception as e:
        logger.error(f"探索失败: {str(e)}")


if __name__ == "__main__":
    # 先探索文件夹内容
    explore_dropbox_folder()

    # 然后下载并解压
    logger.info("\n开始下载和解压...")
    download_and_extract()
