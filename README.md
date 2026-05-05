# TxTime Calculator

Wi-Fi 空中传输时间（TxTime）计算工具，基于 IEEE 802.11n/ac/ax 标准。

## 支持的模式

| 模式 | 标准 | MCS 范围 | 带宽 |
|------|------|----------|------|
| HT | 802.11n | 0-7 | 20/40 MHz |
| VHT | 802.11ac | 0-9 | 20/40/80/160 MHz |
| HE | 802.11ax | 0-11 | 20/40/80/160 MHz |

## 计算公式

```
Nsym = m_STBC × ceil((8×LENGTH + 16 + 6×N_ES) / N_DBPS)
TxTime = Preamble + Nsym × Tsym + Midamble + PE + SignalExtension
```

## 使用方法

### 命令行版本

```bash
# HT 20MHz MCS7 1流 1500字节
python3 ttc_calculator.py --mode HT --mcs 7 --bw 20 --streams 1 --length 1500

# VHT 80MHz MCS9 4流 短GI
python3 ttc_calculator.py --mode VHT --mcs 9 --bw 80 --streams 4 --length 1500 --gi short

# HE 80MHz MCS11 4流 多普勒+包扩展
python3 ttc_calculator.py --mode HE --mcs 11 --bw 80 --streams 4 --length 1500 --he-doppler --he-pe 2
```

### GUI 版本

```bash
python3 ttc_gui.py
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `--mode` | PHY 模式：HT/VHT/HE |
| `--mcs` | MCS 索引 |
| `--bw` | 带宽 MHz |
| `--streams` | 空间流数 |
| `--length` | 帧长度（字节） |
| `--gi` | GI 类型：normal/short |
| `--stbc` | 启用 STBC |
| `--ldpc` | 使用 LDPC 编码 |
| `--freq` | 频段 GHz（2/5） |
| `--he-doppler` | HE 多普勒模式 |
| `--he-pe` | HE 包扩展（0-3） |

## 依赖

- Python 3.7+
- tkinter（GUI 版本，通常随 Python 自带）
