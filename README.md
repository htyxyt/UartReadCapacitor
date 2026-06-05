# TH2817B 电容数据采集助手

基于 Python/Tkinter 的桌面应用，通过串口 (UART) 连接 **TH2817B LCR 测试仪**，实现电容 (C) 和损耗因子 (D) 的自动采集、实时显示与 CSV 导出。

## 功能

- 串口自动枚举 & 连接（9600/19200/38400 bps）
- 仪器参数配置（频率、电压、测量速度）
- 批量数据采集，可设置采样数和间隔
- 实时数据表格显示 + 离群值检测 (IQR)
- 采集结果导出 CSV

## 环境要求

- **Python** >= 3.10
- **操作系统**：Windows 10/11
- **包管理器**：[uv](https://docs.astral.sh/uv/)（推荐）或 pip

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/wesky95/UartReadCapacitor.git
cd UartReadCapacitor
```

### 2. 安装依赖

```bash
uv sync
```

或使用 pip：

```bash
pip install pyserial openpyxl pyinstaller
```

### 3. 运行

```bash
uv run python app.py
```

或直接：

```bash
python app.py
```

### 4. 连接设备

1. 通过串口线连接 TH2817B 仪器
2. 在应用中选择对应串口和波特率（默认 9600）
3. 点击 **连接串口**
4. 设置测量参数（频率、电压、速度），点击 **应用参数**
5. 设置采样数和间隔，点击 **开始采集**

## 打包为独立 EXE

```bash
uv run pyinstaller --onefile --windowed --name "TH2817B采集助手" app.py
```

或直接运行构建脚本：

```bash
build.bat
```

输出文件：`dist/TH2817B采集助手.exe`

## 通信协议

TH2817B 使用自定义串口协议：

| 步骤 | 方向 | 字节 | 说明 |
|------|------|------|------|
| 握手 | PC → 设备 | `0xAA` | 发送握手请求 |
| 握手 | 设备 → PC | `0xCC` | 握手应答 |
| 命令 | PC → 设备 | ASCII + `\n` | 发送 SCPI 风格指令 |
| 数据 | 设备 → PC | ASCII + `\n` | 返回测量结果 |

常用指令：

| 指令 | 说明 |
|------|------|
| `freq 10khz` | 设置频率 |
| `voltagelevel 0.3v` | 设置电压 |
| `funcimpapar cs;bpar d` | 设置测量参数 (Cs + D) |
| `speed med` | 测量速度 (fast/med/slow) |
| `trigsour bus;trg` | 触发模式设置为 BUS |

参考实现见 `demo.c`（原始 DOS 下的 C 语言代码）。

## 项目结构

```
├── app.py              # 主程序（Tkinter GUI）
├── demo.c              # C 语言参考实现（DOS 串口通信）
├── build.bat           # 构建脚本
├── pyproject.toml      # 项目配置 & 依赖
├── uv.lock             # 依赖锁定文件
└── dist/
    └── TH2817B采集助手.exe   # 打包好的可执行文件
```

## 许可

MIT License
