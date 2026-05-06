"""
Word文档转换器
将Markdown AST转换为Word文档
"""

from typing import Any, Dict, List
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from .converter import BaseConverter
from .parser import MarkdownParser
from .flowchart_renderer import FlowchartProcessor


class WordConverter(BaseConverter):
    """Word文档转换器"""

    def __init__(self, **options):
        """
        初始化Word转换器

        Args:
            **options: 转换选项
                - template: Word模板文件路径(.dotx)
                - output_dir: 输出目录
                - font: 默认字体
                - font_size: 默认字号
                - flowchart_enabled: 是否启用流程图
        """
        super().__init__(**options)
        self.font = options.get('font', '宋体')
        self.font_size = options.get('font_size', 12)
        self.doc = None

        # 流程图处理器
        self.flowchart_enabled = options.get('flowchart_enabled', True)
        self.flowchart_processor = FlowchartProcessor(**options) if self.flowchart_enabled else None
        self.flowchart_counter = 0

    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """
        将AST转换为Word文档

        Args:
            ast: Markdown AST节点列表
            output_path: 输出Word文件路径

        Returns:
            转换是否成功
        """
        try:
            # 创建文档
            self.doc = self._create_document()

            # 遍历AST节点
            for node in ast:
                self._process_node(node)

            # 保存文档
            self.doc.save(output_path)
            self.log(f"Word文档已生成: {output_path}")
            return True

        except Exception as e:
            self.log(f"转换失败: {e}", "error")
            return False

    def convert_file(self, input_path: str, output_path: str) -> bool:
        """
        转换Markdown文件为Word文档

        Args:
            input_path: 输入Markdown文件路径
            output_path: 输出Word文件路径

        Returns:
            转换是否成功
        """
        try:
            # 验证输入文件
            self.validate_input(input_path)

            # 解析Markdown
            parser = MarkdownParser()
            ast = parser.parse_file(input_path)

            # 转换为Word
            return self.convert(ast, output_path)

        except Exception as e:
            self.log(f"转换失败: {e}", "error")
            return False

    def _create_document(self):
        """
        创建Word文档

        Returns:
            Word文档对象
        """
        if self.template_path:
            # 加载模板
            doc = Document(self.template_path)
        else:
            # 创建新文档
            doc = Document()

            # 设置默认字体
            style = doc.styles['Normal']
            font = style.font
            font.name = self.font
            font.size = Pt(self.font_size)

            # 设置中文字体
            style.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

        return doc

    def _process_node(self, node: Dict[str, Any]):
        """
        处理AST节点

        Args:
            node: AST节点
        """
        node_type = node.get('type')

        if node_type == 'heading':
            self._add_heading(node)
        elif node_type == 'paragraph':
            self._add_paragraph(node)
        elif node_type == 'list':
            self._add_list(node)
        elif node_type == 'table':
            self._add_table(node)
        elif node_type == 'code_block':
            # 检查是否为流程图
            if self.flowchart_enabled and self.flowchart_processor:
                content = node.get('content', '')
                chart_type = self.flowchart_processor.detect_flowchart(content)
                if chart_type:
                    self._add_flowchart(node, chart_type)
                else:
                    self._add_code_block(node)
            else:
                self._add_code_block(node)
        elif node_type == 'blockquote':
            self._add_blockquote(node)
        elif node_type == 'image':
            self._add_image(node)
        elif node_type == 'hr':
            self._add_hr(node)

    def _add_heading(self, node: Dict[str, Any]):
        """
        添加标题

        Args:
            node: 标题节点
        """
        level = node.get('level', 1)
        content = node.get('content', '')

        # 添加标题
        heading = self.doc.add_heading(content, level=level)

        # 设置中文字体
        for run in heading.runs:
            run.font.name = self.font
            run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

    def _add_paragraph(self, node: Dict[str, Any]):
        """
        添加段落

        Args:
            node: 段落节点
        """
        content = node.get('content', '')

        # 添加段落
        para = self.doc.add_paragraph()

        # 处理内联元素
        self._process_inline_content(para, content)

        # 设置中文字体
        for run in para.runs:
            run.font.name = self.font
            run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

    def _process_inline_content(self, para, content: str):
        """
        处理内联内容

        Args:
            para: 段落对象
            content: 内容文本
        """
        # 简单处理，直接添加文本
        # TODO: 处理粗体、斜体等内联元素
        run = para.add_run(content)
        run.font.name = self.font
        run.font.size = Pt(self.font_size)

    def _add_list(self, node: Dict[str, Any], level: int = 0):
        """
        添加列表

        Args:
            node: 列表节点
            level: 列表级别
        """
        children = node.get('children', [])
        ordered = node.get('attributes', {}).get('ordered', False)

        for item in children:
            if item.get('type') == 'list_item':
                # 获取列表项内容
                item_content = self._get_list_item_content(item)

                # 添加列表项
                if ordered:
                    para = self.doc.add_paragraph(style='List Number')
                else:
                    para = self.doc.add_paragraph(style='List Bullet')

                # 设置内容
                para.text = item_content

                # 设置缩进
                para.paragraph_format.left_indent = Cm(1.27 * level)

                # 设置中文字体
                for run in para.runs:
                    run.font.name = self.font
                    run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

                # 处理嵌套列表
                for child in item.get('children', []):
                    if child.get('type') == 'list':
                        self._add_list(child, level + 1)

    def _get_list_item_content(self, node: Dict[str, Any]) -> str:
        """
        获取列表项内容

        Args:
            node: 列表项节点

        Returns:
            内容文本
        """
        content_parts = []
        for child in node.get('children', []):
            if child.get('type') == 'paragraph':
                content_parts.append(child.get('content', ''))
        return ' '.join(content_parts)

    def _add_table(self, node: Dict[str, Any]):
        """
        添加表格

        Args:
            node: 表格节点
        """
        children = node.get('children', [])

        if not children:
            return

        # 计算行列数
        rows = len(children)
        cols = len(children[0].get('children', [])) if children else 0

        if rows == 0 or cols == 0:
            return

        # 创建表格
        table = self.doc.add_table(rows=rows, cols=cols)
        table.style = 'Table Grid'

        # 填充表格内容
        for i, row_node in enumerate(children):
            row_cells = row_node.get('children', [])
            for j, cell_node in enumerate(row_cells):
                if j < cols:
                    cell = table.cell(i, j)
                    cell.text = cell_node.get('content', '')

                    # 设置中文字体
                    for para in cell.paragraphs:
                        for run in para.runs:
                            run.font.name = self.font
                            run.font.size = Pt(self.font_size)
                            run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

    def _add_code_block(self, node: Dict[str, Any]):
        """
        添加代码块

        Args:
            node: 代码块节点
        """
        content = node.get('content', '')
        language = node.get('attributes', {}).get('language', '')

        # 添加代码块段落
        para = self.doc.add_paragraph()

        # 设置代码块样式
        para.paragraph_format.left_indent = Cm(1)
        para.paragraph_format.right_indent = Cm(1)
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(6)

        # 添加代码内容
        run = para.add_run(content)
        run.font.name = 'Courier New'
        run.font.size = Pt(10)

        # 设置背景色（浅灰色）
        # TODO: 设置段落背景色

        # 如果有语言标识，添加语言标签
        if language:
            lang_para = self.doc.add_paragraph()
            lang_run = lang_para.add_run(f'Language: {language}')
            lang_run.font.size = Pt(8)
            lang_run.font.color.rgb = RGBColor(128, 128, 128)

    def _add_flowchart(self, node: Dict[str, Any], chart_type: str):
        """
        添加流程图

        Args:
            node: 代码块节点
            chart_type: 流程图类型（mermaid, plantuml）
        """
        content = node.get('content', '')

        # 生成输出路径
        self.flowchart_counter += 1
        output_dir = Path(self.output_dir) if self.output_dir else Path('.')
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f'flowchart_{self.flowchart_counter}.png'

        # 渲染流程图
        success = self.flowchart_processor.render_flowchart(
            content, chart_type, str(image_path)
        )

        if success and image_path.exists():
            # 添加流程图标题
            title_para = self.doc.add_paragraph()
            title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title_run = title_para.add_run(f'流程图 {self.flowchart_counter}')
            title_run.font.size = Pt(9)
            title_run.font.color.rgb = RGBColor(128, 128, 128)

            # 插入图片
            self.doc.add_picture(str(image_path), width=Inches(5))

            # 添加图片说明
            caption_para = self.doc.add_paragraph()
            caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption_run = caption_para.add_run(f'图 {self.flowchart_counter}')
            caption_run.font.size = Pt(9)
            caption_run.font.color.rgb = RGBColor(128, 128, 128)
        else:
            # 渲染失败，添加代码块
            self.log(f"流程图渲染失败，添加为代码块", "warning")
            self._add_code_block(node)

    def _add_blockquote(self, node: Dict[str, Any]):
        """
        添加引用

        Args:
            node: 引用节点
        """
        children = node.get('children', [])

        for child in children:
            if child.get('type') == 'paragraph':
                # 添加引用段落
                para = self.doc.add_paragraph()

                # 设置引用样式
                para.paragraph_format.left_indent = Cm(2)
                para.paragraph_format.right_indent = Cm(2)

                # 添加引用内容
                content = child.get('content', '')
                run = para.add_run(content)
                run.font.name = self.font
                run.font.size = Pt(self.font_size)
                run.font.italic = True

                # 设置左边框
                # TODO: 设置段落左边框

    def _add_image(self, node: Dict[str, Any]):
        """
        添加图片

        Args:
            node: 图片节点
        """
        src = node.get('attributes', {}).get('src', '')
        alt = node.get('attributes', {}).get('alt', '')

        if not src:
            self.log(f"图片路径为空: {alt}", "warning")
            return

        try:
            # 处理图片路径
            if src.startswith('http://') or src.startswith('https://'):
                # 远程图片，需要下载
                # TODO: 实现远程图片下载
                self.log(f"远程图片暂不支持: {src}", "warning")
                return
            else:
                # 本地图片
                image_path = Path(src)
                if not image_path.exists():
                    # 尝试相对于输入文件的路径
                    # TODO: 处理相对路径
                    self.log(f"图片不存在: {src}", "warning")
                    return

                # 插入图片
                self.doc.add_picture(str(image_path), width=Inches(4))

                # 添加图片标题
                if alt:
                    caption = self.doc.add_paragraph()
                    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = caption.add_run(alt)
                    run.font.size = Pt(9)
                    run.font.color.rgb = RGBColor(128, 128, 128)

        except Exception as e:
            self.log(f"插入图片失败: {e}", "error")

    def _add_hr(self, node: Dict[str, Any]):
        """
        添加分割线

        Args:
            node: 分割线节点（用于接口一致性）
        """
        # 添加分割线段落
        para = self.doc.add_paragraph()

        # 添加水平线
        # TODO: 实现水平线样式
        run = para.add_run('_' * 50)
        run.font.color.rgb = RGBColor(192, 192, 192)