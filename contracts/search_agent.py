# 负责人：张凯诚（Agent 搜索 / 文献爬取）
# 描述：调用 arXiv API 搜索论文，并自动下载 PDF 到本地
# -*- coding: utf-8 -*-

import os
import re
import time
import ssl
import certifi
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil

# 工具函数：安全提取 XML 文本，防止 None 报错
def _text(element, default=""):
    return element.text.strip() if (element is not None and element.text) else default


def search_papers(query: str, max_results: int = 5) -> list[dict]:
    """
    根据关键词调用 arXiv API 搜索学术论文，并将 PDF 下载到本地。
    """
    if not query.strip():
        raise ValueError("query 不能为空")

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    project_root = Path(__file__).resolve().parent.parent
    download_dir = project_root / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    terms = query.strip().split()
    search_query = "+AND+".join(f"all:{urllib.parse.quote(t)}" for t in terms)

    url = f"https://export.arxiv.org/api/query?search_query={search_query}&start=0&max_results={max_results}"
    headers = {"User-Agent": "AI_Paper_Reader/1.0"}

    print(f"[2号位日志] 正在搜索 arXiv: {query}")

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
            xml_data = response.read()
    except Exception as e:
        raise RuntimeError(f"arXiv API 请求失败: {e}") from e

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        raise RuntimeError("解析 arXiv 返回的数据失败，接口可能发生了变动。") from e

    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    papers_list = []
    entries = root.findall('atom:entry', ns)

    if not entries:
        print("[2号位日志] 未搜索到相关论文。")
        return papers_list

    for i, entry in enumerate(entries):
        title = _text(entry.find('atom:title', ns)).replace('\n', ' ')
        authors = [_text(author.find('atom:name', ns)) for author in entry.findall('atom:author', ns)]
        published = _text(entry.find('atom:published', ns))
        try:
            year = int(published[:4]) if published else 0
        except ValueError:
            year = 0
        abstract = _text(entry.find('atom:summary', ns)).replace('\n', ' ')

        id_url = _text(entry.find('atom:id', ns))
        arxiv_id = id_url.split('/')[-1] if id_url else f"unknown_id_{i}"

        pdf_url = ""
        for link in entry.findall('atom:link', ns):
            if link.attrib.get('title') == 'pdf' or link.attrib.get('type') == 'application/pdf':
                pdf_url = link.attrib.get('href')
                break

        # 不要盲目拼接 .pdf
        if pdf_url and pdf_url.startswith('http://'):
            pdf_url = pdf_url.replace('http://', 'https://')

        local_path_str = ""
        download_performed = False

        if pdf_url:
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:40]
            file_name = f"{arxiv_id}_{safe_title}.pdf"
            local_path = download_dir / file_name
            local_path_str = str(local_path)

            if local_path.exists() and local_path.stat().st_size > 1024:
                print(f"[2号位日志] 论文已存在，跳过下载: {file_name}")
            else:
                print(f"[2号位日志] 正在下载 PDF: {file_name} ...")
                download_performed = True
                try:
                    pdf_req = urllib.request.Request(pdf_url, headers=headers)
                    with urllib.request.urlopen(pdf_req, timeout=30, context=ssl_context) as r, open(local_path, 'wb') as f:
                        shutil.copyfileobj(r, f)

                    with open(local_path, 'rb') as f:
                        if f.read(4) != b'%PDF':
                            raise ValueError("下载的文件非有效 PDF 格式")

                except Exception as e:
                    print(f"[2号位日志] ⚠️ 单篇下载失败: {title[:60]} | 错误: {e}")
                    local_path_str = ""
                    if local_path.exists():
                        local_path.unlink()

        paper_dict = {
            "title": title,
            "authors": authors,
            "year": year,
            "abstract": abstract,
            "pdf_url": pdf_url,
            "local_path": local_path_str,
            "source": "arxiv"
        }
        papers_list.append(paper_dict)

        # 仅当实际下载 PDF 时再 sleep
        if download_performed:
            time.sleep(1)

    return papers_list


# ============================================================
# 测试模块
# ============================================================
if __name__ == "__main__":
    print("=== 开始测试 2号位 (v2.1) ===")
    t0 = time.time()
    try:
        results = search_papers("graph neural network", max_results=2)
        elapsed = time.time() - t0

        for i, res in enumerate(results):
            print(f"\n--- 第 {i+1} 篇 ---")
            print(f"标题: {res['title']}")
            print(f"PDF 本地路径: {res['local_path']}")

            assert os.path.isabs(res['local_path']) or res['local_path'] == "", "路径必须是绝对路径！"

            if res['local_path']:
                if os.path.exists(res['local_path']):
                    print("✅ 状态: PDF 文件存在，且路径为绝对路径！")
                else:
                    print("❌ 状态: PDF 路径有值，但文件不存在！")

        print(f"\n✅ 全部测试通过 (总耗时 {elapsed:.1f}s)")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
