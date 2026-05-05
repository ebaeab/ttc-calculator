#!/usr/bin/env python3
"""
TxTime Calculator - 计算HT/VHT/HE帧的空中传输时间
基于Wi-Fi 802.11n/ac/ax标准
"""

import math
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple


class PhyMode(Enum):
    HT = "HT"      # 802.11n
    VHT = "VHT"    # 802.11ac
    HE = "HE"      # 802.11ax


class GiType(Enum):
    NORMAL = "normal"
    SHORT = "short"


@dataclass
class TTCParams:
    """TTC计算输入参数"""
    phy_mode: PhyMode          # HT/VHT/HE
    mcs: int                   # MCS索引 (0-7 HT, 0-9 VHT, 0-11 HE)
    bandwidth: int             # 带宽 MHz (20, 40, 80, 160)
    num_streams: int           # 空间流数
    frame_length: int          # 帧长度 (字节)
    gi: GiType = GiType.NORMAL # GI类型
    stbc: bool = False         # 是否启用STBC
    ldpc: bool = False         # 是否使用LDPC (影响N_ES)
    he_doppler: bool = False   # HE多普勒模式
    he_pe_duration: int = 0    # HE包扩展时长 (0-3, 对应0/4/8/16µs)
    frequency_band: int = 5    # 频段 2.4或5 GHz


class TTCTables:
    """TTC查表数据"""
    
    # N_DBPS: 每OFDM符号数据比特数
    # 格式: {mode: {bandwidth: {mcs: {streams: n_dbps}}}}
    
    @staticmethod
    def get_n_dbps_ht(bandwidth: int, mcs: int, streams: int) -> int:
        """HT模式N_DBPS查表"""
        # HT 20MHz N_DBPS表 (每流)
        ht20_mcs_dbps = {
            0: 26, 1: 52, 2: 78, 3: 104, 4: 156, 5: 208, 6: 234, 7: 260
        }
        # HT 40MHz N_DBPS表 (每流)
        ht40_mcs_dbps = {
            0: 54, 1: 108, 2: 162, 3: 216, 4: 324, 5: 432, 6: 486, 7: 540
        }
        
        if mcs not in range(0, 8):
            raise ValueError(f"HT MCS must be 0-7, got {mcs}")
        if streams not in range(1, 5):
            raise ValueError(f"HT streams must be 1-4, got {streams}")
        
        if bandwidth == 20:
            return ht20_mcs_dbps[mcs] * streams
        elif bandwidth == 40:
            return ht40_mcs_dbps[mcs] * streams
        else:
            raise ValueError(f"HT bandwidth must be 20 or 40, got {bandwidth}")
    
    @staticmethod
    def get_n_dbps_vht(bandwidth: int, mcs: int, streams: int) -> int:
        """VHT模式N_DBPS查表"""
        # VHT N_DBPS per spatial stream
        # 20MHz
        vht20 = {0: 26, 1: 52, 2: 78, 3: 104, 4: 156, 5: 208, 6: 234, 7: 260, 8: 312, 9: 346}
        # 40MHz
        vht40 = {0: 54, 1: 108, 2: 162, 3: 216, 4: 324, 5: 432, 6: 486, 7: 540, 8: 648, 9: 720}
        # 80MHz
        vht80 = {0: 117, 1: 234, 2: 351, 3: 468, 4: 702, 5: 936, 6: 1053, 7: 1170, 8: 1404, 9: 1560}
        # 160MHz
        vht160 = {0: 234, 1: 468, 2: 702, 3: 936, 4: 1404, 5: 1872, 6: 2106, 7: 2340, 8: 2808, 9: 3120}
        
        tables = {20: vht20, 40: vht40, 80: vht80, 160: vht160}
        
        if mcs not in range(0, 10):
            raise ValueError(f"VHT MCS must be 0-9, got {mcs}")
        if streams not in range(1, 9):
            raise ValueError(f"VHT streams must be 1-8, got {streams}")
        if bandwidth not in tables:
            raise ValueError(f"VHT bandwidth must be 20/40/80/160, got {bandwidth}")
        
        return tables[bandwidth][mcs] * streams
    
    @staticmethod
    def get_n_dbps_he(bandwidth: int, mcs: int, streams: int) -> int:
        """HE模式N_DBPS查表"""
        # HE N_DBPS per spatial stream (802.11ax)
        # 20MHz
        he20 = {0: 24, 1: 48, 2: 72, 3: 96, 4: 144, 5: 192, 6: 216, 7: 240, 8: 288, 9: 320, 10: 360, 11: 384}
        # 40MHz
        he40 = {0: 48, 1: 96, 2: 144, 3: 192, 4: 288, 5: 384, 6: 432, 7: 480, 8: 576, 9: 640, 10: 720, 11: 768}
        # 80MHz
        he80 = {0: 102, 1: 204, 2: 306, 3: 408, 4: 612, 5: 816, 6: 918, 7: 1020, 8: 1224, 9: 1360, 10: 1530, 11: 1632}
        # 160MHz
        he160 = {0: 204, 1: 408, 2: 612, 3: 816, 4: 1224, 5: 1632, 6: 1836, 7: 2040, 8: 2448, 9: 2720, 10: 3060, 11: 3264}
        
        tables = {20: he20, 40: he40, 80: he80, 160: he160}
        
        if mcs not in range(0, 12):
            raise ValueError(f"HE MCS must be 0-11, got {mcs}")
        if streams not in range(1, 9):
            raise ValueError(f"HE streams must be 1-8, got {streams}")
        if bandwidth not in tables:
            raise ValueError(f"HE bandwidth must be 20/40/80/160, got {bandwidth}")
        
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
        """获取OFDM符号时长(µs)"""
        if phy_mode == PhyMode.HE:
            # HE符号时长 = 12.8 + T_GI
            return 12.8 + he_gi_us
        else:
            # HT/VHT
            if gi == GiType.NORMAL:
                return 4.0
            else:  # SHORT
                return 3.6
    
    @staticmethod
    def get_he_gi_value(gi: GiType) -> float:
        """获取HE GI值(µs)"""
        if gi == GiType.NORMAL:
            return 3.2  # HE normal GI
        else:
            return 0.8  # HE short GI (也可为1.6)


class TTCCalculator:
    """TxTime Calculator主计算类"""
    
    def __init__(self, params: TTCParams):
        self.params = params
        self.tables = TTCTables()
    
    def calculate_nsym(self) -> int:
        """计算OFDM符号数 Nsym = m_STBC × ceil((8×LENGTH + 16 + 6×N_ES) / N_DBPS)"""
        # 获取N_DBPS
        if self.params.phy_mode == PhyMode.HT:
            n_dbps = self.tables.get_n_dbps_ht(
                self.params.bandwidth, self.params.mcs, self.params.num_streams
            )
        elif self.params.phy_mode == PhyMode.VHT:
            n_dbps = self.tables.get_n_dbps_vht(
                self.params.bandwidth, self.params.mcs, self.params.num_streams
            )
        else:  # HE
            n_dbps = self.tables.get_n_dbps_he(
                self.params.bandwidth, self.params.mcs, self.params.num_streams
            )
        
        # 获取N_ES
        n_es = self.tables.get_n_es(n_dbps, self.params.phy_mode, self.params.ldpc)
        
        # 计算分子: 8×LENGTH + 16 + 6×N_ES
        numerator = 8 * self.params.frame_length + 16 + 6 * n_es
        
        # m_STBC
        m_stbc = 2 if self.params.stbc else 1
        
        # Nsym = m_STBC × ceil(numerator / N_DBPS)
        nsym = m_stbc * math.ceil(numerator / n_dbps)
        
        return nsym
    
    def calculate_preamble_duration(self) -> float:
        """计算前导码时长(µs)"""
        # Legacy前导码部分 (所有模式相同)
        # L-STF (8 µs) + L-LTF (8 µs) + L-SIG (4 µs) = 20 µs
        legacy_duration = 20.0
        
        if self.params.phy_mode == PhyMode.HT:
            # HT-SIG (4 µs) + HT-STF (4 µs) + HT-LTFs (4 µs × num_streams)
            ht_training = 4 + 4 + 4 * self.params.num_streams
            return legacy_duration + ht_training
        
        elif self.params.phy_mode == PhyMode.VHT:
            # VHT-SIG-A (8 µs) + VHT-STF (4 µs) + VHT-LTFs (4 µs × num_streams) + VHT-SIG-B (4 µs)
            vht_training = 8 + 4 + 4 * self.params.num_streams + 4
            return legacy_duration + vht_training
        
        else:  # HE
            # RL-SIG (4 µs) + HE-SIG-A (8 µs) + HE-STF (4 µs) + HE-LTFs (4 µs × num_streams)
            he_ltf_duration = 4 * self.params.num_streams
            he_training = 4 + 8 + 4 + he_ltf_duration
            return legacy_duration + he_training
    
    def calculate_data_duration(self, nsym: int) -> float:
        """计算数据部分时长(µs)"""
        if self.params.phy_mode == PhyMode.HE:
            he_gi = self.tables.get_he_gi_value(self.params.gi)
            tsym = self.tables.get_symbol_duration(self.params.phy_mode, self.params.gi, he_gi)
        else:
            tsym = self.tables.get_symbol_duration(self.params.phy_mode, self.params.gi)
        
        return nsym * tsym
    
    def calculate_he_midamble(self, nsym: int) -> Tuple[int, float]:
        """计算HE Midamble时长和数量"""
        if self.params.phy_mode != PhyMode.HE or not self.params.he_doppler:
            return 0, 0.0
        
        # Mma: Midamble周期, 通常为10或20
        mma = 20  # 简化假设
        
        # Nma = max(0, ceil((Nsym - 1) / Mma) - 1)
        nma = max(0, math.ceil((nsym - 1) / mma) - 1)
        
        # T_midamble = Nma × N_HE_LTF × T_HE_LTF_SYM
        n_he_ltf = self.params.num_streams
        t_he_ltf_sym = 4.0  # HE-LTF符号时长
        t_midamble = nma * n_he_ltf * t_he_ltf_sym
        
        return nma, t_midamble
    
    def calculate_he_pe_duration(self) -> float:
        """计算HE包扩展(PE)时长"""
        if self.params.phy_mode != PhyMode.HE:
            return 0.0
        
        # he_pe_duration: 0->0µs, 1->4µs, 2->8µs, 3->16µs
        pe_table = [0.0, 4.0, 8.0, 16.0]
        if self.params.he_pe_duration in range(0, 4):
            return pe_table[self.params.he_pe_duration]
        return 0.0
    
    def calculate_signal_extension(self) -> float:
        """计算信号扩展时长"""
        # 2.4G OFDM需要6µs信号扩展
        if self.params.frequency_band == 2.4 and self.params.phy_mode != PhyMode.HE:
            return 6.0
        return 0.0
    
    def calculate(self) -> Dict:
        """执行完整TTC计算"""
        # 1. 计算符号数
        nsym = self.calculate_nsym()
        
        # 2. 前导码时长
        preamble = self.calculate_preamble_duration()
        
        # 3. 数据时长
        data_duration = self.calculate_data_duration(nsym)
        
        # 4. HE Midamble
        nma, midamble_duration = self.calculate_he_midamble(nsym)
        
        # 5. HE包扩展
        pe_duration = self.calculate_he_pe_duration()
        
        # 6. 信号扩展
        signal_ext = self.calculate_signal_extension()
        
        # 7. 总时长
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
    
    def print_result(self):
        """打印计算结果"""
        result = self.calculate()
        
        print(f"\n{'='*60}")
        print(f"TxTime Calculator 计算结果")
        print(f"{'='*60}")
        print(f"模式: {self.params.phy_mode.value}")
        print(f"MCS: {self.params.mcs}")
        print(f"带宽: {self.params.bandwidth} MHz")
        print(f"空间流数: {self.params.num_streams}")
        print(f"帧长度: {self.params.frame_length} bytes")
        print(f"GI类型: {self.params.gi.value}")
        print(f"STBC: {'启用' if self.params.stbc else '禁用'}")
        print(f"LDPC: {'启用' if self.params.ldpc else '禁用'}")
        if self.params.phy_mode == PhyMode.HE:
            print(f"HE多普勒: {'启用' if self.params.he_doppler else '禁用'}")
            print(f"HE包扩展: {self.params.he_pe_duration} ({result['pe_duration_us']} µs)")
        print(f"{'-'*60}")
        print(f"OFDM符号数 (Nsym): {result['nsym']}")
        print(f"{'-'*60}")
        print(f"前导码时长:     {result['preamble_us']:.2f} µs")
        print(f"数据时长:       {result['data_duration_us']:.2f} µs")
        if result['midamble_count'] > 0:
            print(f"Midamble数量:   {result['midamble_count']}")
            print(f"Midamble时长:   {result['midamble_duration_us']:.2f} µs")
        if result['pe_duration_us'] > 0:
            print(f"包扩展时长:     {result['pe_duration_us']:.2f} µs")
        if result['signal_extension_us'] > 0:
            print(f"信号扩展:       {result['signal_extension_us']:.2f} µs")
        print(f"{'-'*60}")
        print(f"总空中时间:     {result['total_time_us']:.2f} µs ({result['total_time_ms']:.4f} ms)")
        print(f"{'='*60}\n")


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='TxTime Calculator - 计算HT/VHT/HE帧的空中传输时间',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 计算HT 20MHz MCS7 1流 1500字节帧的传输时间
  %(prog)s --mode HT --mcs 7 --bw 20 --streams 1 --length 1500
  
  # 计算VHT 80MHz MCS9 4流 1500字节帧(短GI)
  %(prog)s --mode VHT --mcs 9 --bw 80 --streams 4 --length 1500 --gi short
  
  # 计算HE 80MHz MCS11 4流 1500字节帧(启用多普勒和包扩展)
  %(prog)s --mode HE --mcs 11 --bw 80 --streams 4 --length 1500 --he-doppler --he-pe 2
        """
    )
    
    parser.add_argument('--mode', type=str, choices=['HT', 'VHT', 'HE'], required=True,
                        help='物理层模式')
    parser.add_argument('--mcs', type=int, required=True,
                        help='MCS索引 (HT:0-7, VHT:0-9, HE:0-11)')
    parser.add_argument('--bw', type=int, choices=[20, 40, 80, 160], required=True,
                        help='带宽 MHz')
    parser.add_argument('--streams', type=int, required=True,
                        help='空间流数')
    parser.add_argument('--length', type=int, required=True,
                        help='帧长度 (字节)')
    parser.add_argument('--gi', type=str, choices=['normal', 'short'], default='normal',
                        help='GI类型 (默认: normal)')
    parser.add_argument('--stbc', action='store_true',
                        help='启用STBC')
    parser.add_argument('--ldpc', action='store_true',
                        help='使用LDPC编码')
    parser.add_argument('--freq', type=int, choices=[2, 5], default=5,
                        help='频段 GHz (默认: 5)')
    parser.add_argument('--he-doppler', action='store_true',
                        help='HE多普勒模式')
    parser.add_argument('--he-pe', type=int, choices=[0, 1, 2, 3], default=0,
                        help='HE包扩展 (0:0µs, 1:4µs, 2:8µs, 3:16µs)')
    
    args = parser.parse_args()
    
    # 创建参数对象
    params = TTCParams(
        phy_mode=PhyMode[args.mode],
        mcs=args.mcs,
        bandwidth=args.bw,
        num_streams=args.streams,
        frame_length=args.length,
        gi=GiType[args.gi.upper()],
        stbc=args.stbc,
        ldpc=args.ldpc,
        he_doppler=args.he_doppler,
        he_pe_duration=args.he_pe,
        frequency_band=args.freq * 1000  # 转为MHz存储
    )
    
    # 计算并输出结果
    calculator = TTCCalculator(params)
    calculator.print_result()


if __name__ == "__main__":
    main()
