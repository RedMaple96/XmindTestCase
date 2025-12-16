# XmindTestCase - XMind测试用例转换工具

<div align="center">

[![Python Version](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/RedMaple96/XmindTestCase?style=social)](https://github.com/RedMaple96/XmindTestCase)

</div>

---

## 项目概述

本项目是基于 [zhuifengshen/xmind2testcase](https://github.com/zhuifengshen/xmind2testcase) 开源项目的二次开发版本，旨在提供更高效、更稳定的XMind测试用例转换解决方案。

### 🚀 主要改进特性

- **🔧 独立XMind解析器**：完全自主研发的XMind文件解析器，摆脱对xmind库的依赖（支持新版本xmind文件）
- **⚡ 性能优化**：引入缓存机制和并行处理，大幅提升大文件处理速度
- **🛡️ 增强错误处理**：完善的异常捕获和详细的错误报告机制
- **📊 调试支持**：提供详细的性能统计和调试信息
- **🎨 现代化界面**：改进的Web界面和用户体验


---

## 安装指南

### 📋 系统要求

- **Python版本**: 3.6 或更高版本
- **操作系统**: Windows、macOS、Linux
- **内存要求**: 至少 2GB RAM（推荐 4GB+）
- **磁盘空间**: 至少 500MB 可用空间

### 🛠️ 安装步骤

#### 方式一：通过pip安装（推荐）

```bash
# 安装稳定版本
pip install xmind-testcase

# 或安装开发版本
pip install git+https://github.com/RedMaple96/XmindTestCase.git
```

#### 方式二：从源码安装

```bash
# 克隆仓库
git clone https://github.com/RedMaple96/XmindTestCase.git
cd XmindTestCase

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装项目
pip install -e .
```

### 🔧 依赖库

主要依赖库及其版本要求：

```
flask>=2.0.0
arrow>=1.0.0
xmind>=1.0.0  # 可选，用于向后兼容
```

### ⚠️ 常见问题解决

#### 1. 安装失败
```bash
# 升级pip
pip install --upgrade pip

# 使用国内镜像源
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple xmind-testcase
```

#### 2. 权限问题
```bash
# Linux/macOS用户可能需要sudo
sudo pip install xmind-testcase

# 或为用户安装
pip install --user xmind-testcase
```

#### 3. 依赖冲突
```bash
# 创建干净的虚拟环境
python -m venv clean_env
source clean_env/bin/activate
pip install xmind-testcase
```

---

## 使用说明

### 🎯 快速开始

#### 命令行使用

```bash
# 转换XMind文件到所有格式
xmind-testcase /path/to/testcase.xmind

# 只转换为CSV格式
xmind-testcase /path/to/testcase.xmind -csv

# 只转换为XML格式（TestLink）
xmind-testcase /path/to/testcase.xmind -xml

# 只转换为JSON格式
xmind-testcase /path/to/testcase.xmind -json

# 启用调试模式
xmind-testcase /path/to/testcase.xmind --debug
```

#### Web界面使用

```bash
# 启动Web服务（默认端口5001）
xmind-testcase webtool

# 指定端口
xmind-testcase webtool 8080
```

访问 http://localhost:5001 即可使用Web界面。

#### Python API使用

```python
import json
from xmind_testcase import XmindLoader, XmindToZentao, XmindToTestlink

# 加载XMind文件
loader = XmindLoader()
workbook = loader.load('test.xmind')

# 转换为禅道格式
zentao_converter = XmindToZentao()
zentao_csv = zentao_converter.convert(workbook)

# 转换为TestLink格式
testlink_converter = XmindToTestlink()
testlink_xml = testlink_converter.convert(workbook)

# 保存结果
with open('testcase.csv', 'w', encoding='utf-8') as f:
    f.write(zentao_csv)
```

### 📖 配置文件说明

创建 `config.json` 文件来自定义转换行为：

```json
{
  "conversion": {
    "default_priority": "中",
    "default_execution_type": "手动",
    "separator": " ",
    "enable_cache": true,
    "cache_size": 100
  },
  "output": {
    "encoding": "utf-8",
    "csv_delimiter": ",",
    "xml_format": true,
    "json_indent": 2
  },
  "debug": {
    "enable": false,
    "log_level": "INFO",
    "save_temp_files": false
  }
}
```

### 🎨 XMind模板规则

请遵循以下规则创建XMind测试用例：

1. **中心主题**：产品名称
2. **第一层子主题**：测试套件（TestSuite）
3. **第二层子主题**：测试用例（TestCase）
4. **第三层子主题**：测试步骤（TestStep）和预期结果（Expected Result）
5. **优先级标注**：使用优先级图标（1、2、3对应高、中、低）
6. **执行类型**：通过标签定义（手动/自动）
7. **前置条件**：通过备注（Note）定义

详细规则请参考 [测试用例模板规则.md](测试用例模板规则.md)。

---

## 开发指南

### 📁 项目结构

```
XmindTestCase/
├── xmind2testcase/          # 核心转换模块
│   ├── __init__.py
│   ├── cli.py              # 命令行接口
│   ├── parser.py           # XMind文件解析器
│   ├── zentao.py           # 禅道格式转换
│   ├── testlink.py         # TestLink格式转换
│   └── utils.py            # 工具函数
├── xmind_loader.py         # 独立XMind加载器（新增）
├── xmind_processor.py      # XMind文件处理器（新增）
├── webtool/                # Web界面
│   ├── application.py      # Flask应用
│   ├── templates/          # HTML模板
│   └── static/             # 静态资源
├── docs/                   # 文档和示例
└── tests/                  # 测试用例
```

### 🔧 二次开发要点

#### 1. 独立XMind解析器

核心改进是开发了独立的XMind文件解析器，不再依赖xmind库：

```python
# xmind_loader.py
class XmindFileLoader:
    """独立的XMind文件加载器"""
    
    def load(self, xmind_file, enable_debug=False):
        """加载并解析XMind文件"""
        # 1. 验证文件完整性
        # 2. 解压ZIP内容
        # 3. 解析content.json
        # 4. 转换为兼容格式
        pass
```

#### 2. 性能优化

- **文件缓存**：避免重复解析相同的XMind文件
- **流式处理**：大文件采用流式解析，降低内存占用
- **并行转换**：多格式输出时采用并行处理

#### 3. 错误处理

```python
class XmindLoadError(Exception):
    """自定义异常类"""
    
    def __init__(self, error_type, message, details=None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
```

#### 4. 调试支持

```python
class XmindLoaderDebugger:
    """调试信息收集器"""
    
    def get_debug_report(self):
        """生成详细的调试报告"""
        return {
            '性能统计': {...},
            '文件信息': {...},
            '内容结构': {...},
            '错误记录': {...}
        }
```

### 🧪 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_parser.py

# 生成测试报告
python -m pytest tests/ --html=report.html --self-contained-html
```

### 🤝 贡献代码

1. Fork 项目仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

#### 代码规范

- 遵循 PEP 8 Python编码规范
- 添加适当的注释和文档字符串
- 为新功能编写测试用例
- 确保所有测试通过

---

## 许可证信息

本项目基于 MIT 许可证开源，详见 [LICENSE](LICENSE) 文件。

### 📄 版权声明

- 原项目 `xmind2testcase` 版权所有 (c) 2017-2022 Toby Qin, Devin, Alpha
- 二次开发部分版权所有 (c) 2025 Wenze Liang

本项目保留原项目的所有许可证条款，并对二次开发部分同样适用 MIT 许可证。

---

## 致谢

### 🙏 特别感谢

- **Toby Qin** - 原项目 [xmind2testcase](https://github.com/zhuifengshen/xmind2testcase) 的创始人和主要贡献者
- **Devin** - 原项目的核心维护者
- **Alpha** - 原项目的重要贡献者

### 👥 贡献者列表

感谢所有为这个项目做出贡献的开发者：

- [Wenze Liang](https://github.com/RedMaple96) - 二次开发、性能优化、错误处理增强
- [其他贡献者](https://github.com/RedMaple96/XmindTestCase/contributors)

### 📞 联系方式

- **项目维护者**: Wenze Liang
- **GitHub Issues**: [https://github.com/RedMaple96/XmindTestCase/issues](https://github.com/RedMaple96/XmindTestCase/issues)

---

## 更新日志

### v2.0.0 (2025-12-16)
- 🎉 发布二次开发版本
- 🔧 新增独立XMind解析器
- ⚡ 性能优化和缓存机制
- 🛡️ 增强错误处理和调试功能
- 🎨 改进Web界面用户体验

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个Star！**  
**🍴 欢迎Fork和贡献代码！**

</div>