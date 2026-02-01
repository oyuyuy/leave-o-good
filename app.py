"""
试试我试试好 - 视频下载工具 Web 后端
"""

import os
import re
import uuid
import shutil
import requests
import threading
import time
import urllib.parse
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

# 配置
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'downloads')
ZIP_FOLDER = os.path.join(os.path.dirname(__file__), 'zips')
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

# 确保目录存在
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(ZIP_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# 文件清理时间（秒）
CLEANUP_INTERVAL = 300  # 5分钟后清理


def cleanup_old_files():
    """清理过期的下载文件和ZIP包"""
    while True:
        time.sleep(60)  # 每分钟检查一次
        now = time.time()

        # 清理downloads目录
        if os.path.exists(DOWNLOAD_FOLDER):
            for folder in os.listdir(DOWNLOAD_FOLDER):
                folder_path = os.path.join(DOWNLOAD_FOLDER, folder)
                if os.path.isdir(folder_path):
                    if now - os.path.getmtime(folder_path) > CLEANUP_INTERVAL:
                        shutil.rmtree(folder_path, ignore_errors=True)

        # 清理zips目录
        if os.path.exists(ZIP_FOLDER):
            for f in os.listdir(ZIP_FOLDER):
                file_path = os.path.join(ZIP_FOLDER, f)
                if os.path.isfile(file_path):
                    if now - os.path.getmtime(file_path) > CLEANUP_INTERVAL:
                        os.remove(file_path)


# 启动清理线程
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()


@app.route('/')
def index():
    """返回主页"""
    return send_from_directory('.', 'index.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    """提供静态文件"""
    return send_from_directory(STATIC_FOLDER, filename)


@app.route('/api/parse', methods=['POST'])
def parse_content():
    """
    解析用户粘贴的HTML内容，提取视频URL
    针对oiioii平台优化
    """
    try:
        data = request.get_json()
        content = data.get('content', '')

        if not content:
            return jsonify({'code': 400, 'msg': '内容为空', 'data': None})

        video_urls = []

        # ===== 优先匹配 oiioii 平台的 hogi://video/ 视频URI =====
        # 匹配URL编码格式: hogi%3A%2F%2Fvideo%2Fxxx.mp4
        hogi_encoded_pattern = r'hogi%3A%2F%2Fvideo%2F([a-zA-Z0-9_]+\.mp4)'
        for video_id in re.findall(hogi_encoded_pattern, content, re.IGNORECASE):
            url = f'https://api.oiioii.ai/res/read_file?uri=hogi%3A%2F%2Fvideo%2F{video_id}'
            if url not in video_urls:
                video_urls.append(url)

        # 匹配未编码格式: hogi://video/xxx.mp4
        hogi_raw_pattern = r'hogi://video/([a-zA-Z0-9_]+\.mp4)'
        for video_id in re.findall(hogi_raw_pattern, content, re.IGNORECASE):
            url = f'https://api.oiioii.ai/res/read_file?uri=hogi%3A%2F%2Fvideo%2F{video_id}'
            if url not in video_urls:
                video_urls.append(url)

        # ===== 兜底：匹配通用 mp4 直链 =====
        if not video_urls:
            exclude_keywords = [
                'thumb', 'thumbnail', 'preview', 'poster', 'cover',
                'icon', 'logo', 'avatar', 'img', 'image', 'photo',
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
                'watermark', 'sprite', 'loading', 'placeholder',
                'first_frame'
            ]

            patterns = [
                r'["\']([^"\']*?\.mp4(?:\?[^"\']*)?)["\']',
                r'src\s*=\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                r'data-src\s*=\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for url in matches:
                    url = url.strip()
                    if url.startswith('//'):
                        url = 'https:' + url
                    if not url.startswith('http'):
                        continue

                    url_lower = url.lower()
                    is_excluded = False
                    for kw in exclude_keywords:
                        if kw in url_lower:
                            is_excluded = True
                            break
                    if is_excluded:
                        continue
                    if len(url) < 30:
                        continue
                    if url not in video_urls:
                        video_urls.append(url)

        # 去重并保持顺序
        seen = set()
        unique_urls = []
        for url in video_urls:
            # 用视频文件名去重（提取hogi视频ID或URL路径）
            parsed = urllib.parse.urlparse(url)
            uri_param = urllib.parse.parse_qs(parsed.query).get('uri', [''])[0]
            dedup_key = uri_param if uri_param else url.split('?')[0]
            if dedup_key not in seen:
                seen.add(dedup_key)
                unique_urls.append(url)

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': {
                'video_urls': unique_urls,
                'count': len(unique_urls)
            }
        })

    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e), 'data': None})


@app.route('/api/download', methods=['POST'])
def download_videos():
    """
    下载选中的视频并打包为ZIP
    """
    try:
        data = request.get_json()
        selected_links = data.get('selected_links', [])
        custom_names = data.get('custom_names', {})

        if not selected_links:
            return jsonify({'code': 400, 'msg': '未选择视频', 'data': None})

        logs = []
        task_id = str(uuid.uuid4())[:8]
        task_folder = os.path.join(DOWNLOAD_FOLDER, task_id)
        os.makedirs(task_folder, exist_ok=True)

        logs.append(f"📦 创建下载任务: {task_id}")

        # 下载每个视频
        downloaded_files = []
        for idx, url in enumerate(selected_links):
            try:
                # 获取自定义名称
                name = custom_names.get(str(idx), f'视频{idx + 1}')
                filename = f"{name}.mp4"
                filepath = os.path.join(task_folder, filename)

                logs.append(f"⬇ 正在下载: {name}")

                # 下载视频 - 使用更完整的请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://www.oiioii.ai/',
                    'Origin': 'https://www.oiioii.ai',
                    'Accept': '*/*',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'identity',
                    'Connection': 'keep-alive',
                }

                response = requests.get(url, headers=headers, stream=True, timeout=180, allow_redirects=True)
                response.raise_for_status()

                # 检查Content-Type是否为视频
                content_type = response.headers.get('Content-Type', '')
                content_length = int(response.headers.get('Content-Length', 0))

                # 如果文件太小（小于10KB），可能不是真正的视频
                if content_length > 0 and content_length < 10240:
                    logs.append(f"⚠ 跳过 {name}: 文件太小，可能不是视频")
                    continue

                # 写入文件
                total_size = 0
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)

                # 验证下载的文件
                if total_size < 10240:
                    os.remove(filepath)
                    logs.append(f"⚠ 跳过 {name}: 下载的文件太小")
                    continue

                # 检查文件头是否为视频格式
                with open(filepath, 'rb') as f:
                    header = f.read(12)
                    # MP4文件通常在第4-8字节包含 'ftyp'
                    is_mp4 = b'ftyp' in header or header.startswith(b'\x00\x00\x00')
                    # WebM文件以 0x1A45DFA3 开头
                    is_webm = header.startswith(b'\x1a\x45\xdf\xa3')
                    # 如果是oiioii的API链接，放宽检查（API可能返回有效视频但格式头不同）
                    is_oiioii_api = 'oiioii' in url.lower()

                    if not is_mp4 and not is_webm and not is_oiioii_api:
                        os.remove(filepath)
                        logs.append(f"⚠ 跳过 {name}: 文件格式无效")
                        continue

                downloaded_files.append(filepath)
                size_mb = total_size / (1024 * 1024)
                logs.append(f"✔ 下载完成: {name} ({size_mb:.1f}MB)")

            except Exception as e:
                logs.append(f"❌ 下载失败 ({name}): {str(e)}")

        if not downloaded_files:
            shutil.rmtree(task_folder, ignore_errors=True)
            return jsonify({
                'code': 500,
                'msg': '所有视频下载失败',
                'data': {'logs': logs}
            })

        # 打包为ZIP
        logs.append("📦 正在打包视频...")
        zip_id = f"{task_id}"
        zip_path = os.path.join(ZIP_FOLDER, zip_id)
        shutil.make_archive(zip_path, 'zip', task_folder)

        # 清理临时下载文件夹
        shutil.rmtree(task_folder, ignore_errors=True)

        logs.append(f"✔ 打包完成，共 {len(downloaded_files)} 个视频")

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': {
                'zip_id': f"{zip_id}.zip",
                'logs': logs
            }
        })

    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e), 'data': None})


@app.route('/api/zip/<zip_id>')
def get_zip(zip_id):
    """提供ZIP文件下载"""
    try:
        zip_path = os.path.join(ZIP_FOLDER, zip_id)
        if os.path.exists(zip_path):
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=f"视频合集_{zip_id}"
            )
        else:
            return jsonify({'code': 404, 'msg': '文件不存在'}), 404
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)}), 500


@app.route('/api/get_invite_code', methods=['GET'])
def get_invite_code():
    """
    获取邀请码（示例实现）
    你可以根据实际需求修改这个逻辑
    """
    try:
        # 这里可以实现你自己的邀请码逻辑
        # 比如从数据库获取、调用第三方API等
        invite_code = f"XYGS-{uuid.uuid4().hex[:8].upper()}"

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': {
                'invite_code': invite_code
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e), 'data': None})


if __name__ == '__main__':
    print("=" * 50)
    print("运工作室 - 视频下载工具 Web 1.0")
    print("=" * 50)
    print(f"服务启动中...")
    print(f"访问地址: http://localhost:5000")
    print("=" * 50)

    # 生产环境建议使用 waitress 或 gunicorn
    app.run(host='0.0.0.0', port=5000, debug=False)
