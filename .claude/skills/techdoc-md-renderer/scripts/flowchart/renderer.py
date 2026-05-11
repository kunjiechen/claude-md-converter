"""
流程图渲染器
支持Mermaid和PlantUML语法，遵循G-C110规范
"""

import os
import subprocess
import tempfile
from typing import List, Optional
from pathlib import Path
from abc import ABC, abstractmethod

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from .painter import FlowchartPythonRenderer
    HAS_PAINTER = True
except ImportError:
    HAS_PAINTER = False


class FlowchartRenderer(ABC):
    """流程图渲染器基类"""

    @abstractmethod
    def render(self, code: str, output_path: str, **options) -> bool:
        """
        渲染流程图为图片

        Args:
            code: 流程图代码
            output_path: 输出图片路径
            **options: 渲染选项

        Returns:
            渲染是否成功
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查渲染器是否可用

        Returns:
            渲染器是否可用
        """
        pass


class MermaidRenderer(FlowchartRenderer):
    """Mermaid流程图渲染器"""

    def __init__(self, **options):
        """
        初始化Mermaid渲染器

        Args:
            **options: 渲染选项
                - mmdc_path: mmdc命令路径
                - theme: 主题
                - width: 宽度
                - height: 高度
        """
        self.mmdc_path = options.get('mmdc_path', 'mmdc')
        self.theme = options.get('theme', 'default')
        self.width = options.get('width', 800)
        self.height = options.get('height', 600)

    def render(self, code: str, output_path: str, **options) -> bool:
        """
        渲染Mermaid流程图为PNG

        Args:
            code: Mermaid代码
            output_path: 输出图片路径
            **options: 渲染选项

        Returns:
            渲染是否成功
        """
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
                f.write(code)
                temp_input = f.name

            # 准备输出路径
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建命令，使用neutral主题（黑白风格），加载skill的mermaid配置
            cmd = [
                self.mmdc_path,
                '-i', temp_input,
                '-o', str(output_path),
                '-t', 'neutral',
                '-w', str(self.width),
                '-H', str(self.height),
                '-b', 'transparent',
            ]
            # 添加配置文件（如果存在）
            config_file = Path(__file__).parent.parent.parent / 'assets' / 'mermaid_theme.json'
            if config_file.exists():
                cmd.extend(['-c', str(config_file)])

            # 执行命令，配置Chrome路径
            env = os.environ.copy()
            chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
                "/usr/bin/google-chrome",  # Linux
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # Windows
            ]
            if 'PUPPETEER_EXECUTABLE_PATH' not in env:
                for chrome_path in chrome_paths:
                    if os.path.exists(chrome_path):
                        env['PUPPETEER_EXECUTABLE_PATH'] = chrome_path
                        break

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )

            # 清理临时文件
            os.unlink(temp_input)

            if result.returncode == 0 and output_path.exists():
                return True
            else:
                print(f"Mermaid渲染失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print("Mermaid渲染超时")
            return False
        except FileNotFoundError:
            print(f"找不到mmdc命令: {self.mmdc_path}")
            return False
        except Exception as e:
            print(f"Mermaid渲染异常: {e}")
            return False

    def is_available(self) -> bool:
        """检查mmdc是否可用"""
        try:
            result = subprocess.run(
                [self.mmdc_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False


class PlantUMLRenderer(FlowchartRenderer):
    """PlantUML流程图渲染器"""

    def __init__(self, **options):
        """
        初始化PlantUML渲染器

        Args:
            **options: 渲染选项
                - plantuml_path: plantuml命令路径
                - format: 输出格式（png, svg）
        """
        self.plantuml_path = options.get('plantuml_path', 'plantuml')
        self.format = options.get('format', 'png')

    def render(self, code: str, output_path: str, **options) -> bool:
        """
        渲染PlantUML流程图为图片

        Args:
            code: PlantUML代码
            output_path: 输出图片路径
            **options: 渲染选项

        Returns:
            渲染是否成功
        """
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.puml', delete=False) as f:
                f.write(code)
                temp_input = f.name

            # 准备输出目录
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建命令
            cmd = [
                self.plantuml_path,
                '-t' + self.format,
                '-o', str(output_path.parent),
                temp_input
            ]

            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # 清理临时文件
            os.unlink(temp_input)

            # PlantUML生成的文件名可能不同
            generated_file = output_path.parent / (Path(temp_input).stem + '.' + self.format)
            if generated_file.exists():
                generated_file.rename(output_path)
                return True

            if result.returncode == 0:
                return True
            else:
                print(f"PlantUML渲染失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print("PlantUML渲染超时")
            return False
        except FileNotFoundError:
            print(f"找不到plantuml命令: {self.plantuml_path}")
            return False
        except Exception as e:
            print(f"PlantUML渲染异常: {e}")
            return False

    def is_available(self) -> bool:
        """检查plantuml是否可用"""
        try:
            result = subprocess.run(
                [self.plantuml_path, '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False


class KrokiRenderer(FlowchartRenderer):
    """Kroki在线API渲染器（无需本地依赖）"""

    def __init__(self, **options):
        """
        初始化Kroki渲染器

        Args:
            **options: 渲染选项
                - kroki_url: Kroki API地址（默认：https://kroki.io）
                - format: 输出格式（png, svg）
        """
        self.kroki_url = options.get('kroki_url', 'https://kroki.io')
        self.format = options.get('format', 'png')

    def render(self, code: str, output_path: str, chart_type: str = 'mermaid', **options) -> bool:
        """
        使用Kroki API渲染流程图

        Args:
            code: 流程图代码
            output_path: 输出图片路径
            chart_type: 流程图类型（mermaid, plantuml）

        Returns:
            渲染是否成功
        """
        if not HAS_REQUESTS:
            print("需要安装requests库：pip install requests")
            return False

        try:
            # 构建API URL
            url = f"{self.kroki_url}/{chart_type}/{self.format}"

            # 发送请求
            response = requests.post(
                url,
                data=code.encode('utf-8'),
                headers={'Content-Type': 'text/plain'},
                timeout=30
            )

            if response.status_code == 200:
                # 保存图片
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)
                return True
            else:
                print(f"Kroki API错误: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            print("Kroki API请求超时")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Kroki API请求失败: {e}")
            return False
        except Exception as e:
            print(f"Kroki渲染异常: {e}")
            return False

    def is_available(self) -> bool:
        """检查Kroki API是否可用"""
        if not HAS_REQUESTS:
            return False

        try:
            response = requests.get(self.kroki_url, timeout=5)
            return response.status_code == 200
        except:
            return False


class FlowchartProcessor:
    """流程图处理器"""

    def __init__(self, **options):
        """
        初始化流程图处理器

        Args:
            **options: 处理选项
                - mermaid_enabled: 是否启用Mermaid
                - plantuml_enabled: 是否启用PlantUML
                - use_kroki: 是否使用Kroki在线API（无需本地依赖）
                - use_python_painter: 是否使用Python绘图（推荐，完全符合G-C110规范）
                - output_dir: 图片输出目录
                - temp_dir: 临时目录
        """
        self.mermaid_enabled = options.get('mermaid_enabled', True)
        self.plantuml_enabled = options.get('plantuml_enabled', True)
        self.use_kroki = options.get('use_kroki', False)
        self.use_python_painter = options.get('use_python_painter', True)  # 默认使用Python绘图
        self.output_dir = options.get('output_dir')
        self.temp_dir = options.get('temp_dir')

        # 初始化渲染器
        # Python绘图渲染器（推荐，完全符合G-C110规范）
        self.python_renderer = FlowchartPythonRenderer(**options) if self.use_python_painter and HAS_PAINTER else None

        # Kroki在线API渲染器
        self.kroki_renderer = KrokiRenderer(**options) if self.use_kroki else None

        # 本地渲染器（作为备选方案）
        self.mermaid_renderer = MermaidRenderer(**options) if self.mermaid_enabled else None
        self.plantuml_renderer = PlantUMLRenderer(**options) if self.plantuml_enabled else None

    def detect_flowchart(self, code: str) -> Optional[str]:
        """
        检测代码块是否为流程图

        Args:
            code: 代码块内容

        Returns:
            流程图类型（mermaid, plantuml）或None
        """
        code_stripped = code.strip()

        # 检测Mermaid
        mermaid_keywords = [
            'graph ', 'flowchart ', 'sequenceDiagram', 'classDiagram',
            'stateDiagram', 'gantt', 'pie', 'journey'
        ]
        if any(keyword in code_stripped for keyword in mermaid_keywords):
            return 'mermaid'

        # 检测PlantUML
        if code_stripped.startswith('@startuml') or code_stripped.startswith('@startgantt'):
            return 'plantuml'

        return None

    def render_flowchart(self, code: str, chart_type: str, output_path: str) -> bool:
        """
        渲染流程图

        Args:
            code: 流程图代码
            chart_type: 流程图类型（mermaid, plantuml）
            output_path: 输出图片路径

        Returns:
            渲染是否成功
        """
        # 优先使用Python绘图（推荐，完全符合G-C110规范）
        # 只支持graph/flowchart类型的流程图
        if self.use_python_painter and self.python_renderer and chart_type == 'mermaid':
            result = self.python_renderer.render(code, output_path)
            if result:
                return True
            # Python绘图失败（可能是sequenceDiagram等非流程图类型），继续尝试其他渲染器

        # 使用Kroki
        if self.use_kroki and self.kroki_renderer:
            return self.kroki_renderer.render(code, output_path, chart_type)

        # 使用本地渲染器
        if chart_type == 'mermaid' and self.mermaid_renderer:
            return self.mermaid_renderer.render(code, output_path)
        elif chart_type == 'plantuml' and self.plantuml_renderer:
            return self.plantuml_renderer.render(code, output_path)
        else:
            print(f"不支持的流程图类型: {chart_type}")
            return False

    def is_available(self, chart_type: str) -> bool:
        """
        检查指定类型的渲染器是否可用

        Args:
            chart_type: 流程图类型

        Returns:
            渲染器是否可用
        """
        # 检查Python绘图渲染器
        if self.use_python_painter and self.python_renderer and chart_type == 'mermaid':
            return self.python_renderer.is_available()

        # 检查Kroki
        if self.use_kroki and self.kroki_renderer:
            return self.kroki_renderer.is_available()

        # 检查本地渲染器
        if chart_type == 'mermaid' and self.mermaid_renderer:
            return self.mermaid_renderer.is_available()
        elif chart_type == 'plantuml' and self.plantuml_renderer:
            return self.plantuml_renderer.is_available()
        return False

    def get_available_renderers(self) -> List[str]:
        """
        获取可用的渲染器列表

        Returns:
            可用渲染器类型列表
        """
        available = []

        # 检查Python绘图渲染器
        if self.use_python_painter and self.python_renderer and self.python_renderer.is_available():
            available.append('python_painter')

        # 检查Kroki
        if self.use_kroki and self.kroki_renderer and self.kroki_renderer.is_available():
            available.append('kroki')

        # 检查本地渲染器
        if self.mermaid_enabled and self.mermaid_renderer and self.mermaid_renderer.is_available():
            available.append('mermaid')

        if self.plantuml_enabled and self.plantuml_renderer and self.plantuml_renderer.is_available():
            available.append('plantuml')

        return available