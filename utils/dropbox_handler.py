import os
import requests
import zipfile
from pathlib import Path


def download_and_extract_dropbox(url, extract_path="./data"):
    """
    从Dropbox下载ZIP文件并解压到指定目录

    Args:
        url (str): Dropbox分享链接
        extract_path (str): 解压目标路径
    """
    # 确保URL是直接下载链接
    if "dl=0" in url:
        url = url.replace("dl=0", "dl=1")
    elif "?dl=0" not in url and "?dl=1" not in url:
        url += "?dl=1"

    try:
        # 创建目标目录
        Path(extract_path).mkdir(parents=True, exist_ok=True)

        # 下载ZIP文件
        temp_zip = "temp_download.zip"
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(temp_zip, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # 解压文件
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 删除临时ZIP文件
        os.remove(temp_zip)

        return True

    except Exception as e:
        print(f"下载或解压过程中发生错误: {str(e)}")
        return False
