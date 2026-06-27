# WinVMService

Windows VM 帧差检测 + 截图/输入 HTTP 服务。

纯 Python，零依赖 GUI 框架，通过 HTTP API 控制 Windows VM 桌面。

## 快速安装

```batch
# 1. 下载安装包
# 2. 双击 install.bat
# 3. 按提示完成安装
```

## 手动安装

```batch
pip install flask pyautogui pillow numpy waitress mss
python winvm_service.py
```

## API 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ping` | 健康检查 → `"pong"` |
| GET | `/screen` | 实时截图 (JPEG) |
| GET | `/frame` | 帧缓冲 (JSON, base64 JPEG/PNG) |
| GET | `/frame/raw` | 帧缓冲 (Raw JPEG/PNG) |
| POST | `/input` | 输入控制 (JSON body) |

### POST /input

```json
// 移动鼠标
{"action": "move", "x": 960, "y": 540}

// 点击
{"action": "click", "x": 960, "y": 540, "button": "left", "clicks": 1}

// 双击
{"action": "double_click", "x": 960, "y": 540}

// 拖拽
{"action": "drag", "x": 100, "y": 200, "dx": 300, "dy": 0}

// 滚轮
{"action": "scroll", "scroll_y": -3}

// 按键
{"action": "press", "keys": "enter"}

// 输入文字
{"action": "type", "text": "你好世界"}

// 组合键 (Ctrl+Alt+Del)
{"action": "hotkey", "modifiers": ["ctrl", "alt"], "keys": "del"}
```

## 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | 5000 | HTTP 端口 |
| `HOST` | 0.0.0.0 | 监听地址 |
| `SCREENSHOT_MAX_W` | 0 | 缩图上限 (0=原图) |
| `JPEG_QUALITY` | 85 | JPEG 质量 |
| `FRAME_INTERVAL` | 0.5 | 截图间隔 (秒) |
| `DIFF_THRESHOLD` | 0.05 | 像素变化阈值 (5%) |
| `LOG_LEVEL` | INFO | 日志级别 |

## 目录结构

```
WinVMService/
├── winvm_service.py    # 主服务
├── install.bat         # 安装程序
└── uninstall.bat       # 卸载程序
```

## 系统要求

- Windows 10/11（64位）
- Python 3.8+
- 依赖: flask, pyautogui, pillow, numpy, waitress, mss
- 网络: 端口 5000 未被占用

## 常见问题

**Q: 截图是黑屏或报错？**
A: 确保服务运行在用户交互会话（Session 1），非 Session 0。安装程序已自动配置。

**Q: 端口被占用？**
A: `set PORT=8080 && python winvm_service.py`

**Q: 如何修改截图分辨率？**
A: 设置环境变量 `SCREENSHOT_MAX_W=1920`（等比例缩放）或 `0`（原图）。
