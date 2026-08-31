"""
机械革命 (Mechrevo) ACPI / EC 底层驱动模块.

通过 Windows 内核驱动 \\\\.\\ACPIDriver 以 IOCTL 方式读写 Embedded Controller (EC) 寄存器,
实现 CPU 功耗调节、GPU D-State 控制、风扇策略表下发、LED 灯光控制、AC Recovery 开关等硬件级操作.

使用前需确保 Mechrevo Control Center 已正确安装 (提供 ACPIDriver.sys 内核驱动).
"""
import ctypes
import struct
import time
import json
import os
from threading import Lock
from typing import Tuple, List, Optional

# ============================================================
# Win32 API 常量
# ============================================================
GENERIC_READ       = 0x80000000
GENERIC_WRITE      = 0x40000000
FILE_SHARE_READ    = 0x00000001
FILE_SHARE_WRITE   = 0x00000002
OPEN_EXISTING      = 3
INVALID_HANDLE_VALUE = -1

# ============================================================
# IOCTL 控制码 (来自 C# 常量)
# ============================================================
IOCTL_GPD_ACPI_ECREAD    = 2621482120
IOCTL_GPD_ACPI_ECWRITE   = 2621482124
IOCTL_GPD_ACPI_CUSTOMCTL = 2621482244
IOCTL_GPD_ACPI_PEREAD    = 2621482144

# ============================================================
# Linux API 常量 (/dev/mem, 未实现)
# ============================================================
LINUX_MMAP_BASE          = 0xFED50000
LINUX_MMAP_SIZE          = 4096

# ============================================================
# EC 寄存器地址定义
# ============================================================
REG_ADAPTER_WATT         = 1183   # 适配器功率 (编码)
REG_AC_RECOVERY_EC       = 1830   # AC Recovery (EC 路径) bit3
REG_OEM10                = 1831   # 自定义模式 bit5
REG_DEFAULT_POWER_GAMING = 1840   # 游戏模式默认功耗 PL1
REG_DEFAULT_POWER_OFFICE = 1844   # 办公模式默认功耗 PL1
REG_PROJECT_ID           = 1856   # 项目 ID
REG_AP_EXIST             = 1857   # 应用存在标志 bit0
REG_GPU_TGP_CTRL         = 1859   # GPU TGP / Dynamic Boost 控制 bit1:DB, bit2:TGP
REG_GPU_TGP_OFFSET       = 1860   # GPU TGP 增加量
REG_DYNAMIC_BOOST_MAX    = 1862   # Dynamic Boost 最大 TGP
REG_FN_KEY_CTRL          = 1870   # Fn 键控制 bit4
REG_GLOBAL_CONFIG        = 1894   # bit0-1:SupportByte, bit4:China mode
REG_TRIGGER              = 1895   # 触发寄存器 (WinKey/LightBar/USB 充电)
REG_STATUS_FLAGS         = 1896   # bit0:WinKey 状态, bit1:LightBar 状态
REG_CPU_PL1              = 1923   # CPU PL1 (W)
REG_CPU_PL2              = 1924   # CPU PL2 (W)
REG_CPU_PL4              = 1925   # CPU PL4 (W)
REG_CPU_TCC              = 1926   # CPU TCC Offset (bit7=enable, bit6-0=value)
REG_CPU_TCC_APPLIED      = 1036   # CPU TCC Offset Applied (EC Firmware Copy)
REG_FAN_SWITCH_SPEED     = 1927   # 风扇切换速度 (ms/PWM%步进, bit7=enable)
REG_GPU_D_STATE          = 1931   # GPU D-State
REG_KEYBOARD_BACKLIGHT   = 1932   # 键盘背光
REG_POWER_LED            = 1957   # 电源指示灯颜色 bit0-1
REG_TOUCHPAD             = 1958   # 触摸板 bit3:LED, bit6:Toggle
REG_DEFAULT_POWER_TURBO  = 1959   # 狂暴模式默认功耗 PL1
REG_WHISPER_MODE_MAIN    = 1989   # 办公模式安全保护/WhisperMode 主开关
REG_WHISPER_MODE_STATUS  = 1990   # WhisperMode 状态 bit0-1 ADDR_AP_CTL 
REG_TYPEC_STATUS         = 1996   # Type-C 状态
REG_DEFAULT_TCC_GAMING   = 2008   # 游戏模式默认 TCC
REG_DEFAULT_TCC_OFFICE   = 2009   # 办公模式默认 TCC
REG_DEFAULT_TCC_TURBO    = 2010   # 狂暴模式默认 TCC
REG_GPU_FREQ             = 3403   # GPU 核心频率
REG_GPU_MEM_FREQ_LOW     = 3404   # GPU 显存频率 (低字节)
REG_GPU_MEM_FREQ_HIGH    = 3405   # GPU 显存频率 (高字节, bit6-0)

REG_FAN1_RPM_HIGH        = 1124   # CPU 风扇转速
REG_FAN1_RPM_LOW         = 1125
REG_FAN2_RPM_HIGH        = 1132   # GPU 风扇转速
REG_FAN2_RPM_LOW         = 1131
REG_FAN1_DUTY            = 1883   # CPU 风扇 PWM
REG_FAN2_DUTY            = 1884   # GPU 风扇 PWM

# https://gist.github.com/w568w/b2fc5f9d1f4dff13efe751abec27b396
REG_BATTERY_CHARGE_LIMIT = 1977   # 电池上限百分比
REG_BATTERY_VOLT_LOW     = 1314   # 电池上限电压
REG_BATTERY_VOLT_HIGH    = 1315


# 风扇策略表 EC 起始地址
FAN_CPU_UPT   = 3840   # CPU 升温阈值 (16 点)
FAN_CPU_DOWNT = 3856   # CPU 降温阈值 (16 点)
FAN_CPU_DUTY  = 3872   # CPU 占空比 (16 点)
FAN_GPU_UPT   = 3888   # GPU 升温阈值 (16 点)
FAN_GPU_DOWNT = 3904   # GPU 降温阈值 (16 点)
FAN_GPU_DUTY  = 3920   # GPU 占空比 (16 点)

# 风扇策略表大小
FAN_TABLE_SIZE = 16

REG_MAFAN_CTRL           = 1873   # 硬件风扇曲线
# 取值
# 可能要关闭 set_fan_table_enabled 生效？
FAN_CTRL_LABELS = {
    0: "Custom",
    16: "Turbo",
    64: "FanBoost",
    80: "Turbo+FanBoost",
    128: "User_Fan",
    160: "HiMode (Office)",
    224: "HiMode+FanBoost",
}

# ============================================================
# 底层驱动 IO 类
# ============================================================

class AcpiDriver:
    """对应 C# 中的 AcpiCtrl, 负责通过 IOCTL 与 \\\\.\\ACPIDriver 通信."""

    def __init__(self, device_path: str = r"\\.\ACPIDriver"):
        self.device_path = device_path
        self._lock = Lock()
        self.kernel32 = ctypes.windll.kernel32

    def _send_ioctl(self, ioctl_code: int, in_buffer: bytes, out_size: int) -> Optional[bytes]:
        """向驱动发起 DeviceIoControl 请求并返回输出缓冲区原始数据.

        Args:
            ioctl_code: IOCTL 控制码.
            in_buffer:  输入缓冲区 (字节序列).
            out_size:   输出缓冲区大小 (字节数).

        Returns:
            成功时返回输出缓冲区原始字节, 失败返回 None.
        """
        handle = self.kernel32.CreateFileW(
            self.device_path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )

        if handle == INVALID_HANDLE_VALUE:
            return None

        out_buffer = ctypes.create_string_buffer(out_size)
        bytes_returned = ctypes.c_uint32(0)

        success = self.kernel32.DeviceIoControl(
            handle,
            ioctl_code,
            in_buffer,
            len(in_buffer),
            out_buffer,
            out_size,
            ctypes.byref(bytes_returned),
            None,
        )

        self.kernel32.CloseHandle(handle)

        if success:
            return out_buffer.raw
        return None

    def read_ec(self, addr: int) -> int:
        """从 EC 指定地址读取 1 个字节 (0-255).

        Args:
            addr: EC 寄存器地址 (0-65535).

        Returns:
            读取到的字节值 (0-255), 失败返回 0.
        """
        with self._lock:
            in_buf = struct.pack("<I", addr)
            res = self._send_ioctl(IOCTL_GPD_ACPI_ECREAD, in_buf, 4)
            if res:
                val = struct.unpack("<I", res)[0]
                return val & 0xFF
            return 0

    def write_ec(self, addr: int, data: int) -> None:
        """向 EC 指定地址写入 1 个字节 (0-255).

        Args:
            addr: EC 寄存器地址.
            data: 要写入的字节值 (自动截断低 8 位).
        """
        with self._lock:
            in_buf = struct.pack("<II", addr, data & 0xFF)
            self._send_ioctl(IOCTL_GPD_ACPI_ECWRITE, in_buf, 4)
            time.sleep(0.01)  # 对应 C# DelayTime

    def custom_rw(self, method_name: str, input_val: int) -> int:
        """通用自定义读写 (对应 C# CustomRW).

        将方法名前 4 个字符编码为 int 作为方法 ID 发送给驱动.

        Args:
            method_name: 方法名 (前 4 个字符有效).
            input_val:  输入值.

        Returns:
            驱动返回的低字节 (0-255).
        """
        method_bytes = method_name.encode("ascii")[:4].ljust(4, b"\x00")
        method_id = struct.unpack("<I", method_bytes)[0]
        in_buf = struct.pack("<II", method_id, input_val)
        res = self._send_ioctl(IOCTL_GPD_ACPI_CUSTOMCTL, in_buf, 4)
        if res:
            return struct.unpack("<I", res)[0] & 0xFF
        return 0


# ============================================================
# 风扇策略表数据结构
# ============================================================

class FanPoint:
    """风扇策略表中的一个温度-转速点.

    Attributes:
        up_t:   升温触发温度 (到达此温度后升档).
        down_t: 降温触发温度 (低于此温度后降档).
        duty:   占空比 (0-100, 对应 PWM 百分比).
    """

    def __init__(self, up_t: int = 0, down_t: int = 0, duty: float = 0):
        self.UpT = up_t
        self.DownT = down_t
        self.Duty = duty

    def to_dict(self) -> dict:
        """转换为字典, 用于 JSON 序列化."""
        return {"UpT": self.UpT, "DownT": self.DownT, "Duty": self.Duty}

    @classmethod
    def from_dict(cls, d: dict) -> "FanPoint":
        """从字典创建 FanPoint.

        Args:
            d: 包含 UpT, DownT, Duty 键的字典.

        Returns:
            新的 FanPoint 实例.
        """
        return cls(up_t=d.get("UpT", 0), down_t=d.get("DownT", 0), duty=d.get("Duty", 0))

    def __repr__(self) -> str:
        return f"FanPoint(UpT={self.UpT}, DownT={self.DownT}, Duty={self.Duty})"


class FanTable:
    """16 点风扇策略表, 含滞后 (Hysteresis) 逻辑.

    每个点定义了一个温度区间与对应的 PWM 占空比.
    最后几个点通常填充为 sentinel 值 (255/255/95) 表示曲线终点.
    """

    def __init__(self):
        self.Points: List[FanPoint] = [FanPoint() for _ in range(FAN_TABLE_SIZE)]

    def to_dict(self) -> List[dict]:
        """转换为字典列表, 用于 JSON 序列化."""
        return [p.to_dict() for p in self.Points]

    @classmethod
    def from_list(cls, data: List[dict]) -> "FanTable":
        """从字典列表反序列化为 FanTable.

        Args:
            data: 字典列表, 每个元素包含 UpT, DownT, Duty 键.

        Returns:
            新的 FanTable 实例 (不足 16 点自动补齐).
        """
        table = cls()
        for i, d in enumerate(data[:FAN_TABLE_SIZE]):
            table.Points[i] = FanPoint.from_dict(d)
        return table

    @classmethod
    def from_json_file(cls, path: str) -> "FanTable":
        """从 JSON 文件中的列表加载 FanTable.

        Args:
            path: JSON 文件路径.

        Returns:
            新的 FanTable 实例.
        """
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_list(data)

    def __repr__(self) -> str:
        return f"FanTable({len(self.Points)} points)"


# ============================================================
# EC 风扇控制
# ============================================================

class MyEcFanCtrl:
    """EC 风扇策略表读写控制器.

    负责将 FanTable 数据写入 EC 的对应地址,
    或从 EC 读取当前策略表并构造 FanTable 对象返回.
    """

    def __init__(self, driver: Optional[AcpiDriver] = None):
        self.driver = driver or AcpiDriver()

    def set_cpu_fan_table(self, fan_table: FanTable) -> None:
        """将 CPU 风扇策略表下发到 EC.

        Args:
            fan_table: 包含 16 个 FanPoint 的策略表.
        """
        for i in range(FAN_TABLE_SIZE):
            self.driver.write_ec(FAN_CPU_UPT + i, fan_table.Points[i].UpT)
            self.driver.write_ec(FAN_CPU_DOWNT + i, fan_table.Points[i].DownT)
            self.driver.write_ec(FAN_CPU_DUTY + i, int(fan_table.Points[i].Duty * 2))

    def set_gpu_fan_table(self, fan_table: FanTable) -> None:
        """将 GPU 风扇策略表下发到 EC.

        Args:
            fan_table: 包含 16 个 FanPoint 的策略表.
        """
        for i in range(FAN_TABLE_SIZE):
            self.driver.write_ec(FAN_GPU_UPT + i, fan_table.Points[i].UpT)
            self.driver.write_ec(FAN_GPU_DOWNT + i, fan_table.Points[i].DownT)
            self.driver.write_ec(FAN_GPU_DUTY + i, int(fan_table.Points[i].Duty * 2))

    def read_fan_table_from_ec(self) -> Tuple[FanTable, FanTable]:
        """从 EC 读取当前 CPU/GPU 风扇策略表.

        Returns:
            (cpu_fan_table, gpu_fan_table) 元组.
        """
        cpu_table = FanTable()
        gpu_table = FanTable()

        for i in range(FAN_TABLE_SIZE):
            cpu_table.Points[i].UpT   = self.driver.read_ec(FAN_CPU_UPT + i)
            cpu_table.Points[i].DownT = self.driver.read_ec(FAN_CPU_DOWNT + i)
            cpu_table.Points[i].Duty  = self.driver.read_ec(FAN_CPU_DUTY + i) / 2

            gpu_table.Points[i].UpT   = self.driver.read_ec(FAN_GPU_UPT + i)
            gpu_table.Points[i].DownT = self.driver.read_ec(FAN_GPU_DOWNT + i)
            gpu_table.Points[i].Duty  = self.driver.read_ec(FAN_GPU_DUTY + i) / 2

        return cpu_table, gpu_table

    def clear_all_fan_tables(self) -> None:
        """清空所有风扇策略表 (对应 C# ClearFanTable_Test)."""
        offsets = [0, 16, 32, 48, 64, 80]
        for i in range(FAN_TABLE_SIZE):
            for offset in offsets:
                self.driver.write_ec(FAN_CPU_UPT + offset + i, 0)

    def set_fan_switch_speed(self, speed: int) -> None:
        """设置风扇切换速度.

        EC 寄存器 1927: bit7=enable, bit6-0=speed (单位 100ms/PWM%步进).
        写入 0 恢复硬件默认值.

        Args:
            speed: 切换速度 (毫秒), 传 0 恢复默认. 自动按 100ms 对齐.
        """
        # TODO 也有说法是 500 毫秒
        speed //= 100
        if speed > 0:
            speed |= 0x80
            self.driver.write_ec(REG_FAN_SWITCH_SPEED, speed)
        else:
            self.driver.write_ec(REG_FAN_SWITCH_SPEED, 0)

    def get_fan_switch_speed(self) -> int:
        val = self.driver.read_ec(REG_FAN_SWITCH_SPEED)
        return 0 if val == 0 else (val & 0x7F) * 100

    def get_fan_speed(self) -> Tuple[float, int, float, int]:
        """读取风扇转速和 PWM Duty
        """
        cpu_speed = (self.driver.read_ec(REG_FAN1_RPM_HIGH) << 8) | self.driver.read_ec(REG_FAN1_RPM_LOW)
        gpu_speed = (self.driver.read_ec(REG_FAN2_RPM_HIGH) << 8) | self.driver.read_ec(REG_FAN2_RPM_LOW)
        cpu_duty  = self.driver.read_ec(REG_FAN1_DUTY) / 2
        gpu_duty  = self.driver.read_ec(REG_FAN2_DUTY) / 2

        return cpu_duty, cpu_speed, gpu_duty, gpu_speed

    def set_fan_table_enabled(self, enable: bool) -> None:
        val = self.driver.read_ec(REG_WHISPER_MODE_MAIN)

        if enable > 0:
            val |= 0x80
        else:
            val &= 0x7F

        self.driver.write_ec(REG_WHISPER_MODE_MAIN, val)

    def is_fan_table_enabled(self) -> bool:
        val = self.driver.read_ec(REG_WHISPER_MODE_MAIN) & 0x80
        return val != 0

    def load_fan_tables_from_json(self, path: str) -> Tuple[FanTable, FanTable]:
        """从 FanTable.json 格式文件加载 CPU 与 GPU 风扇策略表.

        Args:
            path: JSON 文件路径 (格式: {"CPU": [...], "GPU": [...]}).

        Returns:
            (cpu_fan_table, gpu_fan_table) 元组.
        """
        with open(path, "r") as f:
            data = json.load(f)
        cpu_table = FanTable.from_list(data.get("CPU", []))
        gpu_table = FanTable.from_list(data.get("GPU", []))
        return cpu_table, gpu_table

    def apply_fan_tables_to_ec(self, path: str) -> None:
        """从 FanTable.json 文件加载策略表并下发到 EC.

        Args:
            path: FanTable.json 文件路径.
        """
        cpu_table, gpu_table = self.load_fan_tables_from_json(path)
        self.set_cpu_fan_table(cpu_table)
        self.set_gpu_fan_table(gpu_table)



# ============================================================
# EC 业务逻辑层
# ============================================================

class MyEcCtrl:
    """EC 寄存器高级操作, 对应 C# 中的 MyEcCtrl.

    封装了常用 EC 寄存器的读写, 包括 CPU 功耗,
    GPU 控制, LED 灯效, 按键锁定等业务逻辑.
    """

    def __init__(self, driver: Optional[AcpiDriver] = None):
        self.driver = driver or AcpiDriver()

    # ── 基础信息 ────────────────────────────────────────

    def get_project_id(self) -> int:
        """获取项目 ID (寄存器 1856).

        Returns:
            项目 ID (0-255).
        """
        return self.driver.read_ec(REG_PROJECT_ID) & 0xFF

    def is_china_mode(self) -> bool:
        """检测是否为中国区模式 (寄存器 1894 bit4).

        Returns:
            True 表示中国区模式.
        """
        val = self.driver.read_ec(REG_GLOBAL_CONFIG)
        return (val >> 4) & 1 == 1

    def get_adapter_watt(self) -> int:
        """解析适配器功率 (寄存器 1183, 对应 C# GetAdapterWattFromEC).

        Returns:
            适配器额定功率 (W).
        """
        b = self.driver.read_ec(REG_ADAPTER_WATT) & 0x78
        mapping = {
            0: 330, 8: 230, 16: 180, 24: 150,
            32: 120, 40: 90, 48: 65, 56: 40, 64: 280,
        }
        return mapping.get(b, 150)

    def get_typec_status(self) -> int:
        """获取 Type-C 接口状态 (寄存器 1996 & 0x36).

        Returns:
            Type-C 状态值.
        """
        return self.driver.read_ec(REG_TYPEC_STATUS) & 0x36

    # ── GPU 信息 ─────────────────────────────────────────

    # 用不了所以加前缀了

    def _get_gpu_freq(self) -> int:
        """获取 GPU 核心频率 (寄存器 3403).

        Returns:
            GPU 核心频率 (MHz).
        """
        return self.driver.read_ec(REG_GPU_FREQ)

    def _get_gpu_mem_freq(self) -> int:
        """获取 GPU 显存频率 (寄存器 3404 + 3405 bit6-0).

        Returns:
            GPU 显存频率 (MHz).
        """
        val_high = self.driver.read_ec(REG_GPU_MEM_FREQ_HIGH) & 0x7F
        val_low  = self.driver.read_ec(REG_GPU_MEM_FREQ_LOW) & 0xFF
        return 256 * val_high + val_low

    def get_ap_exist(self) -> int:
        """获取应用存在标志 (寄存器 1857 bit0).

        Returns:
            0 或 1.
        """
        return self.driver.read_ec(REG_AP_EXIST) & 1

    def set_ap_exist(self, exists: bool) -> None:
        """设置应用存在标志 (寄存器 1857 bit0).

        Args:
            exists: True 置位, False 清除.
        """
        val = self.driver.read_ec(REG_AP_EXIST)
        if exists:
            val |= 1
        else:
            val &= 0xFE
        self.driver.write_ec(REG_AP_EXIST, val)

    # ── CPU 功耗 ─────────────────────────────────────────

    def get_cpu_power(self) -> Tuple[int, int, int]:
        """读取 CPU PL1/PL2/PL4 功率限制.

        Returns:
            (pl1, pl2, pl4) 元组, 单位 W.
        """
        pl1 = self.driver.read_ec(REG_CPU_PL1)
        pl2 = self.driver.read_ec(REG_CPU_PL2)
        pl4 = self.driver.read_ec(REG_CPU_PL4)
        return (pl1, pl2, pl4)

    def set_cpu_power(self, pl1: int, pl2: int, pl4: int) -> None:
        """设置 CPU PL1/PL2/PL4 功率限制.

        传入 0 恢复该路默认值.

        Args:
            pl1: PL1 功率 (W), 0 恢复默认.
            pl2: PL2 功率 (W), 0 恢复默认.
            pl4: PL4 功率 (W), 0 恢复默认.
        """
        self.driver.write_ec(REG_CPU_PL1, pl1 & 0xFF)
        self.driver.write_ec(REG_CPU_PL2, pl2 & 0xFF)
        self.driver.write_ec(REG_CPU_PL4, pl4 & 0xFF)

    def get_cpu_tcc(self) -> int:
        val = self.driver.read_ec(REG_CPU_TCC)
        return val & 0x7f if val & 0x80 else 0

    def set_cpu_tcc(self, tcc: int) -> None:
        """设置 CPU TCC 温度偏移 (降温度墙).

        bit7 为使能位, bit6-0 为偏移值 (单位摄氏度).
        传入 -1 恢复默认.

        Args:
            tcc: 温度偏移值 (0-127), -1 禁用.
        """
        if tcc != -1:
            tcc = (tcc & 0x7F) | 0x80
        else:
            tcc = 0
        self.driver.write_ec(REG_CPU_TCC, tcc)

    # ── GPU 控制 ─────────────────────────────────────────

    def set_gpu_d_state(self, dstate: int) -> None:
        """设置 GPU D-State (寄存器 1931 bit0-2).

        Args:
            dstate: 1 或 2, 具体含义待确认.
        """
        value = self.driver.read_ec(REG_GPU_D_STATE)
        value &= 0xF8
        value |= dstate & 0x07
        self.driver.write_ec(REG_GPU_D_STATE, value)

    def set_gpu_configurable_tgp_enable(self, enable: bool) -> None:
        """控制可配置 TGP (寄存器 1859 bit2).

        Args:
            enable: True 使能, False 禁用.
        """
        val = self.driver.read_ec(REG_GPU_TGP_CTRL)
        mask = 0xFB
        status_bit = 4 if enable else 0
        self.driver.write_ec(REG_GPU_TGP_CTRL, (val & mask) | status_bit)

    def set_gpu_configurable_tgp_increment(self, value: int) -> None:
        """设置 TGP 增加量 (寄存器 1860).

        Args:
            value: 相对默认 TGP 增加值 (W).
        """
        self.driver.write_ec(REG_GPU_TGP_OFFSET, value)

    def set_gpu_dynamic_boost_enable(self, status: int) -> None:
        """动态加速开关 (寄存器 1859 bit1).

        Args:
            status: 1 开启, 0 关闭.
        """
        val = self.driver.read_ec(REG_GPU_TGP_CTRL)
        mask = 0xFD
        bit = 2 if status == 1 else 0
        self.driver.write_ec(REG_GPU_TGP_CTRL, (val & mask) | bit)

    def set_gpu_dynamic_boost_tgp_limit(self, max_tgp: int) -> None:
        """设置 Dynamic Boost 最大 TGP (寄存器 1862).

        Args:
            max_tgp: 最大 TGP (W), 0-255.
        """
        self.driver.write_ec(REG_DYNAMIC_BOOST_MAX, max_tgp & 0xFF)

    # ── LED / 灯光 ───────────────────────────────────────

    def set_power_led_color(self, mode: int) -> None:
        """设置电源指示灯颜色 (寄存器 1957 bit0-1).

        Args:
            mode: 0-3, 具体颜色映射由 EC 固件定义.
        """
        value = self.driver.read_ec(REG_POWER_LED)
        value &= 0xFC
        value |= mode & 0x03
        self.driver.write_ec(REG_POWER_LED, value)

    def set_touchpad_led_status(self, status: int) -> None:
        """控制触摸板 LED 指示灯 (寄存器 1958 bit3).

        对应 C# UserSetTouchPadLedStatus.

        Args:
            status: 1 点亮, 0 熄灭.
        """
        val = self.driver.read_ec(REG_TOUCHPAD)
        if status == 1:
            val |= 0x08
        else:
            val &= 0xF7
        self.driver.write_ec(REG_TOUCHPAD, val)

    def get_lightbar_status(self) -> bool:
        """获取灯带状态 (寄存器 1896 bit1).

        对应 C# GetStatus_LightBar.

        Returns:
            True 表示灯带开启.
        """
        b = self.driver.read_ec(REG_STATUS_FLAGS)
        return (b & 0x02) == 0x02

    def _lightbar_trigger(self) -> None:
        """触发灯带状态切换 (寄存器 1895).

        对应 C# LightBar_Trigger: 清除 bit1 后写入.
        """
        val = self.driver.read_ec(REG_TRIGGER)
        b = val & 0xFD           # 清除 bit1
        self.driver.write_ec(REG_TRIGGER, 2 + b)

    def get_keyboard_backlight(self) -> int:
        """0 to 2
        """
        val = self.driver.read_ec(REG_KEYBOARD_BACKLIGHT)
        return (val >> 5)

    def set_keyboard_backlight(self, status: int) -> None:
        val = self.driver.read_ec(REG_KEYBOARD_BACKLIGHT)
        val |= 16
        val &= 31
        val |= (status & 7) << 5
        self.driver.write_ec(REG_KEYBOARD_BACKLIGHT, val)

    # ── USB 充电 ─────────────────────────────────────────

    def set_battery_mode(self, mode: int) -> None:
        # https://gist.github.com/w568w/957976b59906e0ce5d6c13ad342e1593
        # 这里控制的是单体电压与最大电压的差值，但具体数值还和电池温度有关，温度越低，电压越高
        # 0 = 长续航 (-50mV)
        # 1 = 标准   (-100mV)
        # 2 = 工作站 (-200mV)
        if mode < 0 or mode > 2:
            return
        val = self.driver.read_ec(REG_TOUCHPAD) & 0xC7
        val |= 0x08
        val |= mode << 4
        self.driver.write_ec(REG_TOUCHPAD, mode)

    def get_battery_max_voltage(self) -> int:
        return (self.driver.read_ec(REG_BATTERY_VOLT_HIGH) << 8) | self.driver.read_ec(REG_BATTERY_VOLT_LOW)

    def get_battery_limit(self) -> int:
        gate = self.driver.read_ec(0x0742) & 0x04
        if not gate:
            return 0

        return self.driver.read_ec(REG_BATTERY_CHARGE_LIMIT) & 0x7F

    def set_battery_limit(self, percent: int, use_blog_workaround: bool = False) -> int | None:
        if percent < 0 or percent > 100:
            return

        self.driver.write_ec(REG_BATTERY_CHARGE_LIMIT, percent)

        gate = self.driver.read_ec(0x0742) & 0x04
        if gate or not use_blog_workaround:
            return

        val1 = self.driver.read_ec(0x07C3)
        print(f"0x07C3 is {val1}")
        if val1 == 4 or val1 == 5:
            return

        val2 = self.driver.read_ec(0x0770)
        print(f"0x0770 is {val2}")
        if val2 == 4 or val2 == 5:
            return

        self.driver.write_ec(0x07C3, 4)
        time.sleep(2)
        self.driver.write_ec(0x07C3, val1)
        time.sleep(2)

        return self.driver.read_ec(0x0742) & 0x04

    def set_usb_charger_on(self, status: bool) -> None:
        """开关 USB 关机充电功能 (寄存器 1895 bit4).

        对应 C# USB_Charger_ON/OFF.
        """
        val = self.driver.read_ec(REG_TRIGGER)
        if status:
            val |= 0x10
        else:
            val &= 0xEF
        self.driver.write_ec(REG_TRIGGER, val)

    # ── WinKey / 按键锁定 ────────────────────────────────

    def set_win_key(self, status: int) -> None:
        """控制 Windows 键锁定 (寄存器 1896 bit0 + 触发).

        通过检测 bit0 状态决定是否需要发送触发信号.
        对应 C# SetWinKey.

        Args:
            status: 0 锁定 WinKey, 1 解锁 WinKey.
        """
        b = self.driver.read_ec(REG_STATUS_FLAGS)
        if status == 0:
            if (b & 0x01) != 0:
                self._win_key_lock_trigger()
        else:
            if (b & 0x01) != 1:
                self._win_key_lock_trigger()

    def _win_key_lock_trigger(self) -> None:
        """WinKey 锁定触发信号 (寄存器 1895).

        对应 C# WinKeyLock_Trigger: 清除 bit0 后写入.
        """
        val = self.driver.read_ec(REG_TRIGGER)
        b = val & 0xFE           # 清除 bit0
        self.driver.write_ec(REG_TRIGGER, 1 + b)

    # ── 触摸板开关 ───────────────────────────────────────

    def set_touchpad_on(self, status: bool) -> None:
        """开关触摸板 (寄存器 1958 bit6).

        对应 C# TouchpadToggle_ON/OFF.

        Args:
            status: 1 开启, 0 关闭.
        """
        val = self.driver.read_ec(REG_TOUCHPAD)
        if status:
            val &= 0xBF
        else:
            val |= 0x40
        self.driver.write_ec(REG_TOUCHPAD, val)

    # ── Fn 键 ────────────────────────────────────────────

    def set_fn_key(self, status: bool) -> None:
        """设置 Fn 键模式 (寄存器 1870 bit4).

        对应 C# SetFnKey.

        Args:
            status: 1 开启, 0 关闭.
        """
        val = self.driver.read_ec(REG_FN_KEY_CTRL)
        if status == 1:
            val |= 0x10
        else:
            val &= 0xEF
        self.driver.write_ec(REG_FN_KEY_CTRL, val)

    # ── AC Recovery ──────────────────────────────────────

    def set_ac_recovery_switch(self, status: bool) -> None:
        """设置 AC Recovery (EC 路径, 寄存器 1830 bit3).

        当固件不支持 NVRAM 路径时, 通过 EC 控制 AC Recovery.
        对应 C# UserSetAcRecoverySwitch (EC 分支).

        Args:
            status: 1 开启, 0 关闭.
        """
        b = self.driver.read_ec(REG_AC_RECOVERY_EC)
        if status:
            b |= 0x08
        else:
            b &= 0xF7
        self.driver.write_ec(REG_AC_RECOVERY_EC, b)

    # ── 默认值读取 ───────────────────────────────────────

    def get_default_power(self, mode_addr: int) -> Tuple[int, int, int, int]:
        """从连续 4 个寄存器读取默认功耗配置.

        1840: gaming, 1844: office, 1959: turbo.

        Args:
            mode_addr: 模式对应的起始寄存器地址.

        Returns:
            (pl1, pl2, pl4, dstate) 元组.
        """
        pl1 = self.driver.read_ec(mode_addr)
        pl2 = self.driver.read_ec(mode_addr + 1)
        pl4 = self.driver.read_ec(mode_addr + 2)
        dstate = self.driver.read_ec(mode_addr + 3)
        return (pl1, pl2, pl4, dstate)

    def get_default_tcc(self, mode: int) -> int:
        """获取指定模式的默认 TCC 值.

        Args:
            mode: 0=gaming, 1=office, 2=turbo.

        Returns:
            默认 TCC 偏移值, 失败返回 0.
        """
        tcc_map = {
            0: REG_DEFAULT_TCC_GAMING,
            1: REG_DEFAULT_TCC_OFFICE,
            2: REG_DEFAULT_TCC_TURBO,
        }
        addr = tcc_map.get(mode)
        if addr is not None:
            return self.driver.read_ec(addr)
        return 0

    def get_office_fan_abnormal_protect(self) -> bool:
        return (self.driver.read_ec(REG_WHISPER_MODE_MAIN) & 0x10) != 0

    # ── Support Byte ─────────────────────────────────────

    def write_support_byte(self) -> None:
        """写入 Support Byte (寄存器 1894 bit0-1 置位).

        对应 C# Write_Support_BYTE: 将 1894 的值与 3 做 OR.
        """
        val = self.driver.read_ec(REG_GLOBAL_CONFIG)
        self.driver.write_ec(REG_GLOBAL_CONFIG, val | 0x03)

    # ── Whisper Mode ─────────────────────────────────────

    def set_whisper_mode_main_switch(self, status: int) -> None:
        """EC 端 Whisper Mode 主开关 (寄存器 1989).

        Args:
            status: 1 开启, 0 关闭.
        """
        val = self.driver.read_ec(REG_WHISPER_MODE_MAIN)
        mask = 0x9F
        if status == 1:
            bit_data = 0x60
        else:
            self._disable_whisper_mode_status()
            bit_data = 0x40
        self.driver.write_ec(REG_WHISPER_MODE_MAIN, (val & mask) | bit_data)

    def _disable_whisper_mode_status(self) -> None:
        """清除 Whisper Mode 状态标志 (寄存器 1990 bit0-1)."""
        val = self.driver.read_ec(REG_WHISPER_MODE_STATUS)
        self.driver.write_ec(REG_WHISPER_MODE_STATUS, val & 0xFC)

    def get_whisper_mode_status(self) -> int:
        """从 EC 读取 Whisper Mode 当前状态 (寄存器 1990 bit0-1).

        Returns:
            -1=未知, 0/1/2 对应不同模式.
        """
        val = self.driver.read_ec(REG_WHISPER_MODE_STATUS) & 0x03
        mapping = {0: -1, 1: 2, 2: 1, 3: 0}
        return mapping.get(val, -1)


    def get_turbo_mode_support(self) -> bool:
        val = self.driver.read_ec(1183) & (1 << 1)
        return val != 0
    def get_antioc_support(self) -> bool:
        val = self.driver.read_ec(1994) & (1 << 3)
        return val != 0
    def get_fan1p5_support(self) -> bool:
        val = self.driver.read_ec(1934) & (1 << 6)
        return val != 0
    def get_lc_fan_table_support(self) -> bool:
        val = self.driver.read_ec(1992) & (1 << 5)
        return val != 0

# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    ec = MyEcCtrl()
    fan = MyEcFanCtrl()

    print(f"Project ID:    {ec.get_project_id()}")
    print(f"Is China Mode: {ec.is_china_mode()}")
    print(f"Adapter Watt:  {ec.get_adapter_watt()}W")
    print(f"GPU Core Freq: {ec.get_gpu_freq()} MHz")
    print(f"GPU Mem Freq:  {ec.get_gpu_mem_freq()} MHz")

    pl1, pl2, pl4 = ec.get_cpu_power()
    print(f"CPU PL1={pl1}W, PL2={pl2}W, PL4={pl4}W")

    # 备份当前 EC 风扇策略表
    # fan.save_fan_tables_to_json(path="./", fan_mode=1)
