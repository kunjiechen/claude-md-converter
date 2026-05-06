"""
流程图处理器测试
"""

import pytest
from src.md_converter.flowchart_renderer import FlowchartProcessor, MermaidRenderer, PlantUMLRenderer


class TestFlowchartProcessor:
    """流程图处理器测试"""

    def setup_method(self):
        """测试前准备"""
        self.processor = FlowchartProcessor()

    def test_detect_mermaid_flowchart(self):
        """测试检测Mermaid流程图"""
        code = '''graph TD
    A[开始] --> B[处理]
    B --> C[结束]
'''
        result = self.processor.detect_flowchart(code)
        assert result == 'mermaid'

    def test_detect_mermaid_sequence(self):
        """测试检测Mermaid时序图"""
        code = '''sequenceDiagram
    Alice->>Bob: Hello Bob
    Bob-->>Alice: Hi Alice
'''
        result = self.processor.detect_flowchart(code)
        assert result == 'mermaid'

    def test_detect_mermaid_class(self):
        """测试检测Mermaid类图"""
        code = '''classDiagram
    Animal <|-- Duck
'''
        result = self.processor.detect_flowchart(code)
        assert result == 'mermaid'

    def test_detect_plantuml(self):
        """测试检测PlantUML"""
        code = '''@startuml
Alice -> Bob: Hello
@enduml
'''
        result = self.processor.detect_flowchart(code)
        assert result == 'plantuml'

    def test_detect_regular_code(self):
        """测试检测普通代码"""
        code = '''def hello():
    print("Hello World")
'''
        result = self.processor.detect_flowchart(code)
        assert result is None

    def test_detect_empty_code(self):
        """测试检测空代码"""
        result = self.processor.detect_flowchart('')
        assert result is None

    def test_get_available_renderers(self):
        """测试获取可用渲染器"""
        # 在没有安装mmdc和plantuml的情况下，应该返回空列表
        available = self.processor.get_available_renderers()
        assert isinstance(available, list)

    def test_is_available_mermaid(self):
        """测试检查Mermaid是否可用"""
        # 在没有安装mmdc的情况下，应该返回False
        result = self.processor.is_available('mermaid')
        assert result == False

    def test_is_available_plantuml(self):
        """测试检查PlantUML是否可用"""
        # 在没有安装plantuml的情况下，应该返回False
        result = self.processor.is_available('plantuml')
        assert result == False

    def test_is_available_unknown(self):
        """测试检查未知类型是否可用"""
        result = self.processor.is_available('unknown')
        assert result == False


class TestMermaidRenderer:
    """Mermaid渲染器测试"""

    def setup_method(self):
        """测试前准备"""
        self.renderer = MermaidRenderer()

    def test_is_available(self):
        """测试检查是否可用"""
        # 在没有安装mmdc的情况下，应该返回False
        result = self.renderer.is_available()
        assert result == False

    def test_render_without_mmdc(self, temp_dir):
        """测试没有mmdc时的渲染"""
        code = '''graph TD
    A[开始] --> B[结束]
'''
        output_path = str(temp_dir / "test.png")
        result = self.renderer.render(code, output_path)
        assert result == False


class TestPlantUMLRenderer:
    """PlantUML渲染器测试"""

    def setup_method(self):
        """测试前准备"""
        self.renderer = PlantUMLRenderer()

    def test_is_available(self):
        """测试检查是否可用"""
        # 在没有安装plantuml的情况下，应该返回False
        result = self.renderer.is_available()
        assert result == False

    def test_render_without_plantuml(self, temp_dir):
        """测试没有plantuml时的渲染"""
        code = '''@startuml
Alice -> Bob: Hello
@enduml
'''
        output_path = str(temp_dir / "test.png")
        result = self.renderer.render(code, output_path)
        assert result == False