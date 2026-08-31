# -*- coding: utf-8 -*-
"""
GPU低功耗模式控制脚本
通过EC寄存器启用GPU低功耗模式
"""
import sys
import os
import ctypes

# 检查管理员权限
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# 以管理员身份运行
def run_as_admin():
    if not is_admin():
        print("需要管理员权限！正在请求提升...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit(0)

def main():
    run_as_admin()
    
    print("=== GPU低功耗模式控制 ===")
    
    # 添加路径 - 使用绝对路径
    sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
    
    try:
        from mr_ec_hw import ec_read, ec_write
        
        print("\n1. 当前GPU状态:")
        try:
            gpu_temp = ec_read(0x200)  # GPU温度
            gpu_fan = ec_read(0x204)   # GPU风扇
            print(f"   GPU温度: {gpu_temp}°C")
            print(f"   GPU风扇: {gpu_fan}%")
        except Exception as e:
            print(f"   读取GPU状态失败: {e}")
        
        print("\n2. 启用GPU低功耗模式:")
        try:
            # 读取当前0x26寄存器
            current = ec_read(0x26)
            print(f"   当前0x26值: {current:#04x}")
            
            # 设置bit7 (GPU低功耗模式)
            new_val = current | 0x80  # bit7=1
            ec_write(0x26, new_val)
            print(f"   新0x26值: {new_val:#04x}")
            print("   GPU低功耗模式已启用")
            
        except Exception as e:
            print(f"   设置GPU低功耗失败: {e}")
        
        print("\n3. 验证设置:")
        try:
            current = ec_read(0x26)
            print(f"   当前0x26值: {current:#04x}")
            print(f"   bit7 (GPU低功耗): {(current >> 7) & 1}")
        except Exception as e:
            print(f"   验证失败: {e}")
            
    except ImportError as e:
        print(f"导入EC模块失败: {e}")
        print("请确保mr_ec_hw.py在正确位置")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    main()