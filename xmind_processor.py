#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xmind文件处理器
用于将.xmind文件重命名为.zip并解压
"""

import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
import json


class XmindProcessor:
    def __init__(self):
        self.original_file = "/Users/liangwenze/Downloads/TestTools/XmindCaseTest/测试.xmind"
        self.target_file = "/Users/liangwenze/Downloads/TestTools/XmindCaseTest/测试.zip"
        self.extract_dir = "/Users/liangwenze/Downloads/TestTools/XmindCaseTest/extracted_content"
        self.report = {
            "operation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "original_file_path": self.original_file,
            "modified_file_path": self.target_file,
            "extract_target_dir": self.extract_dir,
            "status": "pending",
            "error_message": "",
            "extracted_files": [],
            "operation_steps": []
        }
    
    def rename_file(self):
        """修改文件扩展名"""
        try:
            # 检查原始文件是否存在
            if not os.path.exists(self.original_file):
                raise FileNotFoundError(f"原始文件不存在: {self.original_file}")
            
            # 检查目标文件是否已存在
            if os.path.exists(self.target_file):
                print(f"目标文件已存在，正在删除: {self.target_file}")
                os.remove(self.target_file)
                self.report["operation_steps"].append("删除已存在的目标文件")
            
            # 执行重命名操作
            shutil.copy2(self.original_file, self.target_file)
            self.report["operation_steps"].append(f"文件扩展名修改成功: {os.path.basename(self.original_file)} -> {os.path.basename(self.target_file)}")
            print(f"✅ 文件扩展名修改成功: {self.original_file} -> {self.target_file}")
            return True
            
        except Exception as e:
            self.report["status"] = "failed"
            self.report["error_message"] = f"文件重命名失败: {str(e)}"
            print(f"❌ 文件重命名失败: {str(e)}")
            return False
    
    def verify_extension_change(self):
        """验证文件扩展名是否正确更改"""
        try:
            # 检查目标文件是否存在
            if not os.path.exists(self.target_file):
                raise FileNotFoundError(f"目标文件不存在: {self.target_file}")
            
            # 检查文件扩展名
            if not self.target_file.lower().endswith('.zip'):
                raise ValueError(f"目标文件扩展名不是.zip: {self.target_file}")
            
            # 检查文件大小是否合理
            file_size = os.path.getsize(self.target_file)
            if file_size == 0:
                raise ValueError("目标文件大小为0，可能复制失败")
            
            self.report["operation_steps"].append(f"文件扩展名验证成功，文件大小: {file_size} 字节")
            print(f"✅ 文件扩展名验证成功，文件大小: {file_size} 字节")
            return True
            
        except Exception as e:
            self.report["status"] = "failed"
            self.report["error_message"] = f"文件验证失败: {str(e)}"
            print(f"❌ 文件验证失败: {str(e)}")
            return False
    
    def extract_zip_content(self):
        """解压ZIP文件内容"""
        try:
            # 检查ZIP文件是否存在
            if not os.path.exists(self.target_file):
                raise FileNotFoundError(f"ZIP文件不存在: {self.target_file}")
            
            # 创建解压目录
            if os.path.exists(self.extract_dir):
                print(f"解压目录已存在，正在清理: {self.extract_dir}")
                shutil.rmtree(self.extract_dir)
                self.report["operation_steps"].append("清理已存在的解压目录")
            
            os.makedirs(self.extract_dir, exist_ok=True)
            self.report["operation_steps"].append(f"创建解压目录: {self.extract_dir}")
            
            # 解压ZIP文件
            with zipfile.ZipFile(self.target_file, 'r') as zip_ref:
                # 检查ZIP文件是否损坏
                if zip_ref.testzip() is not None:
                    raise zipfile.BadZipFile("ZIP文件损坏或包含错误")
                
                # 获取所有文件列表
                file_list = zip_ref.namelist()
                
                # 解压所有文件
                zip_ref.extractall(self.extract_dir)
                
                # 记录解压的文件
                self.report["extracted_files"] = file_list
                self.report["operation_steps"].append(f"成功解压 {len(file_list)} 个文件")
                
                print(f"✅ ZIP文件解压成功，共解压 {len(file_list)} 个文件")
                
                # 显示解压的文件列表
                print("📁 解压出的文件列表:")
                for i, file in enumerate(file_list, 1):
                    print(f"  {i}. {file}")
                
                return True
                
        except zipfile.BadZipFile as e:
            self.report["status"] = "failed"
            self.report["error_message"] = f"ZIP文件格式错误: {str(e)}"
            print(f"❌ ZIP文件格式错误: {str(e)}")
            return False
        except Exception as e:
            self.report["status"] = "failed"
            self.report["error_message"] = f"解压过程失败: {str(e)}"
            print(f"❌ 解压过程失败: {str(e)}")
            return False
    
    def generate_report(self):
        """生成操作结果报告"""
        if self.report["status"] == "pending":
            self.report["status"] = "success"
        
        # 添加文件系统信息
        try:
            if os.path.exists(self.target_file):
                self.report["file_size_bytes"] = os.path.getsize(self.target_file)
            
            if os.path.exists(self.extract_dir):
                # 计算解压目录中的文件总数
                total_files = 0
                for root, dirs, files in os.walk(self.extract_dir):
                    total_files += len(files)
                self.report["total_extracted_files"] = total_files
                
        except Exception:
            pass
        
        return self.report
    
    def save_report(self):
        """保存报告到JSON文件"""
        try:
            report_file = "/Users/liangwenze/Downloads/TestTools/XmindCaseTest/operation_report.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, ensure_ascii=False, indent=2)
            print(f"📄 操作报告已保存到: {report_file}")
        except Exception as e:
            print(f"⚠️  保存报告失败: {str(e)}")
    
    def print_final_report(self):
        """打印最终的操作结果报告"""
        print("\n" + "="*60)
        print("📋 操作结果报告")
        print("="*60)
        print(f"⏰ 操作时间: {self.report['operation_time']}")
        print(f"📁 原始文件路径: {self.report['original_file_path']}")
        print(f"📁 修改后文件路径: {self.report['modified_file_path']}")
        print(f"📂 解压目标目录: {self.report['extract_target_dir']}")
        print(f"📊 操作状态: {self.report['status']}")
        
        if self.report['status'] == 'success':
            print(f"📄 解压出的文件数量: {len(self.report['extracted_files'])}")
            if self.report['extracted_files']:
                print("📁 解压出的文件列表:")
                for i, file in enumerate(self.report['extracted_files'], 1):
                    print(f"  {i}. {file}")
        else:
            print(f"❌ 错误信息: {self.report['error_message']}")
        
        if self.report['operation_steps']:
            print("\n📝 操作步骤:")
            for i, step in enumerate(self.report['operation_steps'], 1):
                print(f"  {i}. {step}")
        
        print("="*60)
    
    def run(self):
        """运行完整的处理流程"""
        print("🚀 开始Xmind文件处理流程...")
        
        # 步骤1: 修改文件扩展名
        if not self.rename_file():
            self.generate_report()
            self.print_final_report()
            self.save_report()
            return False
        
        # 步骤2: 验证文件扩展名
        if not self.verify_extension_change():
            self.generate_report()
            self.print_final_report()
            self.save_report()
            return False
        
        # 步骤3: 解压ZIP文件
        if not self.extract_zip_content():
            self.generate_report()
            self.print_final_report()
            self.save_report()
            return False
        
        # 生成最终报告
        # self.generate_report()
        self.print_final_report()
        # self.save_report()
        
        print("✅ 所有操作成功完成！")
        return True


def main():
    """主函数"""
    try:
        processor = XmindProcessor()
        success = processor.run()
        
        if success:
            print("\n🎉 Xmind文件处理成功完成！")
            return 0
        else:
            print("\n💥 Xmind文件处理失败！")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  操作被用户中断")
        return 1
    except Exception as e:
        print(f"\n💥 发生未预期的错误: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())