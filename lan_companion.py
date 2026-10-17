"""
SiamBraille 1.0 - LAN Mobile Companion & Remote Input Server
ระบบเซิร์ฟเวอร์จำลองการพิมพ์ระยะไกลผ่านอุปกรณ์อื่นในวงแลน (Local Area Network) เดียวกัน
ออกแบบให้เข้าถึงได้ 100% สำหรับผู้พิการทางสายตา (NVDA / JAWS / VoiceOver / TalkBack)
รองรับ:
- การพิมพ์ด้วยเสียง (Voice-to-Text / Web Speech API และ Mobile Dictation)
- แป้นสัมผัสเบรลล์ 6 จุดจำลองเครื่องเพอร์กินส์ (6-Key Braille Screen Touchpad)
- ส่งข้อความเข้าโปรแกรม SiamBraille 1.0 แบบเรียลไทม์ผ่าน Wi-Fi
- ช่องแสดง URL ที่อ่านและคัดลอกได้สะดวกรวดเร็วสำหรับ Screen Reader พร้อม QR Code
"""

import sys
import os
import io
import json
import socket
import threading
import webbrowser
from typing import Optional
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFrame, QApplication, QPlainTextEdit
)
from PyQt6.QtGui import QPixmap, QFont, QIcon, QKeySequence
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer

try:
    import qrcode
except ImportError:
    qrcode = None

def get_local_ip() -> str:
    """ค้นหา IPv4 ของเครื่องในวง LAN ปัจจุบัน"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

# ---------------------------------------------------------------------------
# HTML5 Mobile Companion Web Application
# ---------------------------------------------------------------------------
MOBILE_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>SiamBraille 1.0 — พิมพ์ระยะไกล</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #0284c7;
      --primary-hover: #0369a1;
      --success: #16a34a;
      --danger: #dc2626;
      --focus-ring: #38bdf8;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Sukhumvit Set", Tahoma, sans-serif;
      padding: 12px;
      line-height: 1.5;
      min-height: 100vh;
    }
    header {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 16px;
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      font-size: 1.15rem;
      font-weight: 700;
      color: #38bdf8;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.85rem;
      padding: 4px 10px;
      border-radius: 20px;
      background: rgba(22, 163, 74, 0.2);
      color: #4ade80;
      border: 1px solid #16a34a;
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #4ade80;
    }

    /* Tabs */
    .nav-tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
    }
    .tab-btn {
      flex: 1;
      padding: 12px 8px;
      background: var(--card);
      border: 2px solid var(--border);
      color: var(--text-muted);
      border-radius: 10px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      min-height: 48px;
    }
    .tab-btn.active {
      background: var(--primary);
      border-color: #38bdf8;
      color: #ffffff;
    }
    .tab-btn:focus-visible {
      outline: 3px solid var(--focus-ring);
    }

    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }

    /* Card Panels */
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
    }

    label {
      display: block;
      font-weight: 600;
      margin-bottom: 8px;
      color: #e2e8f0;
      font-size: 1rem;
    }

    textarea {
      width: 100%;
      height: 140px;
      background: #090d16;
      border: 2px solid var(--border);
      border-radius: 8px;
      color: #ffffff;
      padding: 12px;
      font-size: 1.1rem;
      font-family: inherit;
      resize: vertical;
    }
    textarea:focus {
      outline: none;
      border-color: var(--focus-ring);
      box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25);
    }

    /* Action Buttons */
    .btn-row {
      display: flex;
      gap: 10px;
      margin-top: 12px;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 14px 18px;
      font-size: 1rem;
      font-weight: 600;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      min-height: 52px;
      transition: background 0.15s;
    }
    .btn:focus-visible {
      outline: 3px solid var(--focus-ring);
    }
    .btn-primary {
      background: var(--primary);
      color: #ffffff;
      flex: 2;
    }
    .btn-primary:active {
      background: var(--primary-hover);
    }
    .btn-voice {
      background: #8b5cf6;
      color: #ffffff;
      flex: 1.5;
    }
    .btn-voice.recording {
      background: var(--danger);
      animation: pulse 1s infinite alternate;
    }
    @keyframes pulse {
      from { opacity: 1; }
      to { opacity: 0.6; }
    }
    .btn-secondary {
      background: #334155;
      color: #f1f5f9;
      flex: 1;
    }

    /* Braille Screen Input (6-key) */
    .braille-pad-container {
      margin-top: 6px;
    }
    .braille-preview {
      background: #090d16;
      border: 2px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      min-height: 60px;
      font-size: 1.5rem;
      letter-spacing: 2px;
      color: #38bdf8;
      word-break: break-all;
      margin-bottom: 12px;
    }
    .braille-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 12px;
    }
    .dot-btn {
      background: #1e293b;
      border: 3px solid #475569;
      border-radius: 14px;
      color: #ffffff;
      font-size: 1.4rem;
      font-weight: bold;
      height: 72px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      user-select: none;
      touch-action: manipulation;
    }
    .dot-btn.active {
      background: #0284c7;
      border-color: #38bdf8;
      box-shadow: 0 0 15px rgba(56, 189, 248, 0.5);
    }
    .dot-btn:focus-visible {
      outline: 3px solid var(--focus-ring);
    }
    .braille-controls {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .log-box {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-top: 10px;
      padding: 8px;
      border-radius: 6px;
      background: rgba(0,0,0,0.2);
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      border: 0;
    }
  </style>
</head>
<body>

  <header role="banner">
    <div>
      <div class="brand">SiamBraille 1.0</div>
      <div style="font-size: 0.8rem; color: #94a3b8;">ระบบพิมพ์ระยะไกลผ่านวง LAN</div>
    </div>
    <div class="status-badge" role="status" aria-live="polite">
      <div class="status-dot"></div>
      <span id="txtConn">เชื่อมต่อแล้ว</span>
    </div>
  </header>

  <div class="nav-tabs" role="tablist">
    <button class="tab-btn active" role="tab" id="tabVoice" aria-selected="true" onclick="switchTab('voice')">
      ⌨️ แป้นพิมพ์มือถือ / พิมพ์ข้อความ
    </button>
    <button class="tab-btn" role="tab" id="tabBraille" aria-selected="false" onclick="switchTab('braille')">
      ⠶ แป้นสัมผัสเบรลล์ 6 จุด
    </button>
  </div>

  <!-- TAB 1: Mobile Keyboard & Standard Text -->
  <main id="paneVoice" class="tab-content active" role="tabpanel" aria-labelledby="tabVoice">
    <div class="card">
      <label for="txtInput">ข้อความที่ต้องการส่งเข้าคอมพิวเตอร์:</label>
      <textarea id="txtInput" placeholder="พิมพ์ข้อความที่นี่ (สามารถแตะปุ่มไมโครโฟนบนแป้นพิมพ์มือถือเพื่อพิมพ์ด้วยเสียงได้)..." aria-describedby="txtHint"></textarea>
      <div id="txtHint" class="sr-only">พิมพ์ข้อความ หรือใช้ปุ่มไมค์บนแป้นพิมพ์ของโทรศัพท์เพื่อพิมพ์ด้วยเสียง</div>

      <div class="btn-row">
        <button id="btnSend" class="btn btn-primary" onclick="sendText()" aria-label="ส่งข้อความเข้าโปรแกรม SiamBraille บนคอมพิวเตอร์">
          📤 ส่งเข้าคอมฯ
        </button>
        <button class="btn btn-secondary" onclick="clearText()" aria-label="ล้างข้อความในกล่องพิมพ์">
          🧹 ล้างข้อความ
        </button>
      </div>

      <div id="statusMsg" class="log-box" role="status" aria-live="polite">
        พร้อมรับข้อความ
      </div>
    </div>
  </main>

  <!-- TAB 2: Perkins 6-Key Braille Screen Input -->
  <main id="paneBraille" class="tab-content" role="tabpanel" aria-labelledby="tabBraille">
    <div class="card braille-pad-container">
      <label>ข้อความอักษรเบรลล์ที่พิมพ์:</label>
      <div id="brailleDisplay" class="braille-preview" aria-live="polite" aria-label="ตัวอย่างเบรลล์ที่พิมพ์">⠀</div>

      <div class="braille-grid" role="group" aria-label="แป้นจุดเบรลล์ 6 จุด">
        <button class="dot-btn" id="dot1" onclick="toggleDot(1)" aria-label="จุด 1 ซ้ายบน">จุด 1 (⠁)</button>
        <button class="dot-btn" id="dot4" onclick="toggleDot(4)" aria-label="จุด 4 ขวาบน">จุด 4 (⠈)</button>
        <button class="dot-btn" id="dot2" onclick="toggleDot(2)" aria-label="จุด 2 ซ้ายกลาง">จุด 2 (⠂)</button>
        <button class="dot-btn" id="dot5" onclick="toggleDot(5)" aria-label="จุด 5 ขวากลาง">จุด 5 (⠐)</button>
        <button class="dot-btn" id="dot3" onclick="toggleDot(3)" aria-label="จุด 3 ซ้ายล่าง">จุด 3 (⠄)</button>
        <button class="dot-btn" id="dot6" onclick="toggleDot(6)" aria-label="จุด 6 ขวาล่าง">จุด 6 (⠠)</button>
      </div>

      <div class="braille-controls">
        <button class="btn btn-primary" onclick="confirmBrailleCell()" aria-label="ตกลงเซลล์เบรลล์ Enter Cell">
          ↵ เคาะเซลล์ (Enter)
        </button>
        <button class="btn btn-secondary" onclick="addBrailleSpace()" aria-label="เว้นวรรค Space">
          ␣ เว้นวรรค
        </button>
        <button class="btn btn-secondary" onclick="backspaceBraille()" aria-label="ลบตัวอักษรล่าสุด Backspace">
          ⌫ ลบ (Back)
        </button>
        <button class="btn btn-primary" onclick="sendBrailleToPC()" aria-label="ส่งข้อความเบรลล์เข้าคอมพิวเตอร์">
          📤 ส่งเข้าคอมฯ
        </button>
      </div>
    </div>
  </main>

  <script>
    // Audio Chime (Web Audio API)
    function playBeep(freq = 880, duration = 0.12) {
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + duration);
      } catch (e) {}
    }

    // Switch Tabs
    function switchTab(mode) {
      document.getElementById('paneVoice').classList.toggle('active', mode === 'voice');
      document.getElementById('paneBraille').classList.toggle('active', mode === 'braille');
      document.getElementById('tabVoice').classList.toggle('active', mode === 'voice');
      document.getElementById('tabBraille').classList.toggle('active', mode === 'braille');
      document.getElementById('tabVoice').setAttribute('aria-selected', mode === 'voice');
      document.getElementById('tabBraille').setAttribute('aria-selected', mode === 'braille');
    }

    // Send Text to PC
    async function sendText() {
      const text = document.getElementById('txtInput').value;
      if (!text.trim()) {
        document.getElementById('statusMsg').textContent = 'กรุณาพิมพ์หรือพูดข้อความก่อนส่ง';
        return;
      }
      document.getElementById('statusMsg').textContent = 'กำลังส่งไปยัง SiamBraille...';
      try {
        const res = await fetch('/api/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text, mode: 'append' })
        });
        const data = await res.json();
        if (data.status === 'ok') {
          playBeep(1760, 0.15);
          document.getElementById('statusMsg').textContent = '✅ ส่งเข้าคอมพิวเตอร์เรียบร้อยแล้ว!';
          document.getElementById('txtInput').value = '';
        } else {
          document.getElementById('statusMsg').textContent = '⚠️ ส่งไม่สำเร็จ: ' + (data.message || 'เกิดข้อผิดพลาด');
        }
      } catch (err) {
        document.getElementById('statusMsg').textContent = '❌ ส่งข้อความล้มเหลว กรุณาตรวจ Wi-Fi';
      }
    }

    function clearText() {
      document.getElementById('txtInput').value = '';
      document.getElementById('statusMsg').textContent = 'ล้างกล่องข้อความแล้ว';
    }

    // ----------------------------------------------------
    // Perkins 6-Key Braille Engine
    // ----------------------------------------------------
    let currentDots = 0; // bitmask for dots 1-6
    let brailleBuffer = "";

    function toggleDot(num) {
      const bit = 1 << (num - 1);
      currentDots ^= bit;
      const btn = document.getElementById('dot' + num);
      btn.classList.toggle('active', (currentDots & bit) !== 0);
      playBeep(400 + (num * 100), 0.05);
    }

    function confirmBrailleCell() {
      let char = " ";
      if (currentDots > 0) {
        // Unicode Braille Patterns: 0x2800 + bitmask
        char = String.fromCharCode(0x2800 + currentDots);
      }
      brailleBuffer += char;
      updateBrailleDisplay();
      resetDots();
      playBeep(1000, 0.08);
    }

    function addBrailleSpace() {
      brailleBuffer += " ";
      updateBrailleDisplay();
      resetDots();
      playBeep(600, 0.08);
    }

    function backspaceBraille() {
      if (brailleBuffer.length > 0) {
        brailleBuffer = brailleBuffer.slice(0, -1);
        updateBrailleDisplay();
        playBeep(400, 0.08);
      }
    }

    function resetDots() {
      currentDots = 0;
      for (let i = 1; i <= 6; i++) {
        document.getElementById('dot' + i).classList.remove('active');
      }
    }

    function updateBrailleDisplay() {
      document.getElementById('brailleDisplay').textContent = brailleBuffer || "⠀";
    }

    async function sendBrailleToPC() {
      if (!brailleBuffer.trim()) {
        alert('ยังไม่มีตัวอักษรเบรลล์');
        return;
      }
      try {
        const res = await fetch('/api/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: brailleBuffer, mode: 'append' })
        });
        const data = await res.json();
        if (data.status === 'ok') {
          playBeep(1760, 0.15);
          alert('ส่งอักษรเบรลล์เข้าคอมพิวเตอร์เรียบร้อยแล้ว');
          brailleBuffer = "";
          updateBrailleDisplay();
        }
      } catch (e) {
        alert('เกิดข้อผิดพลาดในการส่ง');
      }
    }
  </script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Background HTTP Server for LAN Mobile Input
# ---------------------------------------------------------------------------
class LANServerSignals(QObject):
    text_received = pyqtSignal(str, str)     # text, mode
    client_action = pyqtSignal(str)          # log message

class LANCompanionHandler(BaseHTTPRequestHandler):
    signals: Optional[LANServerSignals] = None
    app_reference = None

    def log_message(self, format, *args):
        # ปิดการพิมพ์ log ลง console รบกวน terminal
        pass

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(MOBILE_HTML.encode("utf-8"))
        elif url.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            status_data = {
                "program": "SiamBraille 1.0",
                "status": "ready"
            }
            self.wfile.write(json.dumps(status_data).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/send":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)
                text = data.get("text", "")
                mode = data.get("mode", "append")

                if self.signals:
                    self.signals.text_received.emit(text, mode)
                    self.signals.client_action.emit(f"ได้รับข้อความ: {text[:40]}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")


class LANCompanionServer:
    """ตัวควบคุมเบื้องหลังของ LAN Companion HTTP Server"""
    def __init__(self, port: int = 8080):
        self.port = port
        self.ip = get_local_ip()
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.signals = LANServerSignals()
        self.is_running = False

    def start(self):
        if self.is_running:
            return True
        try:
            # กำหนด handler ให้เชื่อมกับ Qt signals
            handler_class = LANCompanionHandler
            handler_class.signals = self.signals
            
            # ตรวจสอบพอร์ต หากชนให้ขยับไปพอร์ตถัดไป
            for p in [self.port, 8081, 8888, 8000]:
                try:
                    self.server = ThreadingHTTPServer(('0.0.0.0', p), handler_class)
                    self.port = p
                    break
                except OSError:
                    continue
            
            if not self.server:
                return False

            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.is_running = True
            return True
        except Exception:
            self.is_running = False
            return False

    def stop(self):
        if self.server and self.is_running:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.is_running = False

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}"


# ---------------------------------------------------------------------------
# Accessible Dialog for Screen Reader & Sighted Users
# ---------------------------------------------------------------------------
class RemoteInputDialog(QDialog):
    """
    หน้าต่างเปิดระบบพิมพ์ผ่านมือถือในวงแลน (Remote Mobile Input)
    ออกแบบตามหลักการเข้าถึงข้อมูลสากล (Web & Software Accessibility 100%):
    - สำหรับคนตาบอด: มี URL ที่โฟกัสได้, ปุ่มคัดลอกด้วย Alt+C, ปุ่มเปิดในเบราว์เซอร์ Alt+O, เสียงอ่าน NVDA ชัดเจน
    - สำหรับคนสายตาปกติ / ผู้ช่วย: มี QR Code ขนาดใหญ่ สแกนเข้าได้ทันที
    """
    def __init__(self, parent=None, server: Optional[LANCompanionServer] = None):
        super().__init__(parent)
        self.server = server
        self.setWindowTitle("พิมพ์ผ่านมือถือในวง LAN - SiamBraille 1.0")
        self.setFixedSize(490, 460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setAccessibleName("หน้าต่างพิมพ์ผ่านมือถือในวง LAN SiamBraille 1.0")
        self.setAccessibleDescription(
            "ระบบพิมพ์ข้อความจากสมาร์ตโฟนหรือแท็บเล็ตในวงแลนเดียวกัน "
            "รองรับการพิมพ์ด้วยเสียงและแป้นพิมพ์สัมผัสเบรลล์ 6 จุด"
        )

        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Tahoma', 'Segoe UI', sans-serif;
                font-size: 11px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                background-color: #ffffff;
                color: #0f172a;
                font-size: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QLineEdit {
                font-size: 11.5px;
                font-weight: bold;
                padding: 4px 8px;
                border: 1.5px solid #0284c7;
                border-radius: 4px;
                background-color: #f0f9ff;
                color: #0369a1;
            }
            QLineEdit:focus {
                border-color: #0369a1;
                background-color: #e0f2fe;
            }
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
                min-height: 26px;
            }
            QPushButton:focus {
                outline: 2px solid #0284c7;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header Title
        lbl_title = QLabel("📱 พิมพ์ผ่านมือถือหรืออุปกรณ์อื่นในวง LAN (Wi-Fi)")
        lbl_title.setStyleSheet("font-size: 13.5px; font-weight: bold; color: #0369a1;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "ผู้ใช้สามารถใช้สมาร์ตโฟนที่ต่อ Wi-Fi วงเดียวกัน เปิดหน้าเว็บเพื่อ "
            "<b>พิมพ์ข้อความ (ใช้แป้นพิมพ์หรือไมค์บนมือถือ)</b> หรือ <b>ใช้แป้นสัมผัสเบรลล์ 6 จุด</b> "
            "ข้อความจะถูกส่งเข้ามายังเอกสารใน SiamBraille 1.0 บนคอมพิวเตอร์ทันที"
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #475569; font-size: 10.5px; line-height: 1.3;")
        layout.addWidget(lbl_desc)

        # Group: URL & Actions (สำหรับผู้ใช้ Screen Reader และคีย์บอร์ด)
        grp_url = QGroupBox("1. ที่อยู่เว็บไซต์สำหรับเปิดบนมือถือ (URL for Mobile)")
        grp_layout = QVBoxLayout(grp_url)

        lbl_url_guide = QLabel("กด Alt+C เพื่อคัดลอกลิงก์ หรือกด Alt+O เพื่อเปิดในเบราว์เซอร์:")
        lbl_url_guide.setStyleSheet("color: #334155; font-size: 10px;")
        grp_layout.addWidget(lbl_url_guide)

        url_box = QHBoxLayout()
        self.txt_url = QLineEdit(self.server.url if self.server else "http://127.0.0.1:8080")
        self.txt_url.setReadOnly(True)
        self.txt_url.setAccessibleName("ที่อยู่เว็บไซต์สำหรับเปิดบนมือถือ")
        self.txt_url.setAccessibleDescription(f"URL สำหรับพิมพ์บนมือถือคือ {self.txt_url.text()}")
        url_box.addWidget(self.txt_url)

        self.btn_copy = QPushButton("📋 คัดลอก URL (&C)")
        self.btn_copy.setShortcut(QKeySequence("Alt+C"))
        self.btn_copy.setStyleSheet("background-color: #0284c7; color: #ffffff; border: none;")
        self.btn_copy.setAccessibleName("คัดลอกที่อยู่เว็บไซต์สำหรับพิมพ์ผ่านมือถือ")
        self.btn_copy.setAccessibleDescription("กด Alt+C เพื่อคัดลอก URL ลงในคลิปบอร์ดสำหรับนำไปส่งต่อ")
        self.btn_copy.clicked.connect(self.copy_url)
        url_box.addWidget(self.btn_copy)

        self.btn_open = QPushButton("🌐 เปิดในเบราว์เซอร์ (&O)")
        self.btn_open.setShortcut(QKeySequence("Alt+O"))
        self.btn_open.setStyleSheet("background-color: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1;")
        self.btn_open.setAccessibleName("เปิดหน้าเว็บพิมพ์ระยะไกลในเบราว์เซอร์")
        self.btn_open.setAccessibleDescription("กด Alt+O เพื่อเปิดหน้าเว็บพิมพ์ระยะไกลบนเบราว์เซอร์ของเครื่องนี้")
        self.btn_open.clicked.connect(self.open_in_browser)
        url_box.addWidget(self.btn_open)

        grp_layout.addLayout(url_box)
        layout.addWidget(grp_url)

        # Group: QR Code & Status (สำหรับผู้ช่วยสายตาปกติ หรือผู้ใช้ทั่วไป)
        grp_qr = QGroupBox("2. สแกนด้วยกล้องมือถือ (QR Code สำหรับผู้ช่วยหรือบุคคลสายตาปกติ)")
        qr_layout = QHBoxLayout(grp_qr)

        self.lbl_qr = QLabel()
        self.lbl_qr.setFixedSize(110, 110)
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;")
        self.lbl_qr.setAccessibleName("คิวอาร์โค้ด สำหรับเปิดหน้าเว็บพิมพ์บนมือถือ")
        self.lbl_qr.setAccessibleDescription("รูปภาพคิวอาร์โค้ดสำหรับผู้ช่วยสายตาปกติใช้กล้องมือถือสแกน")
        qr_layout.addWidget(self.lbl_qr)

        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(4)
        
        self.lbl_server_status = QLabel(f"🟢 สถานะเซิร์ฟเวอร์: <b>กำลังทำงานที่พอร์ต {self.server.port if self.server else 8080}</b>")
        self.lbl_server_status.setStyleSheet("color: #16a34a; font-size: 11px;")
        info_vbox.addWidget(self.lbl_server_status)

        lbl_steps = QLabel(
            "• โทรศัพท์มือถือและคอมพิวเตอร์ต้องเชื่อมต่อ <b>Wi-Fi วงเดียวกัน</b><br>"
            "• เมื่อเข้าหน้าเว็บแล้ว สามารถกดปุ่มไมค์เพื่อ <b>พูดภาษาไทย</b> ได้ทันที<br>"
            "• หน้าเว็บรองรับโปรแกรมอ่านหน้าจอ VoiceOver (iPhone) และ TalkBack (Android)"
        )
        lbl_steps.setWordWrap(True)
        lbl_steps.setStyleSheet("color: #475569; font-size: 10px; line-height: 1.3;")
        info_vbox.addWidget(lbl_steps)

        self.lbl_last_received = QLabel("สถานะข้อความล่าสุด: ยังไม่มีข้อความเข้ามา")
        self.lbl_last_received.setStyleSheet("color: #64748b; font-size: 9.5px; font-style: italic;")
        info_vbox.addWidget(self.lbl_last_received)

        qr_layout.addLayout(info_vbox)
        layout.addWidget(grp_qr)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_close = QPushButton("ปิดหน้าต่าง (&X)")
        btn_close.setShortcut(QKeySequence("Alt+X"))
        btn_close.setStyleSheet("background-color: #e2e8f0; color: #0f172a; border: 1px solid #94a3b8; font-size: 11px; padding: 4px 14px; min-height: 26px;")
        btn_close.setAccessibleName("ปิดหน้าต่าง")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

        # สร้าง QR Code ภาพ
        self.generate_qr()

        # เชื่อมต่อ Signal เพื่ออัปเดตข้อความเมื่อมีข้อความเข้า
        if self.server:
            self.server.signals.client_action.connect(self.on_client_action)

    def generate_qr(self):
        url = self.txt_url.text()
        if qrcode:
            try:
                img = qrcode.make(url)
                buf = io.BytesIO()
                img.save(buf)
                pix = QPixmap()
                pix.loadFromData(buf.getvalue())
                self.lbl_qr.setPixmap(pix.scaled(104, 104, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            except Exception:
                self.lbl_qr.setText("QR Code Error")
        else:
            self.lbl_qr.setText("ไม่มีไลบรารี qrcode")

    def copy_url(self):
        url = self.txt_url.text()
        cb = QApplication.clipboard()
        if cb:
            cb.setText(url)
        self.btn_copy.setText("✅ คัดลอกแล้ว!")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("📋 คัดลอก URL (&C)"))

        # ประกาศเสียง NVDA ชัดเจน
        from tbtw_app import speak_nvda
        speak_nvda(f"คัดลอกที่อยู่เว็บไซต์เรียบร้อยแล้ว: {url}")

    def open_in_browser(self):
        url = self.txt_url.text()
        webbrowser.open(url)
        from tbtw_app import speak_nvda
        speak_nvda("เปิดหน้าเว็บพิมพ์ระยะไกลในเว็บเบราว์เซอร์แล้ว")

    def on_client_action(self, msg: str):
        self.lbl_last_received.setText(f"สถานะข้อความล่าสุด: {msg}")

    def showEvent(self, event):
        super().showEvent(event)
        # โฟกัสไปที่ปุ่มคัดลอก URL เพื่อให้ผู้ใช้กด Space/Enter หรือ Alt+C ได้ทันที
        self.btn_copy.setFocus()
        url = self.txt_url.text()
        from tbtw_app import speak_nvda
        speak_nvda(
            f"เปิดระบบพิมพ์ผ่านมือถือในวงแลนแล้ว ที่อยู่เว็บไซต์คือ {url} "
            "กด Alt+C เพื่อคัดลอกลิงก์ หรือกด Alt+O เพื่อเปิดในเบราว์เซอร์"
        )
