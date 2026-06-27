"""
Windows VM 帧差检测 + 截图/输入 HTTP 服务 - 安装包版
=============================================
纯 HTTP 控制，无需 VNC。

后台线程：持续 PIL.ImageGrab 截图 → 像素比对 → 仅存储有显著变化的帧。
输入接口：pyautogui 模拟鼠标键盘。

安装位置（默认）: %LOCALAPPDATA%\WinVMService\
自定义安装:        set INSTALL_DIR=D:\MyService && setup.bat

依赖安装:
  pip install flask pyautogui pillow numpy waitress mss
"""

import os
import io
import base64
import time
import threading
import logging
from datetime import datetime

import numpy as np
from PIL import Image, ImageGrab
import pyautogui

from flask import Flask, request, jsonify

# ─── 配置 ──────────────────────────────────────────────────────────
# 可通过环境变量覆盖
FRAME_INTERVAL = float(os.environ.get("FRAME_INTERVAL", "0.5"))
DIFF_THRESHOLD = float(os.environ.get("DIFF_THRESHOLD", "0.05"))
SCREENSHOT_MAX_W = int(os.environ.get("SCREENSHOT_MAX_W", "0"))    # 0 = 不限缩
OUTPUT_FORMAT = os.environ.get("OUTPUT_FORMAT", "JPEG")
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "85"))
PORT = int(os.environ.get("PORT", "5000"))
HOST = os.environ.get("HOST", "0.0.0.0")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# ─── 日志 ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("winvm")

# ─── 全局帧缓冲 ────────────────────────────────────────────────────
_frame_lock = threading.Lock()
_latest_frame: bytes | None = None
_latest_ts: float = 0.0
_frame_width: int = 0
_frame_height: int = 0
_frame_changed_counter: int = 0

# ─── 帧差检测线程 ──────────────────────────────────────────────────
def _frame_monitor():
    global _latest_frame, _latest_ts, _frame_width, _frame_height, _frame_changed_counter

    logger.info("帧差监控线程启动，间隔=%.1fs，变化阈值=%.1f%%",
                FRAME_INTERVAL, DIFF_THRESHOLD * 100)
    logger.info("使用 PIL.ImageGrab 截图（兼容远程会话）")

    prev = None

    while True:
        try:
            img = ImageGrab.grab()

            if img is None or img.width == 0 or img.height == 0:
                logger.warning("截图为空 (%dx%d)",
                               img.width if img else 0,
                               img.height if img else 0)
                time.sleep(FRAME_INTERVAL)
                continue

            arr = np.array(img, dtype=np.uint8)
            _frame_width, _frame_height = img.size

            if prev is None:
                prev = arr
                _encode_and_store_from_pil(img)
                logger.info("首帧已捕获 %dx%d", _frame_width, _frame_height)
                time.sleep(FRAME_INTERVAL)
                continue

            # 像素比对（中央 90% ROI，缩小到 160x90 加速）
            h, w = arr.shape[:2]
            crop_h, crop_w = int(h * 0.9), int(w * 0.9)
            y0, x0 = (h - crop_h) // 2, (w - crop_w) // 2
            curr_roi = arr[y0:y0+crop_h, x0:x0+crop_w]
            prev_roi = prev[y0:y0+crop_h, x0:x0+crop_w]

            curr_small = Image.fromarray(curr_roi).resize((160, 90), Image.BILINEAR)
            prev_small = Image.fromarray(prev_roi).resize((160, 90), Image.BILINEAR)

            diff = np.mean(np.abs(np.array(curr_small, dtype=np.int16) -
                                  np.array(prev_small, dtype=np.int16))) / 255.0

            if diff > DIFF_THRESHOLD:
                prev = arr
                _encode_and_store_from_pil(img)
                _frame_changed_counter += 1
                logger.debug("帧变化：diff=%.3f (阈值=%.2f) #%d",
                             diff, DIFF_THRESHOLD, _frame_changed_counter)

        except Exception as e:
            logger.error("帧差检测异常：%s", e)

        time.sleep(FRAME_INTERVAL)


def _encode_and_store_from_pil(img: Image.Image):
    """将 PIL 图像编码后存入全局缓冲。"""
    global _latest_frame, _latest_ts, _frame_width, _frame_height

    _frame_width, _frame_height = img.size

    if SCREENSHOT_MAX_W > 0 and img.width > SCREENSHOT_MAX_W:
        ratio = SCREENSHOT_MAX_W / img.width
        new_size = (SCREENSHOT_MAX_W, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    if OUTPUT_FORMAT.upper() == "PNG":
        img.save(buf, format="PNG")
    else:
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)

    with _frame_lock:
        _latest_frame = buf.getvalue()
        _latest_ts = time.time()


# ─── Flask API ─────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/ping", methods=["GET"])
def ping():
    return "pong"


@app.route("/frame", methods=["GET"])
def get_frame():
    since = request.args.get("since", type=float, default=0)

    with _frame_lock:
        if _latest_frame is None:
            return jsonify({"error": "首帧尚未就绪"}), 503

        if since > 0 and _latest_ts <= since:
            return jsonify({
                "changed": False,
                "ts": _latest_ts,
                "changed_count": _frame_changed_counter,
            }), 200

        data = _latest_frame
        ts = _latest_ts
        w, h = _frame_width, _frame_height
        cc = _frame_changed_counter

    b64 = base64.b64encode(data).decode("ascii")
    fmt = "JPEG" if OUTPUT_FORMAT.upper() != "PNG" else "PNG"

    return jsonify({
        "changed": True,
        "width": w,
        "height": h,
        "format": fmt,
        "ts": ts,
        "changed_count": cc,
        "base64": b64,
    })


@app.route("/frame/raw", methods=["GET"])
def get_frame_raw():
    with _frame_lock:
        if _latest_frame is None:
            return "No frame", 503
        data = _latest_frame

    mime = "image/jpeg" if OUTPUT_FORMAT.upper() != "PNG" else "image/png"
    return data, 200, {"Content-Type": mime}


@app.route("/input", methods=["POST"])
def handle_input():
    if not request.is_json:
        return jsonify({"error": "需要 JSON body"}), 400

    data = request.get_json()
    action = data.get("action", "").lower()

    try:
        pyautogui.FAILSAFE = False

        if action == "move":
            x = int(data["x"])
            y = int(data["y"])
            pyautogui.moveTo(x, y, duration=0.05)

        elif action == "click":
            x = int(data.get("x", 0))
            y = int(data.get("y", 0))
            btn = data.get("button", "left")
            clicks = int(data.get("clicks", 1))
            pyautogui.click(x, y, clicks=clicks, button=btn, interval=0.03)

        elif action == "double_click":
            x = int(data.get("x", 0))
            y = int(data.get("y", 0))
            btn = data.get("button", "left")
            pyautogui.doubleClick(x, y, button=btn)

        elif action == "drag":
            x1 = int(data.get("x", 0))
            y1 = int(data.get("y", 0))
            dx = int(data.get("dx", 0))
            dy = int(data.get("dy", 0))
            btn = data.get("button", "left")
            pyautogui.dragTo(x1 + dx, y1 + dy, duration=0.15, button=btn)

        elif action == "scroll":
            sy = int(data.get("scroll_y", 0))
            pyautogui.scroll(sy)

        elif action == "press":
            key = str(data.get("keys", ""))
            if not key:
                raise ValueError("keys 必填")
            pyautogui.press(key)

        elif action == "type":
            text = str(data.get("text", ""))
            if not text:
                raise ValueError("text 必填")
            pyautogui.write(text, interval=0.01)

        elif action == "hotkey":
            mods = data.get("modifiers", [])
            final_key = str(data.get("keys", ""))
            if not final_key:
                raise ValueError("keys 必填")
            pyautogui.hotkey(*mods, final_key)

        else:
            return jsonify({"error": f"未知操作：{action}"}), 400

        return jsonify({"status": "ok", "action": action})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/screen", methods=["GET"])
def screen_shot():
    try:
        img = ImageGrab.grab()

        if SCREENSHOT_MAX_W > 0 and img.width > SCREENSHOT_MAX_W:
            ratio = SCREENSHOT_MAX_W / img.width
            img = img.resize((SCREENSHOT_MAX_W, int(img.height * ratio)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return buf.getvalue(), 200, {"Content-Type": "image/jpeg"}
    except Exception as e:
        logger.error("截图失败：%s", e)
        return jsonify({"error": str(e)}), 500


# ─── 启动 ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Windows VM 控制服务启动")
    logger.info("  截图：    PIL.ImageGrab")
    logger.info("  输入：    pyautogui (SendInput)")
    logger.info("  帧差阈值：%.1f%%", DIFF_THRESHOLD * 100)
    logger.info("  输出格式：%s (质量=%d)", OUTPUT_FORMAT, JPEG_QUALITY)
    logger.info("  监听端口：%s:%d", HOST, PORT)
    logger.info("  缩图上限：%dpx (0=不限)", SCREENSHOT_MAX_W)
    logger.info("=" * 50)

    monitor_thread = threading.Thread(target=_frame_monitor, daemon=True)
    monitor_thread.start()

    try:
        from waitress import serve
        logger.info("使用 waitress 生产级服务器")
        serve(app, host=HOST, port=PORT)
    except ImportError:
        logger.info("waitress 未安装，使用 Flask 开发服务器（仅建议测试用）")
        app.run(host=HOST, port=PORT, debug=False)
