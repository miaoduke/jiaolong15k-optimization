#!/usr/bin/env python3
"""
charge_tool.py - 电池充电阈值控制工具
适用于蛟龙15K (GM5BG0E) 及其他支持 sysfs charge_control_end_threshold 的设备
支持模拟模式用于测试

用法:
  python charge_tool.py set <1-100>    设置充电上限百分比
  python charge_tool.py reset          恢复默认充电（充到100%）
  python charge_tool.py status         查看当前充电限制状态
  python charge_tool.py interactive    交互式菜单模式
  python charge_tool.py simulate       进入模拟模式（测试环境）

模拟模式：在当前目录创建 simulation 目录模拟 sysfs 接口
"""

import os
import sys
import argparse
import logging

def wait_for_user(prompt="按回车键退出..."):
    """等待用户输入，但仅在交互式终端下"""
    if sys.stdin.isatty():
        try:
            input(prompt)
        except EOFError:
            pass
from pathlib import Path
from typing import Optional, Union

class BatteryChargeManager:
    """电池充电阈值管理器"""
    
    def __init__(self, simulate: bool = False, log_file: Optional[str] = None):
        """
        初始化管理器
        
        Args:
            simulate: 是否使用模拟模式（用于测试）
            log_file: 日志文件路径，None 则不记录到文件
        """
        self.simulate = simulate
        self.sim_dir = Path("./simulation")
        
        # 配置日志
        self.logger = logging.getLogger("charge_tool")
        self.logger.setLevel(logging.DEBUG)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # 文件处理器（如果指定）
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
        
        # 模拟模式下创建目录结构
        if simulate:
            self._setup_simulation()
    
    def _setup_simulation(self):
        """设置模拟环境"""
        self.sim_dir.mkdir(exist_ok=True)
        
        # 创建模拟的 sysfs 目录结构
        bat_dir = self.sim_dir / "class" / "power_supply" / "BAT0"
        bat_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建阈值文件，默认为100
        threshold_file = bat_dir / "charge_control_end_threshold"
        if not threshold_file.exists():
            threshold_file.write_text("100")
        
        # 创建其他模拟文件
        capacity_file = bat_dir / "capacity"
        if not capacity_file.exists():
            capacity_file.write_text("85")
        
        status_file = bat_dir / "status"
        if not status_file.exists():
            status_file.write_text("Charging")
        
        self.logger.debug(f"模拟环境已创建: {self.sim_dir}")
    
    def _get_sysfs_path(self) -> Path:
        """获取 sysfs 阈值文件路径"""
        if self.simulate:
            return self.sim_dir / "class" / "power_supply" / "BAT0" / "charge_control_end_threshold"
        else:
            return Path("/sys/class/power_supply/BAT0/charge_control_end_threshold")
    
    def _read_threshold(self) -> Optional[int]:
        """读取当前阈值"""
        try:
            path = self._get_sysfs_path()
            if path.exists():
                content = path.read_text().strip()
                return int(content)
            else:
                self.logger.error(f"无法读取阈值文件: {path}")
                return None
        except (ValueError, IOError) as e:
            self.logger.error(f"读取阈值失败: {e}")
            return None
    
    def _write_threshold(self, value: int) -> bool:
        """写入新阈值"""
        try:
            path = self._get_sysfs_path()
            if path.exists():
                path.write_text(str(value))
                self.logger.debug(f"已写入阈值 {value} 到 {path}")
                return True
            else:
                self.logger.error(f"无法写入阈值文件: {path}")
                return False
        except IOError as e:
            self.logger.error(f"写入阈值失败: {e}")
            return False
    
    def set_threshold(self, percent: int) -> bool:
        """
        设置充电上限阈值
        
        Args:
            percent: 百分比 (1-100)
            
        Returns:
            bool: 是否成功
        """
        if not 1 <= percent <= 100:
            self.logger.error("阈值必须在 1-100 之间")
            return False
        
        if self.simulate:
            self.logger.info(f"[模拟] 设置充电上限为 {percent}%")
        else:
            self.logger.info(f"设置充电上限为 {percent}%")
        
        if self._write_threshold(percent):
            # 验证写入是否成功
            readback = self._read_threshold()
            if readback == percent:
                self.logger.info(f"✓ 阈值已成功设置为 {percent}%")
                return True
            else:
                self.logger.warning(f"⚠ 阈值写入后读回不一致: 写入 {percent}, 读回 {readback}")
                return False
        return False
    
    def reset(self) -> bool:
        """
        重置为默认充电（充到100%）
        
        Returns:
            bool: 是否成功
        """
        if self.simulate:
            self.logger.info("[模拟] 重置充电阈值为 100%")
        else:
            self.logger.info("重置充电阈值为 100%")
        
        return self.set_threshold(100)
    
    def status(self) -> dict:
        """
        获取当前充电状态
        
        Returns:
            dict: 状态信息
        """
        info = {
            "threshold": None,
            "capacity": None,
            "status": None,
            "simulated": self.simulate,
            "sysfs_path": str(self._get_sysfs_path())
        }
        
        # 读取阈值
        info["threshold"] = self._read_threshold()
        
        # 在模拟模式下读取其他信息
        if self.simulate:
            try:
                capacity_path = self.sim_dir / "class" / "power_supply" / "BAT0" / "capacity"
                if capacity_path.exists():
                    info["capacity"] = int(capacity_path.read_text().strip())
                
                status_path = self.sim_dir / "class" / "power_supply" / "BAT0" / "status"
                if status_path.exists():
                    info["status"] = status_path.read_text().strip()
            except (ValueError, IOError):
                pass
        
        return info
    
    def print_status(self):
        """打印状态信息"""
        info = self.status()
        
        print("=" * 50)
        print("电池充电阈值状态")
        print("=" * 50)
        
        if info["simulated"]:
            print("[模拟] 运行模式: 模拟 (测试环境)")
        else:
            print("[实际] 运行模式: 实际硬件")
        
        print(f"sysfs 路径: {info['sysfs_path']}")
        
        if info["threshold"] is not None:
            print(f"充电上限阈值: {info['threshold']}%")
            if info["threshold"] == 100:
                print("  (无限制，充电到100%)")
            else:
                print(f"  (充电到 {info['threshold']}% 后停止)")
        else:
            print("充电上限阈值: 不可用")
        
        if info["capacity"] is not None:
            print(f"当前电量: {info['capacity']}%")
        
        if info["status"] is not None:
            print(f"充电状态: {info['status']}")
        
        print("=" * 50)

def interactive_menu(manager: BatteryChargeManager):
    """交互式菜单"""
    print("\n" + "="*50)
    print("蛟龙15K 充电阈值控制工具 (交互模式)")
    print("="*50)
    
    while True:
        print("\n可用命令:")
        print("  1. 查看当前状态")
        print("  2. 设置充电阈值")
        print("  3. 重置为默认 (100%)")
        print("  4. 模拟充电过程")
        print("  5. 退出")
        
        choice = input("\n请选择 (1-5): ").strip()
        
        if choice == '1':
            manager.print_status()
        
        elif choice == '2':
            try:
                percent = int(input("输入充电上限百分比 (1-100): ").strip())
                if manager.set_threshold(percent):
                    print(f"✓ 阈值已设置为 {percent}%")
                else:
                    print("✗ 设置失败")
            except ValueError:
                print("✗ 请输入有效的数字")
        
        elif choice == '3':
            if manager.reset():
                print("✓ 已重置为 100%")
            else:
                print("✗ 重置失败")
        
        elif choice == '4':
            if not manager.simulate:
                print("模拟功能仅在模拟模式下可用")
                continue
            
            print("模拟充电过程:")
            print("1. 充电到阈值后停止")
            print("2. 模拟电量变化")
            
            sim_choice = input("选择模拟类型 (1-2): ").strip()
            
            if sim_choice == '1':
                # 模拟充电到阈值
                threshold = manager._read_threshold()
                if threshold is None:
                    print("无法读取当前阈值")
                    continue
                
                # 模拟电量从0到阈值
                capacity_path = manager.sim_dir / "class" / "power_supply" / "BAT0" / "capacity"
                status_path = manager.sim_dir / "class" / "power_supply" / "BAT0" / "status"
                
                for cap in range(0, threshold + 5, 5):
                    if cap > 100:
                        cap = 100
                    
                    capacity_path.write_text(str(cap))
                    
                    if cap < threshold:
                        status_path.write_text("Charging")
                        status = "充电中"
                    elif cap == threshold:
                        status_path.write_text("Full")
                        status = "已充满（达到阈值）"
                    else:
                        status_path.write_text("Not charging")
                        status = "停止充电（超过阈值）"
                    
                    print(f"电量: {cap}% - {status}")
                
                print(f"模拟完成: 充电到 {threshold}% 后停止")
            
            elif sim_choice == '2':
                # 模拟电量变化
                capacity_path = manager.sim_dir / "class" / "power_supply" / "BAT0" / "capacity"
                
                print("模拟电量变化（输入 q 退出）:")
                while True:
                    try:
                        current = int(capacity_path.read_text().strip())
                        print(f"当前电量: {current}%")
                        new_val = input("输入新电量 (0-100): ").strip()
                        
                        if new_val.lower() == 'q':
                            break
                        
                        new_cap = int(new_val)
                        if 0 <= new_cap <= 100:
                            capacity_path.write_text(str(new_cap))
                            print(f"电量已更新为 {new_cap}%")
                        else:
                            print("请输入 0-100 之间的数值")
                    except ValueError:
                        print("请输入有效的数字或 q 退出")
                    except KeyboardInterrupt:
                        print("\n退出模拟")
                        break
        
        elif choice == '5':
            print("退出工具")
            break
        
        else:
            print("无效选择，请重新输入")

def simulate_test():
    """运行模拟测试"""
    print("=" * 60)
    print("充电阈值控制工具 - 模拟测试")
    print("=" * 60)
    
    # 创建模拟管理器
    manager = BatteryChargeManager(simulate=True)
    
    # 测试1: 查看初始状态
    print("\n[测试1] 初始状态:")
    manager.print_status()
    
    # 测试2: 设置阈值为80%
    print("\n[测试2] 设置阈值为80%:")
    if manager.set_threshold(80):
        manager.print_status()
    else:
        print("测试失败")
    
    # 测试3: 设置阈值为50%
    print("\n[测试3] 设置阈值为50%:")
    manager.set_threshold(50)
    manager.print_status()
    
    # 测试4: 尝试无效值
    print("\n[测试4] 尝试无效值 (150%):")
    manager.set_threshold(150)
    
    print("\n[测试5] 尝试无效值 (0%):")
    manager.set_threshold(0)
    
    # 测试6: 重置
    print("\n[测试6] 重置为100%:")
    manager.reset()
    manager.print_status()
    
    # 测试7: 验证模拟文件
    print("\n[测试7] 验证模拟文件:")
    threshold_file = manager.sim_dir / "class" / "power_supply" / "BAT0" / "charge_control_end_threshold"
    print(f"阈值文件路径: {threshold_file}")
    print(f"文件内容: {threshold_file.read_text().strip()}")
    print(f"文件存在: {threshold_file.exists()}")
    
    print("\n" + "=" * 60)
    print("模拟测试完成")
    print("=" * 60)
    wait_for_user()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="电池充电阈值控制工具 - 蛟龙15K (GM5BG0E)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s set 80        设置充电上限为80%%
  %(prog)s reset         恢复默认（充电到100%%）
  %(prog)s status        查看当前状态
  %(prog)s interactive   进入交互模式
  %(prog)s simulate      运行模拟测试
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # set 命令
    set_parser = subparsers.add_parser("set", help="设置充电上限阈值")
    set_parser.add_argument("percent", type=int, help="充电上限百分比 (1-100)")
    set_parser.add_argument("--simulate", action="store_true", help="使用模拟模式")
    
    # reset 命令
    reset_parser = subparsers.add_parser("reset", help="重置为默认充电")
    reset_parser.add_argument("--simulate", action="store_true", help="使用模拟模式")
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查看充电限制状态")
    status_parser.add_argument("--simulate", action="store_true", help="使用模拟模式")
    
    # interactive 命令
    interactive_parser = subparsers.add_parser("interactive", help="交互式菜单")
    interactive_parser.add_argument("--simulate", action="store_true", help="使用模拟模式")
    
    # simulate 命令
    simulate_parser = subparsers.add_parser("simulate", help="运行模拟测试")
    
    args = parser.parse_args()
    
    # 平台检测：非Linux系统无法访问真实sysfs接口，自动切换到模拟模式
    is_linux = sys.platform.startswith('linux')
    if not is_linux and args.command != "simulate":
        print("提示: 当前系统不是Linux，无法访问真实的充电阈值接口(sysfs)。")
        print("      已自动切换到模拟模式。模拟模式不会修改真实硬件。")
        print("      如需控制真实电池，请在Linux系统上运行本工具。")
    
    if args.command == "simulate":
        simulate_test()
        return
    
    if args.command is None:
        # 无参数时进入交互模式
        print("未指定命令，进入交互式模式...")
        manager = BatteryChargeManager(simulate=not is_linux)
        interactive_menu(manager)
        return
    
    # 确定是否使用模拟模式
    simulate = getattr(args, "simulate", False)
    if not is_linux:
        simulate = True  # 非Linux系统强制模拟模式
    
    # 创建管理器
    manager = BatteryChargeManager(simulate=simulate)
    
    # 执行命令
    if args.command == "set":
        success = manager.set_threshold(args.percent)
        wait_for_user()
        sys.exit(0 if success else 1)
    
    elif args.command == "reset":
        success = manager.reset()
        wait_for_user()
        sys.exit(0 if success else 1)
    
    elif args.command == "status":
        manager.print_status()
        wait_for_user()
    
    elif args.command == "interactive":
        interactive_menu(manager)

if __name__ == "__main__":
    main()