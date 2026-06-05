"""TH2817B 电容数据采集助手 - 桌面版"""

import csv
import threading
import queue
import re
import time
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

import serial
import serial.tools.list_ports


class TH2817BApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TH2817B 电容数据采集系统")
        self.root.geometry("1000x760")
        self.root.minsize(900, 620)

        self.serial_port: serial.Serial | None = None
        self.is_connected = False
        self.is_acquiring = False
        self.stop_event = threading.Event()
        self.ui_queue: queue.Queue = queue.Queue()
        self.collected_data: list[dict] = []
        self.save_path: str | None = None
        self.record_path: str | None = None

        self._build_ui()
        self._sync_filename()
        self._sync_record_filename()
        self.freq_var.trace_add("write", lambda *_: self._sync_filename())
        self.freq_var.trace_add("write", lambda *_: self._sync_record_filename())
        self.temp_var.trace_add("write", lambda *_: self._sync_filename())
        self.temp_var.trace_add("write", lambda *_: self._sync_record_filename())
        self._refresh_ports()
        self._poll_ui_queue()

    # ── UI 构建 ──────────────────────────────────────────────

    def _build_ui(self):
        # macOS-inspired light color palette
        bg_win = "#F5F5F7"
        bg_card = "#FFFFFF"
        fg_primary = "#1D1D1F"
        fg_secondary = "#86868B"
        accent_blue = "#007AFF"
        accent_green = "#34C759"
        accent_red = "#FF3B30"
        accent_orange = "#FF9F0A"
        border_color = "#D2D2D7"
        font_family = "Microsoft YaHei UI"

        self.root.configure(bg=bg_win)

        style = ttk.Style()
        style.theme_use("clam")

        # ── Global ──
        style.configure(".", background=bg_card, foreground=fg_primary, font=(font_family, 10))
        style.configure("TLabel", background=bg_card, foreground=fg_primary)
        style.configure("Bold.TLabel", font=(font_family, 10, "bold"))
        style.configure("Secondary.TLabel", foreground=fg_secondary)

        # ── Frame ──
        style.configure("TFrame", background=bg_card)
        style.configure("Window.TFrame", background=bg_win)

        # ── LabelFrame (card container) ──
        style.configure("Card.TLabelframe", background=bg_card, foreground=fg_primary,
                        bordercolor=border_color, relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=bg_card, foreground=fg_primary,
                        font=(font_family, 10, "bold"))

        # ── Entry / Combobox / Spinbox ──
        style.configure("TEntry", fieldbackground=bg_card, foreground=fg_primary,
                        insertcolor=fg_primary, bordercolor=border_color,
                        relief="solid", borderwidth=1, padding=4)
        style.map("TEntry", fieldbackground=[("focus", bg_card)],
                  bordercolor=[("focus", accent_blue)])
        style.configure("TCombobox", fieldbackground=bg_card, foreground=fg_primary,
                        arrowcolor=fg_secondary, bordercolor=border_color,
                        relief="solid", borderwidth=1, padding=4)
        style.map("TCombobox", fieldbackground=[("readonly", bg_card)])
        style.configure("TSpinbox", fieldbackground=bg_card, foreground=fg_primary,
                        bordercolor=border_color, relief="solid", borderwidth=1)

        # ── Buttons (flat, macOS style) ──
        style.configure("Blue.TButton", background=accent_blue, foreground="white",
                        font=(font_family, 10, "bold"), borderwidth=0,
                        focuscolor="none", relief="flat", padding=(16, 8))
        style.map("Blue.TButton", background=[("active", "#0066CC")])
        style.configure("Green.TButton", background=accent_green, foreground="white",
                        font=(font_family, 11, "bold"), borderwidth=0,
                        focuscolor="none", relief="flat", padding=(20, 10))
        style.map("Green.TButton", background=[("active", "#2DB84E")])
        style.configure("Red.TButton", background=accent_red, foreground="white",
                        font=(font_family, 11, "bold"), borderwidth=0,
                        focuscolor="none", relief="flat", padding=(20, 10))
        style.map("Red.TButton", background=[("active", "#D62929")])
        style.configure("Orange.TButton", background=accent_orange, foreground="white",
                        font=(font_family, 10, "bold"), borderwidth=0,
                        focuscolor="none", relief="flat", padding=(16, 8))
        style.map("Orange.TButton", background=[("active", "#E68A00")])
        style.configure("Icon.TButton", background=bg_card, foreground=fg_primary,
                        font=(font_family, 12), borderwidth=0,
                        focuscolor="none", relief="flat", padding=4)
        style.map("Icon.TButton", background=[("active", "#E8E8ED")])

        # ── Treeview ──
        style.configure("Treeview", background=bg_card, foreground=fg_primary,
                        fieldbackground=bg_card, bordercolor=border_color,
                        relief="solid", borderwidth=1, rowheight=28,
                        font=(font_family, 9))
        style.configure("Treeview.Heading", background="#F5F5F7", foreground=fg_primary,
                        font=(font_family, 9, "bold"), relief="flat", borderwidth=0)
        style.map("Treeview", background=[("selected", accent_blue)],
                  foreground=[("selected", "white")])

        # ── Progressbar ──
        style.configure("TProgressbar", background=accent_blue, troughcolor="#E8E8ED",
                        bordercolor=border_color, relief="flat", borderwidth=0)

        # ── Scrollbar ──
        style.configure("Vertical.TScrollbar", background="#E8E8ED",
                        arrowcolor=fg_primary, relief="flat", borderwidth=0)

        # ── Main Layout ──
        main = ttk.Frame(self.root, style="Window.TFrame")
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        sidebar = ttk.Frame(main, style="Window.TFrame", width=280)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        sidebar.pack_propagate(False)

        right = ttk.Frame(main, style="Window.TFrame")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Helper ──
        def labeled_row(parent, label, width=6):
            r = ttk.Frame(parent)
            r.pack(fill=tk.X, pady=3)
            ttk.Label(r, text=label, width=width, style="Secondary.TLabel",
                      anchor=tk.W).pack(side=tk.LEFT)
            return r

        # ── 串口设置 ──
        card1 = ttk.LabelFrame(sidebar, text="串口设置", style="Card.TLabelframe", padding=10)
        card1.pack(fill=tk.X, pady=(0, 8))

        r = labeled_row(card1, "端口", 5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(r, textvariable=self.port_var,
                                        state="readonly", font=(font_family, 9))
        self.port_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(r, text="↻", width=3, style="Icon.TButton",
                   command=self._refresh_ports).pack(side=tk.LEFT)

        r = labeled_row(card1, "波特率", 5)
        self.baud_var = tk.StringVar(value="9600")
        ttk.Combobox(r, textvariable=self.baud_var,
                      values=["9600", "19200", "38400"],
                      state="readonly", font=(font_family, 9), width=12).pack(side=tk.LEFT)

        self.btn_connect = ttk.Button(card1, text="连接串口",
                                       command=self._toggle_connection,
                                       style="Blue.TButton")
        self.btn_connect.pack(fill=tk.X, pady=(8, 0), ipady=1)

        # ── 采集设置 ──
        card3 = ttk.LabelFrame(sidebar, text="采集设置", style="Card.TLabelframe", padding=10)
        card3.pack(fill=tk.X, pady=(0, 8))

        r = labeled_row(card3, "采样数")
        self.count_var = tk.StringVar(value="10")
        ttk.Entry(r, textvariable=self.count_var,
                  font=(font_family, 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(r, text="−", width=2, style="Icon.TButton",
                   command=lambda: self._adjust_value("count", -self._get_acq_step())).pack(side=tk.LEFT, padx=1)
        ttk.Button(r, text="＋", width=2, style="Icon.TButton",
                   command=lambda: self._adjust_value("count", self._get_acq_step())).pack(side=tk.LEFT, padx=1)

        r = labeled_row(card3, "间隔 ms")
        self.interval_var = tk.StringVar(value="300")
        ttk.Entry(r, textvariable=self.interval_var,
                  font=(font_family, 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(r, text="−", width=2, style="Icon.TButton",
                   command=lambda: self._adjust_value("interval", -self._get_acq_step())).pack(side=tk.LEFT, padx=1)
        ttk.Button(r, text="＋", width=2, style="Icon.TButton",
                   command=lambda: self._adjust_value("interval", self._get_acq_step())).pack(side=tk.LEFT, padx=1)

        r = labeled_row(card3, "跨度")
        self.step_acq_var = tk.StringVar(value="10")
        ttk.Entry(r, textvariable=self.step_acq_var, width=8,
                  font=(font_family, 9)).pack(side=tk.LEFT)

        r = labeled_row(card3, "离群值")
        self.outlier_var = tk.StringVar(value="remove")
        ttk.Combobox(r, textvariable=self.outlier_var,
                      values=["none", "mark", "remove"],
                      state="readonly", font=(font_family, 9), width=12).pack(side=tk.LEFT)

        # ── 测量参数 ──
        card2 = ttk.LabelFrame(sidebar, text="测量参数", style="Card.TLabelframe", padding=10)
        card2.pack(fill=tk.X, pady=(0, 8))

        r = labeled_row(card2, "温度")
        self.temp_var = tk.StringVar(value="20degC")
        ttk.Entry(r, textvariable=self.temp_var,
                  font=(font_family, 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(r, text="−", width=2, style="Icon.TButton",
                   command=lambda: self._adjust_value("temp", -self._get_step())).pack(side=tk.LEFT, padx=1)
        ttk.Button(r, text="＋", width=2, style="Icon.TButton",
                   command=lambda: self._adjust_value("temp", self._get_step())).pack(side=tk.LEFT, padx=1)

        r = labeled_row(card2, "频率")
        self.freq_var = tk.StringVar(value="100kHz")
        ttk.Entry(r, textvariable=self.freq_var,
                  font=(font_family, 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(r, text="−", width=2, style="Icon.TButton",
                   command=lambda: self._adjust_value("freq", -self._get_step())).pack(side=tk.LEFT, padx=1)
        ttk.Button(r, text="＋", width=2, style="Icon.TButton",
                   command=lambda: self._adjust_value("freq", self._get_step())).pack(side=tk.LEFT, padx=1)

        r = labeled_row(card2, "跨度")
        self.step_var = tk.StringVar(value="10")
        ttk.Entry(r, textvariable=self.step_var, width=8,
                  font=(font_family, 9)).pack(side=tk.LEFT)

        # ── 数据操作 ──
        card4 = ttk.LabelFrame(sidebar, text="数据操作", style="Card.TLabelframe", padding=10)
        card4.pack(fill=tk.X, pady=(0, 8))

        self.btn_acquire = ttk.Button(card4, text="开始采集",
                                       command=self._toggle_acquisition,
                                       state=tk.DISABLED,
                                       style="Green.TButton")
        self.btn_acquire.pack(fill=tk.X, pady=(0, 6), ipady=3)

        self.btn_save = ttk.Button(card4, text="保存数据",
                                    command=self._save_data,
                                    state=tk.DISABLED,
                                    style="Orange.TButton")
        self.btn_save.pack(fill=tk.X, pady=(0, 6), ipady=1)

        r = labeled_row(card4, "数据文件", 7)
        self.title_var = tk.StringVar(value="")
        ttk.Entry(r, textvariable=self.title_var,
                  font=(font_family, 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── 状态栏 ──
        status_frame = ttk.Frame(right, style="Window.TFrame")
        status_frame.pack(fill=tk.X, pady=(0, 8))

        self.status_label = ttk.Label(status_frame, text="○ 未连接",
                                       style="Secondary.TLabel",
                                       font=(font_family, 10))
        self.status_label.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(status_frame, length=200, mode="determinate")
        self.progress.pack(side=tk.LEFT, padx=12, fill=tk.X, expand=True)

        self.progress_label = ttk.Label(status_frame, text="0 / 0",
                                         style="Secondary.TLabel",
                                         font=(font_family, 10))
        self.progress_label.pack(side=tk.RIGHT)

        # ── 数据表格 ──
        table_frame = ttk.Frame(right, style="Window.TFrame")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols = ("index", "cs", "d", "timestamp")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                  selectmode="extended", style="Treeview")

        self.tree.heading("index", text="#")
        self.tree.heading("cs", text="C (F)")
        self.tree.heading("d", text="D")
        self.tree.heading("timestamp", text="时间戳")
        self.tree.column("index", width=45, anchor=tk.CENTER, stretch=False)
        self.tree.column("cs", width=140, anchor=tk.E)
        self.tree.column("d", width=140, anchor=tk.E)
        self.tree.column("timestamp", width=160, anchor=tk.CENTER)

        sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                            command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("outlier", background="#FFF0F0", foreground="#FF3B30")

        # ── 记录工具栏 ──
        record_bar = ttk.Frame(right, style="Window.TFrame")
        record_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(record_bar, text="记录文件", style="Secondary.TLabel",
                  font=(font_family, 9)).pack(side=tk.LEFT, padx=(0, 6))
        self.record_var = tk.StringVar(value="")
        ttk.Entry(record_bar, textvariable=self.record_var,
                  font=(font_family, 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.btn_record = ttk.Button(record_bar, text="记录",
                                      command=self._record_average,
                                      state=tk.DISABLED,
                                      style="Orange.TButton")
        self.btn_record.pack(side=tk.LEFT, ipady=1, padx=(0, 6))
        self.btn_plot = ttk.Button(record_bar, text="绘制",
                                    command=self._plot_record,
                                    state=tk.NORMAL,
                                    style="Blue.TButton")
        self.btn_plot.pack(side=tk.LEFT, ipady=1)

        # ── 日志 ──
        lf = ttk.LabelFrame(right, text="日志", style="Card.TLabelframe", padding=8)
        lf.pack(fill=tk.X)

        self.log_text = tk.Text(lf, height=6, font=(font_family, 9), state=tk.DISABLED,
                                bg=bg_card, fg=fg_primary, insertbackground=fg_primary,
                                relief=tk.FLAT, borderwidth=0, padx=6, pady=4)
        ls = ttk.Scrollbar(lf, orient=tk.VERTICAL,
                            command=self.log_text.yview, style="Vertical.TScrollbar")
        self.log_text.configure(yscrollcommand=ls.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ls.pack(side=tk.RIGHT, fill=tk.Y)

    # ── 同步文件名 ───────────────────────────────────────────

    def _sync_filename(self):
        """将测量参数同步到文件名输入框"""
        self.title_var.set(f"{self.temp_var.get()}_{self.freq_var.get()}")

    def _sync_record_filename(self):
        """将测量参数同步到记录文件名输入框"""
        if self.record_var.get().strip():
            return  # 框里有内容，不动
        self.record_var.set("")

    # ── 数值微调 ─────────────────────────────────────────────

    def _get_step(self) -> float:
        try:
            return float(self.step_var.get())
        except ValueError:
            return 10.0

    def _get_acq_step(self) -> float:
        try:
            return float(self.step_acq_var.get())
        except ValueError:
            return 10.0

    def _adjust_value(self, field: str, delta: float):
        if field == "count":
            var = self.count_var
        elif field == "interval":
            var = self.interval_var
        elif field == "freq":
            var = self.freq_var
        else:
            var = self.temp_var
        current = var.get()
        m = re.match(r"([\d.]+)(.*)", current)
        if not m:
            return
        num_str, suffix = m.group(1), m.group(2)
        try:
            num = float(num_str)
        except ValueError:
            return
        num = max(0, num + delta)
        # 保持整数/小数格式与原值一致
        new_val = f"{int(num)}{suffix}" if "." not in num_str else f"{num}{suffix}"
        var.set(new_val)

    # ── 日志 ─────────────────────────────────────────────────

    def _log(self, msg: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        # 颜色标签
        self.log_text.tag_configure("info", foreground="#FF9F0A")
        self.log_text.tag_configure("tx", foreground="#007AFF")
        self.log_text.tag_configure("rx", foreground="#34C759")
        self.log_text.tag_configure("err", foreground="#FF3B30")

    # ── UI 队列轮询 ──────────────────────────────────────────

    def _poll_ui_queue(self):
        while not self.ui_queue.empty():
            action, data = self.ui_queue.get_nowait()
            if action == "log":
                self._log(data["msg"], data.get("type", "info"))
            elif action == "add_row":
                self._add_table_row(data)
            elif action == "progress":
                self.progress["value"] = data["pct"]
                self.progress_label.config(text=f"{data['current']} / {data['total']}")
            elif action == "acq_done":
                self._on_acquisition_done(data)
        self.root.after(100, self._poll_ui_queue)

    # ── 串口枚举 ─────────────────────────────────────────────

    def _refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [f"{p.device} - {p.description}" for p in ports]
        self.port_combo["values"] = port_list
        self._port_objects = {f"{p.device} - {p.description}": p.device for p in ports}
        if port_list:
            self.port_combo.current(0)
            self._log(f"检测到 {len(port_list)} 个串口: {', '.join(p.device for p in ports)}")
        else:
            self.port_var.set("")
            self._log("未检测到串口设备，请检查连接", "err")

    # ── 连接/断开 ────────────────────────────────────────────

    def _toggle_connection(self):
        if self.is_connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port_desc = self.port_var.get()
        if not port_desc or port_desc not in self._port_objects:
            messagebox.showwarning("提示", "请先选择串口")
            return

        device = self._port_objects[port_desc]
        baud = int(self.baud_var.get())

        try:
            self.serial_port = serial.Serial(
                port=device, baudrate=baud, bytesize=8, parity="N",
                stopbits=1, timeout=1,
            )
            # DTR/RTS：PySerial 不支持在 __init__ 中设置，需创建后单独设
            self.serial_port.dtr = True
            self.serial_port.rts = True
            # 等待设备就绪（参考 LabVIEW VISA 的初始化行为）
            time.sleep(0.5)
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()

            self.is_connected = True
            self.btn_connect.config(text="断开连接")
            self.status_label.config(text=f"● 已连接 ({device})", foreground="#34C759")
            self.btn_acquire.config(state=tk.NORMAL)
            self._log(f"串口已连接: {device} @ {baud}bps")
        except Exception as e:
            self._log(f"连接失败: {e}", "err")

    def _disconnect(self):
        self.stop_event.set()
        self.is_acquiring = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.serial_port = None
        self.is_connected = False
        self.btn_connect.config(text="连接串口", style="Blue.TButton")
        self.status_label.config(text="○ 未连接", foreground="#86868B")
        self.btn_acquire.config(state=tk.DISABLED)
        self._log("串口已断开")

    # ── TH2817B 协议 ─────────────────────────────────────────

    def _send_byte(self, b: int, delay_after: float = 0):
        """发送单字节，可选发送后延迟（毫秒）"""
        self.serial_port.write(bytes([b]))
        if delay_after:
            time.sleep(delay_after)

    def _read_byte(self, timeout: float = 0.05) -> int | None:
        old_timeout = self.serial_port.timeout
        self.serial_port.timeout = timeout
        try:
            data = self.serial_port.read(1)
            return data[0] if data else None
        finally:
            self.serial_port.timeout = old_timeout

    def _flush_input(self):
        """清空串口输入缓冲区（参考 C 代码 handshake 前的 while read）"""
        self.serial_port.reset_input_buffer()

    def _handshake(self) -> bool:
        """
        握手：发送 0xAA，期望收到 0xCC。
        设备在连续发送数据时可能不响应握手，所以只试几次就放弃。
        """
        self._flush_input()
        for i in range(15):
            if self.stop_event.is_set():
                return False
            self._send_byte(0xAA, delay_after=0.002)
            result = self._read_byte(0.1)
            if result == 0xCC:
                return True
        return False

    def _send_command(self, cmd: str):
        """逐字节发送命令，每字节间延迟 2ms（匹配 C 代码 delay(2)）"""
        for ch in cmd:
            self._send_byte(ord(ch), delay_after=0.002)
        self._send_byte(ord("\n"), delay_after=0.002)
        self.ui_queue.put(("log", {"msg": f"TX: {cmd}", "type": "tx"}))

    def _read_string(self, timeout: float = 2.0) -> str:
        """
        读一行数据（以 \n 结尾），跳过 0xCC 字节。
        如果超时且已有部分数据，直接返回。
        """
        buf = ""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self.stop_event.is_set():
                if buf:
                    return buf
                raise TimeoutError("用户中断")
            old_timeout = self.serial_port.timeout
            self.serial_port.timeout = 0.2
            try:
                data = self.serial_port.read(1)
            finally:
                self.serial_port.timeout = old_timeout
            if data:
                b = data[0]
                if b == 0xCC:
                    continue
                ch = chr(b)
                if ch == "\n":
                    return buf
                buf += ch
        if buf:
            return buf
        raise TimeoutError("读取超时")

    def _send_and_read(self, cmd: str) -> str:
        if not self._handshake():
            raise ConnectionError("握手失败：设备未响应 0xCC")
        self._send_command(cmd)
        return self._read_string()

    # ── 应用参数 ─────────────────────────────────────────────

    def _apply_settings(self):
        """
        尝试配置仪器参数。
        如果设备在连续发送数据，握手可能失败，
        此时跳过配置（设备保持当前参数）。
        """
        if not self.is_connected:
            self._log("请先连接串口", "err")
            return

        def _do():
            self.ui_queue.put(("log", {"msg": "正在尝试配置仪器参数（如设备连续输出中可能跳过）...", "type": "info"}))
            cmds = [
                "trigsour bus;trg",
                "funcimpapar cs;bpar d",
            ]

            ok = 0
            for cmd in cmds:
                if self.stop_event.is_set():
                    return
                try:
                    resp = self._send_and_read(cmd)
                    ok += 1
                    self.ui_queue.put(("log", {"msg": f"配置成功: {cmd} → {resp}", "type": "rx"}))
                    time.sleep(0.1)
                except Exception:
                    self.ui_queue.put(("log", {"msg": f"配置跳过: {cmd}（设备未响应握手）", "type": "err"}))
                    # 继续尝试下一条

            if ok == 0:
                self.ui_queue.put(("log", {"msg": "所有配置均失败（设备可能处于连续输出模式，参数保留当前值）", "type": "info"}))
            else:
                self.ui_queue.put(("log", {"msg": f"成功配置 {ok}/{len(cmds)} 项参数", "type": "info"}))

        threading.Thread(target=_do, daemon=True).start()

    # ── 保存数据 ─────────────────────────────────────────────

    def _save_data(self):
        if not self.collected_data:
            messagebox.showwarning("提示", "没有数据可保存，请先采集")
            return
        # 根据离群值设置过滤
        outliers, clean = self._mark_and_filter_outliers()
        mode = self.outlier_var.get()
        data_to_save = clean if mode == "remove" else self.collected_data

        title = self.title_var.get().strip() or "电容数据"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"{title}_{ts}.csv"
        )
        if not path:
            return
        self.save_path = path
        self._save_to_txt(data_to_save)

    # ── 数据采集 ─────────────────────────────────────────────

    def _toggle_acquisition(self):
        if self.is_acquiring:
            self._stop_acquisition()
        else:
            self._start_acquisition()

    def _stop_acquisition(self):
        self.stop_event.set()
        self.is_acquiring = False
        self.btn_acquire.config(text="开始采集", style="Green.TButton")
        self.btn_acquire.config(state=tk.NORMAL)
        self.btn_connect.config(state=tk.NORMAL)
        self.status_label.config(text=f"● 已连接", foreground="#34C759")
        self._log("采集已停止")

    def _start_acquisition(self):
        if not self.is_connected or self.is_acquiring:
            return
        self.is_acquiring = True
        self.stop_event.clear()
        self.collected_data = []
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.btn_acquire.config(text="停止采集", style="Red.TButton", state=tk.NORMAL)
        self.btn_connect.config(state=tk.DISABLED)
        self.status_label.config(text="● 采集中...", foreground="#FF9F0A")

        count = int(self.count_var.get())
        interval = int(self.interval_var.get())

        threading.Thread(target=self._acquisition_loop, args=(count, interval), daemon=True).start()

    def _read_line_from_stream(self) -> str | None:
        """
        从设备连续数据流中读取一行。
        不清空缓冲区（避免丢弃设备已发数据），
        每次最多等 0.3s，读到 \n 就返回。
        """
        buf = b""
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            if self.stop_event.is_set():
                return None
            old_to = self.serial_port.timeout
            self.serial_port.timeout = 0.05
            try:
                chunk = self.serial_port.read(256)
            finally:
                self.serial_port.timeout = old_to
            if not chunk:
                continue
            buf += chunk
            if b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = bytes(b for b in line if b != 0xCC)
                line = line.rstrip(b"\r")
                if line:
                    return line.decode("ascii", errors="replace")
        # 超时：拿手里有的
        if buf:
            line = bytes(b for b in buf if b != 0xCC)
            line = line.rstrip(b"\r\n")
            if line:
                return line.decode("ascii", errors="replace")
        return None

    def _acquisition_loop(self, count: int, interval: int):
        """
        采集主循环。
        设备连续发送数据 → 直接读取解析，不握手不发送触发。
        """
        self.ui_queue.put(("log", {"msg": f"开始采集: {count} 个采样, 间隔 {interval}ms", "type": "info"}))
        self.ui_queue.put(("log", {"msg": "设备连续输出模式: 直接读取数据流...", "type": "info"}))

        # 先读空缓冲区，避免拿到旧数据
        self.serial_port.reset_input_buffer()
        # 等设备吐出第一条完整数据的时间
        time.sleep(0.1)
        self.serial_port.reset_input_buffer()

        success = 0
        i = 0
        while i < count:
            if self.stop_event.is_set():
                break
            try:
                line = self._read_line_from_stream()
                if line is None:
                    self.ui_queue.put(("log", {"msg": f"第 {i+1} 次读取超时", "type": "err"}))
                    i += 1
                    continue

                # 去除可能的 0xCC 前缀（_read_line_from_stream 已跳过，这里冗余处理）
                line = line.lstrip()
                if not line:
                    continue



                parsed = self._parse_response(line)
                if parsed:
                    success += 1
                    row = {
                        "index": success,
                        "cs": parsed["cs"],
                        "d": parsed["d"],
                        "timestamp": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                    }
                    self.collected_data.append(row)
                    self.ui_queue.put(("add_row", row))
                else:
                    self.ui_queue.put(("log", {"msg": f"第 {i+1} 行解析失败: {line}", "type": "err"}))

                pct = round((i + 1) / count * 100)
                self.ui_queue.put(("progress", {"pct": pct, "current": i + 1, "total": count}))
                i += 1

                if i < count and not self.stop_event.is_set():
                    time.sleep(interval / 1000.0)
            except Exception as e:
                self.ui_queue.put(("log", {"msg": f"采样错误: {e}", "type": "err"}))
                if not self.is_connected or self.stop_event.is_set():
                    break
                i += 1

        self._acquisition_cleanup()
        self.ui_queue.put(("acq_done", {"success": success, "total": count}))

    def _acquisition_cleanup(self):
        self.is_acquiring = False
        self.btn_acquire.config(text="开始采集", style="Green.TButton", state=tk.NORMAL if self.is_connected else tk.DISABLED)
        self.btn_save.config(state=tk.NORMAL if self.collected_data else tk.DISABLED)
        self.btn_record.config(state=tk.NORMAL if self.collected_data else tk.DISABLED)
        self.btn_connect.config(state=tk.NORMAL)
        if not self.stop_event.is_set():
            self.status_label.config(text=f"● 已连接", foreground="#34C759")

    def _on_acquisition_done(self, data: dict):
        self._log(f"采集完成: 成功 {data['success']}/{data['total']}")
        if self.collected_data:
            outliers, _ = self._mark_and_filter_outliers()
            if outliers:
                self._log(f"检测到 {len(outliers)} 个离群值，可在保存时不保留")

    # ── 响应解析 ─────────────────────────────────────────────

    @staticmethod
    def _parse_response(response: str) -> dict | None:
        if not response or response.startswith("E"):
            return None
        line = response.strip()
        if not line:
            return None

        # 尝试按数字提取：找至少两个连续数字
        nums = re.findall(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', line)
        if len(nums) >= 2:
            try:
                cs = float(nums[0])
                d = float(nums[1])
                return {"cs": cs, "d": d}
            except ValueError:
                pass
        return None

    # ── 离群值检测 ───────────────────────────────────────────

    @staticmethod
    def _detect_outliers_iqr(data: list[float]) -> tuple[float, float]:
        if len(data) < 4:
            return float("-inf"), float("inf")
        sorted_d = sorted(data)
        q1 = sorted_d[len(sorted_d) // 4]
        q3 = sorted_d[len(sorted_d) * 3 // 4]
        iqr = q3 - q1
        return q1 - 1.5 * iqr, q3 + 1.5 * iqr

    def _mark_and_filter_outliers(self) -> tuple[list[int], list[dict]]:
        mode = self.outlier_var.get()
        if mode == "none" or len(self.collected_data) < 4:
            return [], self.collected_data

        cs_vals = [d["cs"] for d in self.collected_data]
        d_vals = [d["d"] for d in self.collected_data]
        cs_lo, cs_hi = self._detect_outliers_iqr(cs_vals)
        d_lo, d_hi = self._detect_outliers_iqr(d_vals)

        outlier_indices = set()
        for i, row in enumerate(self.collected_data):
            if row["cs"] < cs_lo or row["cs"] > cs_hi or row["d"] < d_lo or row["d"] > d_hi:
                outlier_indices.add(i)

        # 标记表格行
        items = self.tree.get_children()
        for i, item in enumerate(items):
            if i in outlier_indices:
                self.tree.item(item, tags=("outlier",))
            else:
                self.tree.item(item, tags=())

        clean = [row for i, row in enumerate(self.collected_data) if i not in outlier_indices]

        if outlier_indices:
            self._log(f"离群值检测: Cs 范围 [{cs_lo:.3e}, {cs_hi:.3e}], D 范围 [{d_lo:.3e}, {d_hi:.3e}]")
            label = "已剔除" if mode == "remove" else "已标记"
            self._log(f"发现 {len(outlier_indices)} 个离群值 ({label})")
        else:
            self._log("未发现离群值")

        return list(outlier_indices), clean

    # ── 表格行 ───────────────────────────────────────────────

    def _add_table_row(self, row: dict):
        item = self.tree.insert("", tk.END, values=(
            row["index"],
            f"{row['cs']:.6e}",
            f"{row['d']:.6e}",
            row["timestamp"],
        ))
        # 每 20 条滚动一次到底部，避免逐条滚动拖慢 UI
        if row["index"] % 20 == 0:
            self.tree.see(item)

    # ── 记录平均值 ───────────────────────────────────────────

    def _record_average(self):
        """将表格选中行的平均值记录到 CSV 文件"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先在表格中用 Ctrl+点击 / Shift+点击 选择数据行")
            return

        cs_vals, d_vals = [], []
        for item_id in selection:
            values = self.tree.item(item_id, "values")
            try:
                cs_vals.append(float(values[1]))
                d_vals.append(float(values[2]))
            except (ValueError, IndexError):
                continue

        if not cs_vals:
            messagebox.showwarning("提示", "未能提取选中行的数据")
            return

        avg_cs = sum(cs_vals) / len(cs_vals)
        avg_d = sum(d_vals) / len(d_vals)

        # 读取文本框中的路径，为空则弹窗创建
        path = self.record_var.get().strip()
        if not path or not Path(path).exists():
            ts = datetime.now().strftime("%Y%m%d")
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV 文件", "*.csv")],
                initialfile=f"{ts}.csv"
            )
            if not path:
                return
            self.record_path = path
            self.record_var.set(path)

        try:
            file_exists = Path(path).exists()
            with open(path, "a", encoding="utf-8-sig", newline="") as f:
                if not file_exists:
                    f.write("温度,频率,平均C(F),平均D,样本数,时间戳\n")
                f.write(f"{self.temp_var.get()},{self.freq_var.get()},{avg_cs:.6e},{avg_d:.6e},{len(cs_vals)},{datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n")
            self._log(f"已记录: {Path(path).name} ({len(cs_vals)} 行, avg C={avg_cs:.6e})")
        except Exception as e:
            self._log(f"记录失败: {e}", "err")

    # ── 绘制 C-T 曲线 ────────────────────────────────────────

    def _plot_record(self):
        """读取记录 CSV 并绘制 C-T 曲线"""
        path = self.record_var.get().strip()
        if not path or not Path(path).exists():
            path = filedialog.askopenfilename(
                filetypes=[("CSV 文件", "*.csv")],
                title="选择记录文件"
            )
            if not path:
                return

        groups: dict[float, list[tuple[float, float, str]]] = defaultdict(list)
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    temp_str = row.get("温度", "")
                    freq_str = row.get("频率", "")
                    cs_str = row.get("平均C(F)", "")
                    if not temp_str or not freq_str or not cs_str:
                        continue
                    tm = re.match(r"([\d.]+)", temp_str)
                    fm = re.match(r"([\d.]+)", freq_str)
                    if not tm or not fm:
                        continue
                    try:
                        temp = float(tm.group(1))
                        freq = float(fm.group(1))
                        cs = float(cs_str) * 1e12
                    except ValueError:
                        continue
                    groups[freq].append((temp, cs, freq_str.strip()))
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {e}")
            return

        if not groups:
            messagebox.showwarning("提示", "文件中没有可绘制的数据")
            return

        fig, ax = plt.subplots(figsize=(8, 5))
        for freq_num, points in sorted(groups.items()):
            points.sort(key=lambda p: p[0])
            temps = [p[0] for p in points]
            css = [p[1] for p in points]
            label = points[0][2]  # 原始频率字符串
            ax.plot(temps, css, marker="o", label=label)

        ax.set_xlabel("温度 (degC)")
        ax.set_ylabel("电容 C (pF)")
        ax.set_title(f"C-T 曲线 — {Path(path).stem}")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        # 嵌入到独立 tkinter 窗口（无 Subplots 按钮）
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        top = tk.Toplevel(self.root)
        top.title(f"C-T 曲线 — {Path(path).stem}")
        top.geometry("900x650")

        canvas = FigureCanvasTkAgg(fig, master=top)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar_frame = tk.Frame(top)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        _saved = NavigationToolbar2Tk.toolitems
        NavigationToolbar2Tk.toolitems = [t for t in _saved if t[0] != "Subplots"]
        try:
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            toolbar.update()
            toolbar.pack()
        finally:
            NavigationToolbar2Tk.toolitems = _saved

    # ── CSV 导出 ───────────────────────────────────────────

    def _save_to_txt(self, data: list[dict]):
        try:
            with open(self.save_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write("序号,C(F),D,时间戳\n")
                for row in data:
                    f.write(f"{row['index']},{row['cs']:.6e},{row['d']:.6e},{row['timestamp']}\n")
            self._log(f"数据已保存: {Path(self.save_path).name} ({len(data)} 条)")
        except Exception as e:
            self._log(f"保存失败: {e}", "err")
            try:
                fallback = Path.home() / f"capacitor_data_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"
                with open(fallback, "w", encoding="utf-8-sig", newline="") as f:
                    f.write("序号,C(F),D,时间戳\n")
                    for row in data:
                        f.write(f"{row['index']},{row['cs']:.6e},{row['d']:.6e},{row['timestamp']}\n")
                self._log(f"已保存到: {fallback}")
            except Exception as e2:
                self._log(f"回退保存也失败: {e2}", "err")


def main():
    root = tk.Tk()
    app = TH2817BApp(root)

    # 快捷键
    root.bind("<space>", lambda e: app._start_acquisition() if app.is_connected and not app.is_acquiring else None)

    # 关闭时清理
    def on_close():
        app.stop_event.set()
        if app.serial_port and app.serial_port.is_open:
            app.serial_port.close()
        plt.close("all")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
