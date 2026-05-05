#!/usr/bin/env python3
"""
TxTime Calculator GUI - 带界面的HT/VHT/HE帧空中传输时间计算工具
基于tkinter实现
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple


class PhyMode(Enum):
    HT = "HT"
    VHT = "VHT"
    HE = "HE"


class GiType(Enum):
    NORMAL = "normal"
    SHORT = "short"


@dataclass
class TTCParams:
    phy_mode: PhyMode
    mcs: int
    bandwidth: int
    num_streams: int
    frame_length: int
    gi: GiType = GiType.NORMAL
    stbc: bool = False
    ldpc: bool = False
    he_doppler: bool = False
    he_pe_duration: int = 0
    frequency_band: int = 5


class TTCTables:
    @staticmethod
    def get_n_dbps_ht(bandwidth: int, mcs: int, streams: int) -> int:
        ht20_mcs_dbps = {0: 26, 1: 52, 2: 78, 3: 104, 4: 156, 5: 208, 6: 234, 7: 260}
        ht40_mcs_dbps = {0: 54, 1: 108, 2: 162, 3: 216, 4: 324, 5: 432, 6: 486, 7: 540}
        
        if bandwidth == 20:
            return ht20_mcs_dbps[mcs] * streams
        elif bandwidth == 40:
            return ht40_mcs_dbps[mcs] * streams
        return 0
    
    @staticmethod
    def get_n_dbps_vht(bandwidth: int, mcs: int, streams: int) -> int:
        vht20 = {0: 26, 1: 52, 2: 78, 3: 104, 4: 156, 5: 208, 6: 234, 7: 260, 8: 312, 9: 346}
        vht40 = {0: 54, 1: 108, 2: 162, 3: 216, 4: 324, 5: 432, 6: 486, 7: 540, 8: 648, 9: 720}
        vht80 = {0: 117, 1: 234, 2: 351, 3: 468, 4: 702, 5: 936, 6: 1053, 7: 1170, 8: 1404, 9: 1560}
        vht160 = {0: 234, 1: 468, 2: 702, 3: 936, 4: 1404, 5: 1872, 6: 2106, 7: 2340, 8: 2808, 9: 3120}
        
        tables = {20: vht20, 40: vht40, 80: vht80, 160: vht160}
        return tables[bandwidth][mcs] * streams
    
    @staticmethod
    def get_n_dbps_he(bandwidth: int, mcs: int, streams: int) -> int:
        he20 = {0: 24, 1: 48, 2: 72, 3: 96, 4: 144, 5: 192, 6: 216, 7: 240, 8: 288, 9: 320, 10: 360, 11: 384}
        he40 = {0: 48, 1: 96, 2: 144, 3: 192, 4: 288, 5: 384, 6: 432, 7: 480, 8: 576, 9: 640, 10: 720, 11: 768}
        he80 = {0: 102, 1: 204, 2: 306, 3: 408, 4: 612, 5: 816, 6: 918, 7: 1020, 8: 1224, 9: 1360, 10: 1530, 11: 1632}
        he160 = {0: 204, 1: 408, 2: 612, 3: 816, 4: 1224, 5: 1632, 6: 1836, 7: 2040, 8: 2448, 9: 2720, 10: 3060, 11: 3264}
        
        tables = {20: he20, 40: he40, 80: he80, 160: he160}
        return tables[bandwidth][mcs] * streams
    
    @staticmethod
    def get_n_es(n_dbps: int, phy_mode: PhyMode, ldpc: bool) -> int:
        """计算BCC编码器并行数量N_ES
        LDPC: N_ES = 1
        BCC: N_ES = ceil(N_DBPS / N_ES_MAX)
          HT/VHT: N_ES_MAX = 600
          HE: N_ES_MAX = 960
        """
        if ldpc:
            return 1
        if phy_mode in [PhyMode.HT, PhyMode.VHT]:
            return math.ceil(n_dbps / 600)
        else:
            return math.ceil(n_dbps / 960)
    
    @staticmethod
    def get_symbol_duration(phy_mode: PhyMode, gi: GiType, he_gi_us: float = 0.8) -> float:
        if phy_mode == PhyMode.HE:
            return 12.8 + he_gi_us
        else:
            return 4.0 if gi == GiType.NORMAL else 3.6
    
    @staticmethod
    def get_he_gi_value(gi: GiType) -> float:
        return 3.2 if gi == GiType.NORMAL else 0.8


class TTCCalculator:
    def __init__(self, params: TTCParams):
        self.params = params
        self.tables = TTCTables()
    
    def calculate_nsym(self) -> int:
        if self.params.phy_mode == PhyMode.HT:
            n_dbps = self.tables.get_n_dbps_ht(self.params.bandwidth, self.params.mcs, self.params.num_streams)
        elif self.params.phy_mode == PhyMode.VHT:
            n_dbps = self.tables.get_n_dbps_vht(self.params.bandwidth, self.params.mcs, self.params.num_streams)
        else:
            n_dbps = self.tables.get_n_dbps_he(self.params.bandwidth, self.params.mcs, self.params.num_streams)
        
        n_es = self.tables.get_n_es(n_dbps, self.params.phy_mode, self.params.ldpc)
        numerator = 8 * self.params.frame_length + 16 + 6 * n_es
        m_stbc = 2 if self.params.stbc else 1
        return m_stbc * math.ceil(numerator / n_dbps)
    
    def calculate_preamble_duration(self) -> float:
        legacy_duration = 20.0
        if self.params.phy_mode == PhyMode.HT:
            return legacy_duration + 4 + 4 + 4 * self.params.num_streams
        elif self.params.phy_mode == PhyMode.VHT:
            return legacy_duration + 8 + 4 + 4 * self.params.num_streams + 4
        else:
            he_ltf_duration = 4 * self.params.num_streams
            return legacy_duration + 4 + 8 + 4 + he_ltf_duration
    
    def calculate_data_duration(self, nsym: int) -> float:
        if self.params.phy_mode == PhyMode.HE:
            he_gi = self.tables.get_he_gi_value(self.params.gi)
            tsym = self.tables.get_symbol_duration(self.params.phy_mode, self.params.gi, he_gi)
        else:
            tsym = self.tables.get_symbol_duration(self.params.phy_mode, self.params.gi)
        return nsym * tsym
    
    def calculate_he_midamble(self, nsym: int) -> Tuple[int, float]:
        if self.params.phy_mode != PhyMode.HE or not self.params.he_doppler:
            return 0, 0.0
        mma = 20
        nma = max(0, math.ceil((nsym - 1) / mma) - 1)
        t_midamble = nma * self.params.num_streams * 4.0
        return nma, t_midamble
    
    def calculate_he_pe_duration(self) -> float:
        if self.params.phy_mode != PhyMode.HE:
            return 0.0
        pe_table = [0.0, 4.0, 8.0, 16.0]
        return pe_table[self.params.he_pe_duration]
    
    def calculate_signal_extension(self) -> float:
        if self.params.frequency_band == 2.4 and self.params.phy_mode != PhyMode.HE:
            return 6.0
        return 0.0
    
    def calculate(self) -> Dict:
        nsym = self.calculate_nsym()
        preamble = self.calculate_preamble_duration()
        data_duration = self.calculate_data_duration(nsym)
        nma, midamble_duration = self.calculate_he_midamble(nsym)
        pe_duration = self.calculate_he_pe_duration()
        signal_ext = self.calculate_signal_extension()
        total = preamble + data_duration + midamble_duration + pe_duration + signal_ext
        
        return {
            'nsym': nsym,
            'preamble_us': preamble,
            'data_duration_us': data_duration,
            'midamble_count': nma,
            'midamble_duration_us': midamble_duration,
            'pe_duration_us': pe_duration,
            'signal_extension_us': signal_ext,
            'total_time_us': total,
            'total_time_ms': total / 1000.0
        }


class TTCGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TxTime Calculator - TTC计算工具")
        self.root.configure(bg='#f0f0f0')
        
        # 直接创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill="both", expand=True)
        
        self.create_widgets()
        
        # 窗口大小根据内容自动调整
        self.root.update_idletasks()
        req_width = self.main_frame.winfo_reqwidth() + 20
        req_height = self.main_frame.winfo_reqheight() + 20
        self.root.geometry(f"{req_width}x{req_height}")
    
    def create_widgets(self):
        # 标题
        title_label = tk.Label(self.main_frame, text="TxTime Calculator", 
                               font=("Arial", 16, "bold"), bg='#f0f0f0', fg='#333')
        title_label.pack(pady=10)
        
        subtitle_label = tk.Label(self.main_frame, text="HT/VHT/HE空中传输时间计算", 
                                  font=("Arial", 10), bg='#f0f0f0', fg='#666')
        subtitle_label.pack(pady=(0, 10))
        
        # 输入参数框架
        input_frame = ttk.LabelFrame(self.main_frame, text="输入参数", padding="15")
        input_frame.pack(fill="x", padx=10, pady=5)
        
        # 模式选择
        ttk.Label(input_frame, text="PHY模式:").grid(row=0, column=0, sticky="w", pady=5)
        self.mode_var = tk.StringVar(value="HT")
        self.mode_combo = ttk.Combobox(input_frame, textvariable=self.mode_var, 
                                        values=["HT", "VHT", "HE"], state="readonly", width=15)
        self.mode_combo.grid(row=0, column=1, sticky="w", pady=5, padx=(5, 0))
        self.mode_combo.bind('<<ComboboxSelected>>', self.on_mode_change)
        
        # MCS
        ttk.Label(input_frame, text="MCS索引:").grid(row=0, column=2, sticky="w", pady=5, padx=(20, 0))
        self.mcs_var = tk.IntVar(value=7)
        self.mcs_combo = ttk.Combobox(input_frame, textvariable=self.mcs_var, 
                                       values=list(range(0, 8)), state="readonly", width=15)
        self.mcs_combo.grid(row=0, column=3, sticky="w", pady=5, padx=(5, 0))
        
        # 带宽
        ttk.Label(input_frame, text="带宽 (MHz):").grid(row=1, column=0, sticky="w", pady=5)
        self.bw_var = tk.IntVar(value=20)
        self.bw_combo = ttk.Combobox(input_frame, textvariable=self.bw_var, 
                                      values=[20, 40, 80, 160], state="readonly", width=15)
        self.bw_combo.grid(row=1, column=1, sticky="w", pady=5, padx=(5, 0))
        
        # 空间流数
        ttk.Label(input_frame, text="空间流数:").grid(row=1, column=2, sticky="w", pady=5, padx=(20, 0))
        self.streams_var = tk.IntVar(value=1)
        self.streams_combo = ttk.Combobox(input_frame, textvariable=self.streams_var, 
                                           values=list(range(1, 9)), state="readonly", width=15)
        self.streams_combo.grid(row=1, column=3, sticky="w", pady=5, padx=(5, 0))
        
        # 帧长度
        ttk.Label(input_frame, text="帧长度 (字节):").grid(row=2, column=0, sticky="w", pady=5)
        self.length_var = tk.StringVar(value="1500")
        self.length_entry = ttk.Entry(input_frame, textvariable=self.length_var, width=18)
        self.length_entry.grid(row=2, column=1, sticky="w", pady=5, padx=(5, 0))
        
        # GI类型
        ttk.Label(input_frame, text="GI类型:").grid(row=2, column=2, sticky="w", pady=5, padx=(20, 0))
        self.gi_var = tk.StringVar(value="normal")
        self.gi_combo = ttk.Combobox(input_frame, textvariable=self.gi_var, 
                                      values=["normal", "short"], state="readonly", width=15)
        self.gi_combo.grid(row=2, column=3, sticky="w", pady=5, padx=(5, 0))
        
        # 频段
        ttk.Label(input_frame, text="频段 (GHz):").grid(row=3, column=0, sticky="w", pady=5)
        self.freq_var = tk.IntVar(value=5)
        self.freq_combo = ttk.Combobox(input_frame, textvariable=self.freq_var, 
                                        values=[2, 5], state="readonly", width=15)
        self.freq_combo.grid(row=3, column=1, sticky="w", pady=5, padx=(5, 0))
        
        # 复选框框架
        check_frame = ttk.Frame(input_frame)
        check_frame.grid(row=3, column=2, columnspan=2, sticky="w", pady=5, padx=(20, 0))
        
        self.stbc_var = tk.BooleanVar()
        self.stbc_check = ttk.Checkbutton(check_frame, text="启用STBC", variable=self.stbc_var)
        self.stbc_check.pack(side="left", padx=(0, 10))
        
        self.ldpc_var = tk.BooleanVar()
        self.ldpc_check = ttk.Checkbutton(check_frame, text="使用LDPC", variable=self.ldpc_var)
        self.ldpc_check.pack(side="left")
        
        # HE特有参数框架
        self.he_frame = ttk.LabelFrame(self.main_frame, text="HE模式参数", padding="15")
        self.he_frame.pack(fill="x", padx=10, pady=5)
        
        self.he_doppler_var = tk.BooleanVar()
        self.he_doppler_check = ttk.Checkbutton(self.he_frame, text="启用多普勒(Doppler)", 
                                                 variable=self.he_doppler_var)
        self.he_doppler_check.grid(row=0, column=0, sticky="w", pady=5)
        
        ttk.Label(self.he_frame, text="包扩展(PE):").grid(row=0, column=1, sticky="w", pady=5, padx=(20, 0))
        self.he_pe_var = tk.IntVar(value=0)
        self.he_pe_combo = ttk.Combobox(self.he_frame, textvariable=self.he_pe_var, 
                                         values=[0, 1, 2, 3], state="readonly", width=12)
        self.he_pe_combo.grid(row=0, column=2, sticky="w", pady=5, padx=(5, 0))
        ttk.Label(self.he_frame, text="(0:0µs, 1:4µs, 2:8µs, 3:16µs)").grid(row=0, column=3, sticky="w", pady=5, padx=(5, 0))
        
        self.update_he_frame_visibility()
        
        # 帧长度计算框架
        frame_calc_frame = ttk.LabelFrame(self.main_frame, text="帧长度计算（基于吞吐和聚合）", padding="15")
        frame_calc_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_calc_frame, text="吞吐速率 (Mbps):").grid(row=0, column=0, sticky="w", pady=5)
        self.throughput_var = tk.StringVar(value="100")
        ttk.Entry(frame_calc_frame, textvariable=self.throughput_var, width=18).grid(row=0, column=1, sticky="w", pady=5, padx=(5, 0))
        
        ttk.Label(frame_calc_frame, text="时间 (s):").grid(row=0, column=2, sticky="w", pady=5, padx=(20, 0))
        self.time_var = tk.StringVar(value="1")
        ttk.Entry(frame_calc_frame, textvariable=self.time_var, width=18).grid(row=0, column=3, sticky="w", pady=5, padx=(5, 0))
        
        ttk.Label(frame_calc_frame, text="AMSDU聚合个数:").grid(row=1, column=0, sticky="w", pady=5)
        self.amsdu_var = tk.StringVar(value="2")
        ttk.Entry(frame_calc_frame, textvariable=self.amsdu_var, width=18).grid(row=1, column=1, sticky="w", pady=5, padx=(5, 0))
        
        ttk.Label(frame_calc_frame, text="AMPDU聚合个数:").grid(row=1, column=2, sticky="w", pady=5, padx=(20, 0))
        self.ampdu_var = tk.StringVar(value="4")
        ttk.Entry(frame_calc_frame, textvariable=self.ampdu_var, width=18).grid(row=1, column=3, sticky="w", pady=5, padx=(5, 0))
        
        ttk.Button(frame_calc_frame, text="计算帧长度并填入输入框", command=self.calculate_frame_length).grid(row=2, column=0, columnspan=4, pady=10)
        
        # 计算按钮框架
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(pady=15)
        
        self.calc_button = ttk.Button(button_frame, text="计算传输时间", command=self.calculate, width=25)
        self.calc_button.pack(side="left", padx=5)
        
        self.clear_button = ttk.Button(button_frame, text="清除结果", command=self.clear_results, width=15)
        self.clear_button.pack(side="left", padx=5)
        
        # 结果显示框架
        result_frame = ttk.LabelFrame(self.main_frame, text="计算结果", padding="15")
        result_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 创建结果显示文本框
        self.result_text = tk.Text(result_frame, height=40, width=80, font=("Courier", 9))
        self.result_text.pack(fill="both", expand=True)
        
        # 配置文本标签样式
        self.result_text.tag_configure("header", font=("Courier", 10, "bold"), foreground="#333")
        self.result_text.tag_configure("param", foreground="#0066cc")
        self.result_text.tag_configure("value", font=("Courier", 9, "bold"), foreground="#009900")
        self.result_text.tag_configure("divider", foreground="#cccccc")
        self.result_text.tag_configure("total", font=("Courier", 10, "bold"), foreground="#ff0000")
        
        # 底部信息
        info_label = tk.Label(self.main_frame, text="基于802.11n/ac/ax标准 | 公式: Nsym = ceil((8×LENGTH + 16 + 6×N_ES) / N_DBPS)", 
                               font=("Arial", 8), bg='#f0f0f0', fg='#999')
        info_label.pack(pady=(10, 5))
    
    def calculate_frame_length(self):
        """根据吞吐速率、时间、AMSDU/AMPDU聚合个数计算帧长度"""
        try:
            throughput_mbps = float(self.throughput_var.get())
            time_s = float(self.time_var.get())
            amsdu_count = int(self.amsdu_var.get())
            ampdu_count = int(self.ampdu_var.get())
            
            if throughput_mbps <= 0:
                messagebox.showerror("输入错误", "吞吐速率必须大于0")
                return
            if time_s <= 0:
                messagebox.showerror("输入错误", "时间必须大于0")
                return
            if amsdu_count <= 0 or ampdu_count <= 0:
                messagebox.showerror("输入错误", "聚合个数必须大于0")
                return
            
            total_bits = throughput_mbps * time_s * 1_000_000
            total_bytes = total_bits / 8
            total_agg_frames = amsdu_count * ampdu_count
            frame_length = int(total_bytes / total_agg_frames)
            
            self.length_var.set(str(frame_length))
            
            messagebox.showinfo("计算完成", 
                              f"总数据量: {total_bytes:.0f} 字节\n"
                              f"聚合总帧数: {total_agg_frames}\n"
                              f"单个帧长度: {frame_length} 字节\n"
                              f"(已自动填入帧长度输入框)")
            
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的数值")
    
    def on_mode_change(self, event=None):
        mode = self.mode_var.get()
        if mode == "HT":
            self.mcs_combo['values'] = list(range(0, 8))
            if self.mcs_var.get() >= 8:
                self.mcs_var.set(7)
        elif mode == "VHT":
            self.mcs_combo['values'] = list(range(0, 10))
            if self.mcs_var.get() >= 10:
                self.mcs_var.set(9)
        else:
            self.mcs_combo['values'] = list(range(0, 12))
        self.update_he_frame_visibility()
    
    def update_he_frame_visibility(self):
        mode = self.mode_var.get()
        if mode == "HE":
            self.he_frame.pack(fill="x", padx=10, pady=5)
        else:
            self.he_frame.pack_forget()
    
    def validate_inputs(self) -> bool:
        try:
            length = int(self.length_var.get())
            if length <= 0:
                messagebox.showerror("输入错误", "帧长度必须为正整数")
                return False
        except ValueError:
            messagebox.showerror("输入错误", "帧长度必须是整数")
            return False
        return True
    
    def calculate(self):
        if not self.validate_inputs():
            return
        
        mode_map = {"HT": PhyMode.HT, "VHT": PhyMode.VHT, "HE": PhyMode.HE}
        gi_map = {"normal": GiType.NORMAL, "short": GiType.SHORT}
        
        params = TTCParams(
            phy_mode=mode_map[self.mode_var.get()],
            mcs=self.mcs_var.get(),
            bandwidth=self.bw_var.get(),
            num_streams=self.streams_var.get(),
            frame_length=int(self.length_var.get()),
            gi=gi_map[self.gi_var.get()],
            stbc=self.stbc_var.get(),
            ldpc=self.ldpc_var.get(),
            he_doppler=self.he_doppler_var.get() if self.mode_var.get() == "HE" else False,
            he_pe_duration=self.he_pe_var.get() if self.mode_var.get() == "HE" else 0,
            frequency_band=self.freq_var.get()
        )
        
        calculator = TTCCalculator(params)
        result = calculator.calculate()
        
        self.display_results(params, result)
        
        # 计算后调整窗口大小
        self.root.update_idletasks()
        req_width = self.main_frame.winfo_reqwidth() + 20
        req_height = self.main_frame.winfo_reqheight() + 20
        self.root.geometry(f"{req_width}x{req_height}")
    
    def display_results(self, params: TTCParams, result: Dict):
        self.result_text.delete(1.0, tk.END)
        
        self.result_text.insert(tk.END, "=" * 65 + "\n", "divider")
        self.result_text.insert(tk.END, "TxTime Calculator 计算结果\n", "header")
        self.result_text.insert(tk.END, "=" * 65 + "\n", "divider")
        
        self.result_text.insert(tk.END, f"模式: {params.phy_mode.value}\n", "param")
        self.result_text.insert(tk.END, f"MCS: {params.mcs}\n", "param")
        self.result_text.insert(tk.END, f"带宽: {params.bandwidth} MHz\n", "param")
        self.result_text.insert(tk.END, f"空间流数: {params.num_streams}\n", "param")
        self.result_text.insert(tk.END, f"帧长度: {params.frame_length} bytes\n", "param")
        self.result_text.insert(tk.END, f"GI类型: {params.gi.value}\n", "param")
        self.result_text.insert(tk.END, f"STBC: {'启用' if params.stbc else '禁用'}\n", "param")
        self.result_text.insert(tk.END, f"LDPC: {'启用' if params.ldpc else '禁用'}\n", "param")
        
        if params.phy_mode == PhyMode.HE:
            self.result_text.insert(tk.END, f"HE多普勒: {'启用' if params.he_doppler else '禁用'}\n", "param")
            self.result_text.insert(tk.END, f"HE包扩展: {params.he_pe_duration} ({result['pe_duration_us']} µs)\n", "param")
        
        self.result_text.insert(tk.END, "-" * 65 + "\n", "divider")
        self.result_text.insert(tk.END, f"OFDM符号数 (Nsym): {result['nsym']}\n", "value")
        self.result_text.insert(tk.END, "-" * 65 + "\n", "divider")
        self.result_text.insert(tk.END, f"前导码时长:     {result['preamble_us']:.2f} µs\n", "value")
        self.result_text.insert(tk.END, f"数据时长:       {result['data_duration_us']:.2f} µs\n", "value")
        
        if result['midamble_count'] > 0:
            self.result_text.insert(tk.END, f"Midamble数量:   {result['midamble_count']}\n", "value")
            self.result_text.insert(tk.END, f"Midamble时长:   {result['midamble_duration_us']:.2f} µs\n", "value")
        
        if result['pe_duration_us'] > 0:
            self.result_text.insert(tk.END, f"包扩展时长:     {result['pe_duration_us']:.2f} µs\n", "value")
        
        if result['signal_extension_us'] > 0:
            self.result_text.insert(tk.END, f"信号扩展:       {result['signal_extension_us']:.2f} µs\n", "value")
        
        self.result_text.insert(tk.END, "-" * 65 + "\n", "divider")
        self.result_text.insert(tk.END, f"总空中时间:     {result['total_time_us']:.2f} µs ({result['total_time_ms']:.4f} ms)\n", "total")
        self.result_text.insert(tk.END, "=" * 65 + "\n", "divider")
    
    def clear_results(self):
        self.result_text.delete(1.0, tk.END)


def main():
    root = tk.Tk()
    app = TTCGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
