"""
PDF文档转换器（reportlab版本）
使用reportlab生成PDF，无需系统依赖
"""

from typing import Any, Dict, List
from pathlib import Path
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Preformatted, Image
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .converter import BaseConverter
from .parser import MarkdownParser
from .flowchart_renderer import FlowchartProcessor


class PDFConverterReportlab(BaseConverter):
    """PDF文档转换器（reportlab版本）"""

    def __init__(self, **options):
        """
        初始化PDF转换器

        Args:
            **options: 转换选项
                - output_dir: 输出目录
                - page_size: 页面大小（A4, Letter等）
                - margin: 页边距
                - font: 默认字体
                - font_size: 默认字号
                - css_template: 自定义CSS模板路径（预留）
        """
        super().__init__(**options)
        self.page_size_name = options.get('page_size', 'A4')
        self.page_size = A4 if self.page_size_name == 'A4' else LETTER
        self.margin = options.get('margin', 2.5)  # cm
        self.font = options.get('font', 'Helvetica')
        self.font_size = options.get('font_size', 12)
        self.css_template = options.get('css_template')  # 预留模板接口

        # 注册中文字体（如果可用）
        self._register_chinese_fonts()

        # 流程图处理器
        self.flowchart_enabled = options.get('flowchart_enabled', True)
        self.flowchart_processor = FlowchartProcessor(**options) if self.flowchart_enabled else None
        self.flowchart_counter = 0

    def _register_chinese_fonts(self):
        """注册中文字体"""
        try:
            # 尝试注册系统中文字体
            import os
            font_paths = [
                '/System/Library/Fonts/STHeiti Light.ttc',
                '/System/Library/Fonts/STHeiti Medium.ttc',
                '/System/Library/Fonts/PingFang.ttc',
                'C:\\Windows\\Fonts\\simsun.ttc',
                'C:\\Windows\\Fonts\\msyh.ttc',
            ]

            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('Chinese', font_path))
                        self.font = 'Chinese'
                        break
                    except:
                        continue
        except:
            pass

    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """
        将AST转换为PDF文档

        Args:
            ast: Markdown AST节点列表
            output_path: 输出PDF文件路径

        Returns:
            转换是否成功
        """
        try:
            # 创建PDF文档
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.margin * cm,
                rightMargin=self.margin * cm,
                topMargin=self.margin * cm,
                bottomMargin=self.margin * cm
            )

            # 获取样式
            styles = self._get_styles()

            # 转换AST为流程元素
            story = self._convert_ast_to_story(ast, styles)

            # 生成PDF
            doc.build(story)

            self.log(f"PDF文档已生成: {output_path}")
            return True

        except Exception as e:
            self.log(f"转换失败: {e}", "error")
            return False

    def convert_file(self, input_path: str, output_path: str) -> bool:
        """
        转换Markdown文件为PDF文档

        Args:
            input_path: 输入Markdown文件路径
            output_path: 输出PDF文件路径

        Returns:
            转换是否成功
        """
        try:
            # 验证输入文件
            self.validate_input(input_path)

            # 解析Markdown
            parser = MarkdownParser()
            ast = parser.parse_file(input_path)

            # 转换为PDF
            return self.convert(ast, output_path)

        except Exception as e:
            self.log(f"转换失败: {e}", "error")
            return False

    def _get_styles(self) -> Dict[str, ParagraphStyle]:
        """
        获取样式定义

        Returns:
            样式字典
        """
        styles = getSampleStyleSheet()

        # 自定义样式
        custom_styles = {
            'Heading1': ParagraphStyle(
                'CustomHeading1',
                parent=styles['Heading1'],
                fontName=self.font,
                fontSize=24,
                spaceAfter=12,
                spaceBefore=24,
            ),
            'Heading2': ParagraphStyle(
                'CustomHeading2',
                parent=styles['Heading2'],
                fontName=self.font,
                fontSize=18,
                spaceAfter=8,
                spaceBefore=18,
            ),
            'Heading3': ParagraphStyle(
                'CustomHeading3',
                parent=styles['Heading3'],
                fontName=self.font,
                fontSize=14,
                spaceAfter=6,
                spaceBefore=12,
            ),
            'Normal': ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName=self.font,
                fontSize=self.font_size,
                spaceAfter=6,
                alignment=TA_JUSTIFY,
            ),
            'Code': ParagraphStyle(
                'CustomCode',
                fontName='Courier',
                fontSize=10,
                spaceAfter=6,
                spaceBefore=6,
                leftIndent=20,
                rightIndent=20,
                backColor=HexColor('#f4f4f4'),
            ),
            'Quote': ParagraphStyle(
                'CustomQuote',
                parent=styles['Normal'],
                fontName=self.font,
                fontSize=self.font_size,
                leftIndent=40,
                rightIndent=40,
                spaceAfter=6,
                textColor=HexColor('#555555'),
            ),
            'ListBullet': ParagraphStyle(
                'CustomListBullet',
                parent=styles['Normal'],
                fontName=self.font,
                fontSize=self.font_size,
                leftIndent=40,
                spaceAfter=3,
                bulletIndent=20,
            ),
            'ListNumber': ParagraphStyle(
                'CustomListNumber',
                parent=styles['Normal'],
                fontName=self.font,
                fontSize=self.font_size,
                leftIndent=40,
                spaceAfter=3,
                bulletIndent=20,
            ),
        }

        return custom_styles

    def _convert_ast_to_story(self, ast: List[Dict[str, Any]], styles: Dict[str, ParagraphStyle]) -> List:
        """
        将AST转换为PDF流程元素

        Args:
            ast: AST节点列表
            styles: 样式字典

        Returns:
            流程元素列表
        """
        story = []

        for node in ast:
            elements = self._process_node(node, styles)
            if elements:
                story.extend(elements)

        return story

    def _process_node(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """
        处理AST节点

        Args:
            node: AST节点
            styles: 样式字典

        Returns:
            流程元素列表
        """
        node_type = node.get('type')

        if node_type == 'heading':
            return self._process_heading(node, styles)
        elif node_type == 'paragraph':
            return self._process_paragraph(node, styles)
        elif node_type == 'list':
            return self._process_list(node, styles)
        elif node_type == 'table':
            return self._process_table(node, styles)
        elif node_type == 'code_block':
            # 检查是否为流程图
            if self.flowchart_enabled and self.flowchart_processor:
                content = node.get('content', '')
                chart_type = self.flowchart_processor.detect_flowchart(content)
                if chart_type:
                    return self._process_flowchart(node, chart_type, styles)
                else:
                    return self._process_code_block(node, styles)
            else:
                return self._process_code_block(node, styles)
        elif node_type == 'blockquote':
            return self._process_blockquote(node, styles)
        elif node_type == 'image':
            return self._process_image(node, styles)
        elif node_type == 'hr':
            return self._process_hr(node, styles)
        else:
            return []

    def _process_heading(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """处理标题"""
        level = node.get('level', 1)
        content = node.get('content', '')

        style_name = f'Heading{level}'
        style = styles.get(style_name, styles['Normal'])

        return [Paragraph(content, style)]

    def _process_paragraph(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """处理段落"""
        content = node.get('content', '')
        style = styles['Normal']

        return [Paragraph(content, style)]

    def _process_list(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """处理列表"""
        children = node.get('children', [])
        ordered = node.get('attributes', {}).get('ordered', False)

        elements = []
        for i, item in enumerate(children):
            if item.get('type') == 'list_item':
                item_content = self._get_list_item_content(item)

                if ordered:
                    bullet_text = f'{i + 1}.'
                    style = styles['ListNumber']
                else:
                    bullet_text = '•'
                    style = styles['ListBullet']

                # 创建带项目符号的段落
                para = Paragraph(f'{bullet_text} {item_content}', style)
                elements.append(para)

                # 处理嵌套列表
                for child in item.get('children', []):
                    if child.get('type') == 'list':
                        nested_elements = self._process_list(child, styles)
                        elements.extend(nested_elements)

        return elements

    def _get_list_item_content(self, node: Dict[str, Any]) -> str:
        """获取列表项内容"""
        content_parts = []
        for child in node.get('children', []):
            if child.get('type') == 'paragraph':
                content_parts.append(child.get('content', ''))
        return ' '.join(content_parts)

    def _process_table(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """处理表格"""
        children = node.get('children', [])

        if not children:
            return []

        # 准备表格数据
        table_data = []
        for row_node in children:
            row_data = []
            for cell_node in row_node.get('children', []):
                cell_content = cell_node.get('content', '')
                row_data.append(Paragraph(cell_content, styles['Normal']))
            table_data.append(row_data)

        if not table_data:
            return []

        # 创建表格
        table = Table(table_data)

        # 设置表格样式
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f2f2f2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#dddddd')),
        ])

        # 交替行背景色
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i), HexColor('#f9f9f9'))

        table.setStyle(table_style)

        return [table]

    def _process_code_block(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """处理代码块"""
        content = node.get('content', '')
        # language参数用于接口一致性

        # 使用预格式化文本
        code_style = styles['Code']
        code_para = Preformatted(content, code_style)

        return [code_para]

    def _process_flowchart(self, node: Dict[str, Any], chart_type: str, styles: Dict[str, ParagraphStyle]) -> List:
        """处理流程图"""
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
            elements = []

            # 添加流程图标题
            title_style = ParagraphStyle(
                'FlowchartTitle',
                parent=styles['Normal'],
                alignment=TA_CENTER,
                fontSize=9,
                textColor=HexColor('#808080'),
                spaceAfter=6,
            )
            elements.append(Paragraph(f'流程图 {self.flowchart_counter}', title_style))

            # 插入图片
            img = Image(str(image_path), width=400, height=300)
            elements.append(img)

            # 添加图片说明
            caption_style = ParagraphStyle(
                'FlowchartCaption',
                parent=styles['Normal'],
                alignment=TA_CENTER,
                fontSize=9,
                textColor=HexColor('#808080'),
                spaceBefore=6,
            )
            elements.append(Paragraph(f'图 {self.flowchart_counter}', caption_style))

            return elements
        else:
            # 渲染失败，添加代码块
            self.log(f"流程图渲染失败，添加为代码块", "warning")
            return self._process_code_block(node, styles)

    def _process_blockquote(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """处理引用"""
        children = node.get('children', [])
        elements = []

        for child in children:
            if child.get('type') == 'paragraph':
                content = child.get('content', '')
                quote_style = styles['Quote']
                elements.append(Paragraph(content, quote_style))

        return elements

    def _process_image(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """处理图片"""
        # reportlab处理图片需要额外逻辑
        # 暂时返回占位符
        alt = node.get('attributes', {}).get('alt', '图片')

        placeholder = Paragraph(f'[{alt}]', styles['Normal'])
        return [placeholder]

    def _process_hr(self, node: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List:
        """处理分割线"""
        # node和styles参数用于接口一致性
        # 使用表格模拟分割线
        hr_table = Table([['']], colWidths=[400])
        hr_style = TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 1, HexColor('#dddddd')),
        ])
        hr_table.setStyle(hr_style)

        return [hr_table]