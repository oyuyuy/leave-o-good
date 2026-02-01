# 运工作室 - 视频下载工具 Web 1.0

## 项目结构

```
文件包/
├── app.py              # Flask 后端主程序
├── index.html          # 前端页面
├── requirements.txt    # Python 依赖
├── start.bat           # Windows 启动脚本（生产模式）
├── start_dev.bat       # Windows 启动脚本（开发模式）
├── static/             # 静态资源目录
│   └── meishaonv.png   # 顶部图片（需自行添加）
├── downloads/          # 临时下载目录（自动创建）
└── zips/               # ZIP 打包目录（自动创建）
```

## 部署步骤

### 1. 安装 Python
确保服务器已安装 Python 3.8 或更高版本。

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 添加静态资源
将 `meishaonv.png` 图片放入 `static/` 目录。

### 4. 启动服务
- **生产模式**：双击 `start.bat`
- **开发模式**：双击 `start_dev.bat`

### 5. 访问网站
浏览器打开 `http://服务器IP:5000`

## 防火墙设置
确保服务器的 5000 端口已开放：
- Windows 防火墙：入站规则允许 TCP 5000
- 云服务器：安全组开放 5000 端口

## 注意事项
1. 2G2核服务器资源有限，建议限制同时下载的视频数量
2. 下载的临时文件会在 5 分钟后自动清理
3. 如需修改端口，编辑 `app.py` 最后一行的 `port=5000`

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/parse` | POST | 解析HTML提取视频URL |
| `/api/download` | POST | 下载视频并打包ZIP |
| `/api/zip/<id>` | GET | 获取ZIP文件 |
| `/api/get_invite_code` | GET | 获取邀请码 |
