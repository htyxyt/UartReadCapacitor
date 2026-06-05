# TH2817B 电容数据采集助手

基于 Python/Tkinter 的桌面应用，通过串口 (UART) 连接 **TH2817B LCR 测试仪**，实现电容 (C) 和损耗因子 (D) 的自动采集、实时显示、CSV 导出，以及 C-T 曲线绘制。

## 功能

- 串口自动枚举 & 连接（9600/19200/38400 bps）
- 测量参数设置（频率、温度），支持可调速率的 ± 微调按钮
- 批量数据采集，采样数 / 间隔可调，带独立 ± 微调
- 实时数据表格显示 + IQR 离群值检测
- 多选数据行 → 一键记录平均值到专用 CSV（不同温度/频率追加同一文件）
- 读取记录 CSV 绘制 C-T 曲线（每个频率一条曲线，横轴温度、纵轴电容 pF）
- 采集结果导出 CSV（文件名自动拼温度+频率+时间戳）

## 环境要求

- **Python** >= 3.10
- **操作系统**：Windows 10/11
- **包管理器**：[uv](https://docs.astral.sh/uv/)

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/htyxyt/UartReadCapacitor.git
cd UartReadCapacitor
```

### 2. 安装依赖

```bash
uv sync
```

### 3. 运行

```bash
uv run python app.py
```

### 4. 使用流程

1. 串口线连接 TH2817B，选择端口和波特率，点击 **连接串口**
2. 设置采集参数（采样数、间隔、离群值处理方式）
3. 设置温度和频率（可用微调按钮或手动输入），跨度控制步长
4. 点击 **开始采集** → 数据实时显示在表格中
5. 采集完成后可 **保存数据** 为 CSV
6. 在表格中 Ctrl/Shift 多选数据行 → 点 **记录** 将平均值追加到记录文件
7. 积累多组记录后点 **绘制** 查看 C-T 曲线

## 打包为独立 EXE

```bash
uv run pyinstaller --onefile --windowed --name "TH2817B采集助手" app.py
```

或运行构建脚本：

```bash
build.bat
```

输出：`dist/TH2817B采集助手.exe`

## 通信协议

TH2817B 使用自定义串口协议：

| 步骤 | 方向 | 字节 | 说明 |
|------|------|------|------|
| 握手 | PC → 设备 | `0xAA` | 发送握手请求 |
| 握手 | 设备 → PC | `0xCC` | 握手应答 |
| 命令 | PC → 设备 | ASCII + `\n` | SCPI 风格指令 |
| 数据 | 设备 → PC | ASCII + `\n` | 连续测量数据流 |

应用仅发送 `trigsour bus;trg` 和 `funcimpapar cs;bpar d` 两条指令，频率/电压/速度在仪器面板上设置。

参考实现见 `demo.c`。

## 项目结构

```
├── app.py              # 主程序（Tkinter GUI）
├── demo.c              # C 语言参考实现
├── build.bat           # 构建脚本
├── pyproject.toml      # 项目配置
├── uv.lock             # 依赖锁
└── README.md
```

## 许可

MIT License
