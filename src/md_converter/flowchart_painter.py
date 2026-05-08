"""
Python绘图流程图渲染器
完全遵循G-C110规范，精确控制节点形状、大小和出线位置
"""

import re
import math
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class FlowchartNode:
    """流程图节点"""

    def __init__(self, node_id: str, label: str, node_type: str = 'process'):
        """
        初始化节点

        Args:
            node_id: 节点ID
            label: 节点标签
            node_type: 节点类型
                - 'start_end': 端点符（圆角矩形）
                - 'process': 处理符号（矩形）
                - 'decision': 判断（菱形）
                - 'data': 数据符号（平行四边形）
                - 'loop': 循环界限（去角矩形）
                - 'connector': 连接符（圆形）
        """
        self.id = node_id
        self.label = label
        self.node_type = node_type
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0


class FlowchartEdge:
    """流程图边"""

    def __init__(self, from_node: str, to_node: str, label: str = ''):
        """
        初始化边

        Args:
            from_node: 起始节点ID
            to_node: 目标节点ID
            label: 边标签
        """
        self.from_node = from_node
        self.to_node = to_node
        self.label = label


class FlowchartGraph:
    """流程图"""

    def __init__(self, direction: str = 'TD'):
        """
        初始化流程图

        Args:
            direction: 流向方向
                - 'TD': 从上到下
                - 'LR': 从左到右
        """
        self.direction = direction
        self.nodes: Dict[str, FlowchartNode] = {}
        self.edges: List[FlowchartEdge] = []
        self.title = ''

    def add_node(self, node: FlowchartNode):
        """添加节点"""
        self.nodes[node.id] = node

    def add_edge(self, edge: FlowchartEdge):
        """添加边"""
        self.edges.append(edge)


class MermaidParser:
    """Mermaid语法解析器"""

    def parse(self, code: str) -> FlowchartGraph:
        """
        解析Mermaid代码

        Args:
            code: Mermaid代码

        Returns:
            流程图对象
        """
        lines = code.strip().split('\n')
        graph = FlowchartGraph()

        # 检测图表类型
        is_flowchart = False
        for line in lines:
            line = line.strip()
            if line.startswith('graph ') or line.startswith('flowchart '):
                is_flowchart = True
                direction = line.split()[1] if len(line.split()) > 1 else 'TD'
                graph.direction = direction
                break

        # 只处理流程图（graph/flowchart），其他类型（sequenceDiagram、gantt等）返回空
        if not is_flowchart:
            return graph

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过图方向声明
            if line.startswith('graph ') or line.startswith('flowchart '):
                continue

            # 解析节点定义和边
            # 格式: A[label] --> B[label] 或 A[label] -->|label| B[label]
            edge_pattern = r'(\w+)(?:\[([^\]]*)\]|\{([^}]*)\}|\(\[([^\]]*)\]\)|\(\(([^)]*)\)\)|\[\[([^\]]*)\]\]|\[\\?"([^"]*)\\?"\])?\s*-->?\s*(?:\|([^|]*)\|\s*)?(\w+)(?:\[([^\]]*)\]|\{([^}]*)\}|\(\[([^\]]*)\]\)|\(\(([^)]*)\)\)|\[\[([^\]]*)\]\]|\[\\?"([^"]*)\\?"\])?'

            match = re.search(edge_pattern, line)
            if match:
                groups = match.groups()
                from_id = groups[0]
                from_label = groups[1] or groups[2] or groups[3] or groups[4] or groups[5] or groups[6] or from_id
                edge_label = groups[7] or ''
                to_id = groups[8]
                to_label = groups[9] or groups[10] or groups[11] or groups[12] or groups[13] or groups[14] or to_id

                # 确定节点类型
                from_type = self._detect_node_type(line, from_id)
                to_type = self._detect_node_type(line, to_id)

                # 添加节点
                if from_id not in graph.nodes:
                    graph.add_node(FlowchartNode(from_id, from_label, from_type))
                if to_id not in graph.nodes:
                    graph.add_node(FlowchartNode(to_id, to_label, to_type))

                # 添加边
                graph.add_edge(FlowchartEdge(from_id, to_id, edge_label))

        return graph

    def _detect_node_type(self, line: str, node_id: str) -> str:
        """检测节点类型"""
        # 查找节点定义
        escaped_id = re.escape(node_id)
        patterns = [
            (escaped_id + r'\{[^}]*\}', 'decision'),  # {text} 菱形
            (escaped_id + r'\(\[([^\]]*)\]\)', 'start_end'),  # ([text]) 圆角矩形
            (escaped_id + r'\(\(([^)]*)\)\)', 'connector'),  # ((text)) 圆形
            (escaped_id + r'\[\[([^\]]*)\]\]', 'data'),  # [[text]] 平行四边形
            (escaped_id + r'\[([^\]]*)\]', 'process'),  # [text] 矩形
        ]

        for pattern, node_type in patterns:
            if re.search(pattern, line):
                return node_type

        # 默认为处理符号
        return 'process'


class FlowchartPainter:
    """流程图绘制器"""

    def __init__(self, **options):
        """
        初始化绘制器

        Args:
            **options: 绘制选项
                - font_path: 字体路径
                - font_size: 字体大小
                - node_min_width: 节点最小宽度
                - node_min_height: 节点最小高度
                - node_padding: 节点内边距
                - horizontal_spacing: 水平间距
                - vertical_spacing: 垂直间距
                - line_color: 线条颜色
                - fill_color: 填充颜色
                - text_color: 文字颜色
        """
        if not HAS_PIL:
            raise ImportError("需要安装Pillow库：pip install Pillow")

        self.font_path = options.get('font_path', self._get_default_font())
        self.font_size = options.get('font_size', 14)
        self.node_min_width = options.get('node_min_width', 120)
        self.node_min_height = options.get('node_min_height', 50)
        self.node_padding = options.get('node_padding', 20)
        self.horizontal_spacing = options.get('horizontal_spacing', 60)
        self.vertical_spacing = options.get('vertical_spacing', 50)
        self.line_color = options.get('line_color', (0, 0, 0))
        self.fill_color = options.get('fill_color', (255, 255, 255))
        self.text_color = options.get('text_color', (0, 0, 0))

        # 加载字体
        try:
            self.font = ImageFont.truetype(self.font_path, self.font_size)
        except:
            self.font = ImageFont.load_default()

    def _get_default_font(self) -> str:
        """获取默认字体路径（优先楷体，其次黑体）"""
        import platform
        system = platform.system()

        if system == 'Darwin':  # macOS
            fonts = [
                '/System/Library/Fonts/STKaiti.ttf',
                '/System/Library/Fonts/Kaiti.ttf',
                '/Library/Fonts/Kaiti.ttf',
                '/System/Library/Fonts/STHeiti Medium.ttc',  # 华文黑体
                '/System/Library/Fonts/Hiragino Sans GB.ttc',  # 苹方
                '/Library/Fonts/Arial Unicode.ttf',
            ]
        elif system == 'Windows':
            fonts = [
                'C:\\Windows\\Fonts\\simkai.ttf',
                'C:\\Windows\\Fonts\\kaiti.ttf',
                'C:\\Windows\\Fonts\\simhei.ttf',
                'C:\\Windows\\Fonts\\msyh.ttc',
            ]
        else:  # Linux
            fonts = [
                '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
                '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
            ]

        for font in fonts:
            if Path(font).exists():
                return font

        return ''

    def paint(self, graph: FlowchartGraph, output_path: str) -> bool:
        """
        绘制流程图

        Args:
            graph: 流程图对象
            output_path: 输出图片路径

        Returns:
            绘制是否成功
        """
        try:
            # 计算布局
            self._calculate_layout(graph)

            # 计算画布大小
            canvas_width, canvas_height = self._calculate_canvas_size(graph)

            # 计算偏移量，确保所有节点都在画布内
            min_x = min(node.x - node.width / 2 for node in graph.nodes.values())
            min_y = min(node.y - node.height / 2 for node in graph.nodes.values())
            offset_x = -min_x if min_x < 0 else 0
            offset_y = -min_y if min_y < 0 else 0

            # 调整所有节点位置
            for node in graph.nodes.values():
                node.x += offset_x
                node.y += offset_y

            # 创建画布
            padding = 40
            img_width = canvas_width + padding * 2
            img_height = canvas_height + padding * 2

            # 计算缩放比例，限制高度在8cm左右（约300像素）
            max_height = 300
            scale = 1.0
            if img_height > max_height:
                scale = max_height / img_height

            # 创建画布
            target_width = int(img_width * scale)
            target_height = int(img_height * scale)
            img = Image.new('RGB', (target_width, target_height), (255, 255, 255))
            draw = ImageDraw.Draw(img)

            # 应用缩放
            self.scale = scale

            # 绘制边（先绘制边，再绘制节点）
            for edge in graph.edges:
                self._draw_edge(draw, graph, edge, padding)

            # 绘制节点
            for node in graph.nodes.values():
                self._draw_node(draw, node, padding)

            # 保存图片
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(output_path), 'PNG')

            return True

        except Exception as e:
            print(f"流程图绘制失败: {e}")
            return False

    def _calculate_layout(self, graph: FlowchartGraph):
        """计算节点布局"""
        # 先尝试检测是否为for循环模式
        is_for_loop, loop_nodes = self._detect_for_loop(graph)
        # 检测是否为switch case模式
        is_switch_case, switch_nodes = self._detect_switch_case(graph)

        # 计算节点大小
        for node in graph.nodes.values():
            self._calculate_node_size(node)

        # 统一节点大小（让所有节点大小尽量一致）
        max_width = max(node.width for node in graph.nodes.values())
        max_height = max(node.height for node in graph.nodes.values())
        for node in graph.nodes.values():
            if node.node_type == 'start_end':
                # 开始/结束框：横向椭圆（明显区别于矩形处理框）
                node.width = max_width * 1.1
                node.height = max_height * 0.55
            else:
                node.width = max_width
                node.height = max_height

        if is_for_loop and graph.direction == 'TD':
            # 使用for循环专用布局
            self._layout_for_loop(graph, loop_nodes)
        elif is_switch_case and graph.direction == 'TD':
            # 使用switch case专用布局
            self._layout_switch_case(graph, switch_nodes)
        else:
            # 按拓扑排序确定节点顺序
            ordered_nodes = self._topological_sort(graph)

            # 计算每个节点的层级
            levels = self._calculate_levels(graph, ordered_nodes)

            # 按层级分组
            level_groups = {}
            for node_id, level in levels.items():
                if level not in level_groups:
                    level_groups[level] = []
                level_groups[level].append(node_id)

            # 计算节点位置
            if graph.direction == 'TD':
                self._layout_top_down(graph, level_groups)
            else:
                self._layout_left_right(graph, level_groups)

    def _detect_for_loop(self, graph: FlowchartGraph) -> Tuple[bool, Dict[str, str]]:
        """检测是否为for循环模式"""
        # 找是否有一个判断节点有两条入边：一条从初始化/处理来，一条从增量来
        decision_nodes = [n for n in graph.nodes.values() if n.node_type == 'decision']

        for decision_node in decision_nodes:
            # 找到指向判断节点的边
            incoming_edges = [e for e in graph.edges if e.to_node == decision_node.id]
            if len(incoming_edges) >= 2:
                # 找到判断节点的"是"分支
                yes_node = None
                for e in graph.edges:
                    if e.from_node == decision_node.id and e.label in ['是', '条件成立', 'yes', 'Y']:
                        yes_node = e.to_node
                        break

                if yes_node:
                    # 找到yes_node指向的节点（应该是增量操作）
                    inc_node = None
                    for e in graph.edges:
                        if e.from_node == yes_node:
                            inc_node = e.to_node
                            break

                    if inc_node:
                        # 检查inc_node是否指向decision_node（形成闭环）
                        inc_to_decision = any(e.from_node == inc_node and e.to_node == decision_node.id for e in graph.edges)

                        if inc_to_decision:
                            # 找到开始和结束节点
                            start_nodes = [n.id for n in graph.nodes.values() if n.node_type == 'start_end']
                            init_node = None

                            # 找到指向decision_node的另一个节点（初始化节点）
                            init_node = None
                            for e in incoming_edges:
                                if e.from_node != inc_node:
                                    init_node = e.from_node
                                    break

                            # 找到"否"分支指向的结束节点
                            end_node = None
                            for e in graph.edges:
                                if e.from_node == decision_node.id and e.label not in ['是', '条件成立', 'yes', 'Y']:
                                    end_node = e.to_node
                                    break

                            return True, {
                                'start': start_nodes[0] if len(start_nodes) > 0 else None,
                                'init': init_node,
                                'decision': decision_node.id,
                                'body': yes_node,
                                'inc': inc_node,
                                'end': end_node
                            }

        return False, {}

    def _detect_switch_case(self, graph: FlowchartGraph) -> Tuple[bool, Dict[str, Any]]:
        """检测是否为switch case模式

        Switch case特征：
        1. 只有一个判断框
        2. 判断框有多个出边（多个case分支）
        3. 所有分支最终汇合到同一个结束节点

        Returns:
            (is_switch_case, switch_nodes)
            switch_nodes包含：start, init, decision, branches, end
        """
        decision_nodes = [n for n in graph.nodes.values() if n.node_type == 'decision']

        # 只有一个判断框
        if len(decision_nodes) != 1:
            return False, {}

        decision_node = decision_nodes[0]

        # 找到判断框的所有出边
        outgoing_edges = [e for e in graph.edges if e.from_node == decision_node.id]

        # 判断框应该有多个出边（至少3个：2个case + 1个default）
        if len(outgoing_edges) < 3:
            return False, {}

        # 找到所有分支节点
        branch_nodes = []
        for edge in outgoing_edges:
            branch_nodes.append(edge.to_node)

        # 检查所有分支是否都指向同一个结束节点
        end_nodes = set()
        for branch_id in branch_nodes:
            for edge in graph.edges:
                if edge.from_node == branch_id:
                    end_nodes.add(edge.to_node)

        # 所有分支应该指向同一个结束节点
        if len(end_nodes) != 1:
            return False, {}

        end_node = list(end_nodes)[0]

        # 找到开始节点
        start_nodes = [n.id for n in graph.nodes.values() if n.node_type == 'start_end']
        if not start_nodes:
            return False, {}

        # 找到初始化节点（指向判断框的节点）
        incoming_edges = [e for e in graph.edges if e.to_node == decision_node.id]
        if not incoming_edges:
            return False, {}

        init_node = incoming_edges[0].from_node

        return True, {
            'start': start_nodes[0],
            'init': init_node,
            'decision': decision_node.id,
            'branches': branch_nodes,
            'end': end_node
        }

    def _topological_sort(self, graph: FlowchartGraph) -> List[str]:
        """拓扑排序"""
        # 计算入度
        in_degree = {node_id: 0 for node_id in graph.nodes}
        for edge in graph.edges:
            in_degree[edge.to_node] += 1

        # BFS
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            for edge in graph.edges:
                if edge.from_node == node_id:
                    in_degree[edge.to_node] -= 1
                    if in_degree[edge.to_node] == 0:
                        queue.append(edge.to_node)

        return result

    def _calculate_levels(self, graph: FlowchartGraph, ordered_nodes: List[str]) -> Dict[str, int]:
        """计算节点层级"""
        levels = {}
        for node_id in ordered_nodes:
            # 找到所有前驱节点
            predecessors = [e.from_node for e in graph.edges if e.to_node == node_id]
            if not predecessors:
                levels[node_id] = 0
            else:
                levels[node_id] = max(levels.get(p, 0) for p in predecessors) + 1
        return levels

    def _calculate_node_size(self, node: FlowchartNode):
        """计算节点大小"""
        # 计算文本大小
        bbox = self.font.getbbox(node.label)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 节点大小 = 文本大小 + 内边距
        node.width = max(text_width + self.node_padding * 2, self.node_min_width)
        node.height = max(text_height + self.node_padding * 2, self.node_min_height)

    def _layout_top_down(self, graph: FlowchartGraph, level_groups: Dict[int, List[str]]):
        """从上到下布局，支持判断框出线规范"""
        # 首先进行基础布局
        y = 0
        for level in sorted(level_groups.keys()):
            node_ids = level_groups[level]
            total_width = len(node_ids) * self.node_min_width + (len(node_ids) - 1) * self.horizontal_spacing
            x = -total_width / 2

            for node_id in node_ids:
                node = graph.nodes[node_id]
                node.x = x + node.width / 2
                node.y = y + node.height / 2
                x += node.width + self.horizontal_spacing

            y += self.node_min_height + self.vertical_spacing

        # 调整判断框的子节点位置
        for edge in graph.edges:
            from_node = graph.nodes[edge.from_node]
            to_node = graph.nodes[edge.to_node]

            # 判断框出线规范
            if from_node.node_type == 'decision':
                if edge.label in ['是', '条件成立', 'yes', 'Y']:
                    # 条件成立：正下方，与判断框垂直对齐
                    to_node.x = from_node.x
                else:
                    # 条件不成立：右中方，水平出线到右边
                    # 将目标节点移到判断框右边
                    to_node.x = from_node.x + from_node.width + self.horizontal_spacing
                    # 与"条件成立"的方框在同一水平线上
                    # 找到"条件成立"的目标节点
                    for e in graph.edges:
                        if e.from_node == from_node.id and e.label in ['是', '条件成立', 'yes', 'Y']:
                            to_node.y = graph.nodes[e.to_node].y
                            break

        # 处理switch case：多个判断框串联的情况
        # 找到所有判断框，检查是否有多个判断框串联
        decision_nodes = [n for n in graph.nodes.values() if n.node_type == 'decision']
        if len(decision_nodes) > 1:
            # 检查是否有判断框的"否"分支指向另一个判断框
            for decision in decision_nodes:
                for edge in graph.edges:
                    if edge.from_node == decision.id and edge.label not in ['是', '条件成立', 'yes', 'Y']:
                        target_node = graph.nodes[edge.to_node]
                        if target_node.node_type == 'decision':
                            # 将目标判断框移到当前判断框右边
                            target_node.x = decision.x + decision.width + self.horizontal_spacing
                            # 保持在同一水平线上
                            target_node.y = decision.y

    def _layout_for_loop(self, graph: FlowchartGraph, loop_nodes: Dict[str, str]):
        """For循环专用布局"""
        y = 0

        # 计算左侧需要的空间（半个框长度用于左侧出线）
        decision_node = graph.nodes[loop_nodes['decision']]
        left_margin = decision_node.width

        # 开始节点
        if loop_nodes.get('start'):
            start_node = graph.nodes[loop_nodes['start']]
            start_node.x = left_margin
            start_node.y = y + start_node.height / 2
            y += start_node.height + self.vertical_spacing

        # 初始化节点
        if loop_nodes.get('init'):
            init_node = graph.nodes[loop_nodes['init']]
            init_node.x = left_margin
            init_node.y = y + init_node.height / 2
            y += init_node.height + self.vertical_spacing

        # 判断节点
        decision_node.x = left_margin
        decision_node.y = y + decision_node.height / 2

        # 循环体节点（在判断节点正下方）
        body_node = graph.nodes[loop_nodes['body']]
        body_node.x = left_margin
        body_node.y = decision_node.y + decision_node.height + self.vertical_spacing

        # 增量节点（在判断节点右侧）
        inc_node = graph.nodes[loop_nodes['inc']]
        inc_node.x = left_margin + decision_node.width / 2 + inc_node.width / 2 + self.horizontal_spacing * 1.2
        inc_node.y = decision_node.y

        # 结束节点（在循环体节点下方）
        if loop_nodes.get('end'):
            end_node = graph.nodes[loop_nodes['end']]
            end_node.x = left_margin
            end_node.y = body_node.y + body_node.height + self.vertical_spacing

    def _layout_switch_case(self, graph: FlowchartGraph, switch_nodes: Dict[str, Any]):
        """Switch case专用布局

        布局要求：
        1. 开始→初始化→判断框（垂直排列，居中）
        2. 所有分支执行框并行排布（同一水平线）
        3. 结束框与开始框竖向对齐（同一垂直线）
        """
        y = 0
        decision_node = graph.nodes[switch_nodes['decision']]
        branch_nodes = switch_nodes['branches']
        branch_count = len(branch_nodes)

        # 计算总宽度：分支数 * 节点宽度 + (分支数-1) * 间距
        total_width = branch_count * self.node_min_width + (branch_count - 1) * self.horizontal_spacing
        start_x = -total_width / 2

        # 开始节点（居中）
        start_node = graph.nodes[switch_nodes['start']]
        start_node.x = 0
        start_node.y = y + start_node.height / 2
        y += start_node.height + self.vertical_spacing

        # 初始化节点（居中）
        init_node = graph.nodes[switch_nodes['init']]
        init_node.x = 0
        init_node.y = y + init_node.height / 2
        y += init_node.height + self.vertical_spacing

        # 判断节点（居中）
        decision_node.x = 0
        decision_node.y = y + decision_node.height / 2

        # 分支执行框（并行排布，同一水平线）
        branch_y = decision_node.y + decision_node.height + self.vertical_spacing * 2
        for i, branch_id in enumerate(branch_nodes):
            branch_node = graph.nodes[branch_id]
            branch_node.x = start_x + i * (self.node_min_width + self.horizontal_spacing) + self.node_min_width / 2
            branch_node.y = branch_y + branch_node.height / 2

        # 结束节点（与开始框竖向对齐，即x=0）
        end_node = graph.nodes[switch_nodes['end']]
        end_node.x = 0
        end_node.y = branch_y + self.node_min_height + self.vertical_spacing * 2

    def _layout_left_right(self, graph: FlowchartGraph, level_groups: Dict[int, List[str]]):
        """从左到右布局"""
        x = 0
        for level in sorted(level_groups.keys()):
            node_ids = level_groups[level]
            total_height = len(node_ids) * self.node_min_height + (len(node_ids) - 1) * self.vertical_spacing
            y = -total_height / 2

            for node_id in node_ids:
                node = graph.nodes[node_id]
                node.x = x + node.width / 2
                node.y = y + node.height / 2
                y += node.height + self.vertical_spacing

            x += self.node_min_width + self.horizontal_spacing

    def _calculate_canvas_size(self, graph: FlowchartGraph) -> Tuple[int, int]:
        """计算画布大小"""
        if not graph.nodes:
            return (100, 100)

        min_x = min(node.x - node.width / 2 for node in graph.nodes.values())
        max_x = max(node.x + node.width / 2 for node in graph.nodes.values())
        min_y = min(node.y - node.height / 2 for node in graph.nodes.values())
        max_y = max(node.y + node.height / 2 for node in graph.nodes.values())

        return (int(max_x - min_x), int(max_y - min_y))

    def _draw_node(self, draw: ImageDraw.Draw, node: FlowchartNode, padding: int):
        """绘制节点"""
        scale = getattr(self, 'scale', 1.0)
        x = (node.x + padding) * scale
        y = (node.y + padding) * scale
        w = node.width * scale
        h = node.height * scale

        # 计算边界框
        left = x - w / 2
        top = y - h / 2
        right = x + w / 2
        bottom = y + h / 2

        # 根据节点类型绘制形状
        if node.node_type == 'start_end':
            # 端点符：椭圆（更明显）
            draw.ellipse([left, top, right, bottom],
                        fill=self.fill_color, outline=self.line_color, width=2)
        elif node.node_type == 'decision':
            # 判断：菱形
            points = [
                (x, top),  # 上
                (right, y),  # 右
                (x, bottom),  # 下
                (left, y),  # 左
            ]
            draw.polygon(points, fill=self.fill_color, outline=self.line_color)
            draw.line(points + [points[0]], fill=self.line_color, width=2)
        elif node.node_type == 'data':
            # 数据符号：平行四边形
            offset = w * 0.15
            points = [
                (left + offset, top),  # 左上
                (right, top),  # 右上
                (right - offset, bottom),  # 右下
                (left, bottom),  # 左下
            ]
            draw.polygon(points, fill=self.fill_color, outline=self.line_color)
            draw.line(points + [points[0]], fill=self.line_color, width=2)
        elif node.node_type == 'connector':
            # 连接符：圆形
            radius = min(w, h) / 2
            draw.ellipse([left, top, right, bottom], fill=self.fill_color, outline=self.line_color, width=2)
        elif node.node_type == 'loop':
            # 循环界限：去角矩形
            corner = min(w, h) / 4
            points = [
                (left + corner, top),
                (right - corner, top),
                (right, top + corner),
                (right, bottom - corner),
                (right - corner, bottom),
                (left + corner, bottom),
                (left, bottom - corner),
                (left, top + corner),
            ]
            draw.polygon(points, fill=self.fill_color, outline=self.line_color)
            draw.line(points + [points[0]], fill=self.line_color, width=2)
        else:
            # 处理符号：矩形
            draw.rectangle([left, top, right, bottom], fill=self.fill_color, outline=self.line_color, width=2)

        # 绘制文本（居中）
        bbox = self.font.getbbox(node.label)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = x - text_width / 2
        text_y = y - text_height / 2
        draw.text((text_x, text_y), node.label, fill=self.text_color, font=self.font)

    def _draw_edge(self, draw: ImageDraw.Draw, graph: FlowchartGraph, edge: FlowchartEdge, padding: int):
        """绘制边 - 不允许斜线，只允许水平线和垂直线"""
        scale = getattr(self, 'scale', 1.0)
        from_node = graph.nodes[edge.from_node]
        to_node = graph.nodes[edge.to_node]

        # 先检测是否为for循环
        is_for_loop, loop_nodes = self._detect_for_loop(graph)
        # 检测是否为switch case
        is_switch_case, switch_nodes = self._detect_switch_case(graph)

        if is_for_loop:
            # For循环专用走线
            self._draw_for_loop_edge(draw, graph, edge, padding, loop_nodes)
            return

        if is_switch_case:
            # Switch case专用走线
            self._draw_switch_case_edge(draw, graph, edge, padding, switch_nodes)
            return

        # 判断框出线规范
        if from_node.node_type == 'decision' and graph.direction == 'TD':
            if edge.label in ['是', '条件成立', 'yes', 'Y']:
                # 条件成立：正下方，垂直线
                start_x = (from_node.x + padding) * scale
                start_y = (from_node.y + from_node.height / 2 + padding) * scale
                end_x = (to_node.x + padding) * scale
                end_y = (to_node.y - to_node.height / 2 + padding) * scale

                # 绘制垂直线
                draw.line([(start_x, start_y), (end_x, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, start_x, start_y, end_x, end_y)

                # 保存这条线的中间位置，用于"条件不成立"线路的连接
                self._decision_yes_mid_y = (start_y + end_y) / 2

                # 绘制标签
                if edge.label:
                    label_x = start_x + 10 * scale
                    label_y = (start_y + end_y) / 2
                    bbox = self.font.getbbox(edge.label)
                    text_width = bbox[2] - bbox[0]
                    draw.text((label_x - text_width / 2, label_y), edge.label, fill=self.text_color, font=self.font)
            else:
                # 条件不成立：右中方，先水平向右，再垂直向下，再水平向左
                # 第一步：从判断框右中方水平向右
                start_x = (from_node.x + from_node.width / 2 + padding) * scale
                start_y = (from_node.y + padding) * scale

                # 水平到目标节点的x位置
                mid_x1 = (to_node.x + padding) * scale
                mid_y1 = start_y

                # 绘制水平线
                draw.line([(start_x, start_y), (mid_x1, mid_y1)], fill=self.line_color, width=2)

                # 第二步：垂直向下到目标节点上方
                end_y = (to_node.y - to_node.height / 2 + padding) * scale
                draw.line([(mid_x1, mid_y1), (mid_x1, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, mid_x1, mid_y1, mid_x1, end_y)

                # 绘制标签
                if edge.label:
                    label_x = (start_x + mid_x1) / 2
                    label_y = start_y - 15 * scale
                    bbox = self.font.getbbox(edge.label)
                    text_width = bbox[2] - bbox[0]
                    draw.text((label_x - text_width / 2, label_y), edge.label, fill=self.text_color, font=self.font)
        else:
            # 普通边：不允许斜线，使用折线连接
            # 策略：竖线减半，然后左折到结束框上方的垂直线上
            if graph.direction == 'TD':
                start_x = (from_node.x + padding) * scale
                start_y = (from_node.y + from_node.height / 2 + padding) * scale
                end_x = (to_node.x + padding) * scale
                end_y = (to_node.y - to_node.height / 2 + padding) * scale
            else:
                start_x = (from_node.x + from_node.width / 2 + padding) * scale
                start_y = (from_node.y + padding) * scale
                end_x = (to_node.x - to_node.width / 2 + padding) * scale
                end_y = (to_node.y + padding) * scale

            # 策略：
            # 1. 如果起点和终点x相同：直接垂直线
            # 2. 否则：竖线减半，然后水平到结束框的垂直线上
            if abs(start_x - end_x) < 1:
                # 同一垂直线，直接连接
                draw.line([(start_x, start_y), (end_x, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, start_x, start_y, end_x, end_y)
            else:
                # 第一步：竖线长度减半（走到起点和终点中间的位置）
                mid_y = (start_y + end_y) / 2
                draw.line([(start_x, start_y), (start_x, mid_y)], fill=self.line_color, width=2)

                # 第二步：水平移动到结束框的垂直线上（end_x）
                draw.line([(start_x, mid_y), (end_x, mid_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, start_x, mid_y, end_x, mid_y)

            # 绘制标签
            if edge.label:
                mid_x = (start_x + end_x) / 2
                mid_y_label = (start_y + end_y) / 2
                bbox = self.font.getbbox(edge.label)
                text_width = bbox[2] - bbox[0]
                draw.text((mid_x - text_width / 2, mid_y_label - 10 * scale), edge.label, fill=self.text_color, font=self.font)

    def _draw_arrow(self, draw: ImageDraw.Draw, x1: float, y1: float, x2: float, y2: float):
        """绘制箭头"""
        arrow_size = 10
        angle = math.atan2(y2 - y1, x2 - x1)

        # 箭头两个点
        arrow_x1 = x2 - arrow_size * math.cos(angle - math.pi / 6)
        arrow_y1 = y2 - arrow_size * math.sin(angle - math.pi / 6)
        arrow_x2 = x2 - arrow_size * math.cos(angle + math.pi / 6)
        arrow_y2 = y2 - arrow_size * math.sin(angle + math.pi / 6)

        draw.polygon([(x2, y2), (arrow_x1, arrow_y1), (arrow_x2, arrow_y2)],
                      fill=self.line_color, outline=self.line_color)

    def _draw_for_loop_edge(self, draw: ImageDraw.Draw, graph: FlowchartGraph, edge: FlowchartEdge, padding: int, loop_nodes: Dict[str, str]):
        """绘制For循环专用边"""
        scale = getattr(self, 'scale', 1.0)
        from_node = graph.nodes[edge.from_node]
        to_node = graph.nodes[edge.to_node]

        # 判断是否为循环体到增量节点的边
        if edge.from_node == loop_nodes.get('body') and edge.to_node == loop_nodes.get('inc'):
            # 循环处理框 -> 循环变量操作框：右侧出横线，然后上折
            body_node = graph.nodes[loop_nodes['body']]
            inc_node = graph.nodes[loop_nodes['inc']]

            start_x = (body_node.x + body_node.width / 2 + padding) * scale
            start_y = (body_node.y + padding) * scale

            mid_x = (inc_node.x + padding) * scale
            mid_y = start_y

            # 向右横线
            draw.line([(start_x, start_y), (mid_x, mid_y)], fill=self.line_color, width=2)

            # 向上到增量节点下方边框中点
            end_x = (inc_node.x + padding) * scale
            end_y = (inc_node.y + inc_node.height / 2 + padding) * scale
            draw.line([(mid_x, mid_y), (mid_x, end_y - 5 * scale)], fill=self.line_color, width=2)

            # 箭头指向增量节点下方边框中点
            self._draw_arrow(draw, mid_x, mid_y, mid_x, end_y)
            return

        # 判断是否为增量操作返回判断节点的边
        if edge.from_node == loop_nodes.get('inc') and edge.to_node == loop_nodes.get('decision'):
            # 循环变量操作框 -> 判断框：上方出线，先上竖，再左折到判断框正上方的线上
            inc_node = graph.nodes[loop_nodes['inc']]
            decision_node = graph.nodes[loop_nodes['decision']]
            init_node = graph.nodes[loop_nodes['init']]

            # 从增量节点上方出线
            start_x = (inc_node.x + padding) * scale
            start_y = (inc_node.y - inc_node.height / 2 + padding) * scale

            # 上竖到判断框上方一定距离
            up_y = (decision_node.y - decision_node.height / 2 - self.vertical_spacing * 0.5 + padding) * scale
            draw.line([(start_x, start_y), (start_x, up_y)], fill=self.line_color, width=2)

            # 左折到判断框正上方（连接到初始化节点到判断框的垂直线上）
            init_x = (init_node.x + padding) * scale
            draw.line([(start_x, up_y), (init_x, up_y)], fill=self.line_color, width=2)

            # 箭头指向左边（指向初始化节点到判断框的垂直线）
            self._draw_arrow(draw, start_x, up_y, init_x, up_y)
            return

        # 判断是否为判断节点到循环体的边（是分支）
        if edge.from_node == loop_nodes.get('decision') and edge.to_node == loop_nodes.get('body'):
            # 判断 -> 循环体：垂直向下
            decision_node = graph.nodes[loop_nodes['decision']]
            body_node = graph.nodes[loop_nodes['body']]

            start_x = (decision_node.x + padding) * scale
            start_y = (decision_node.y + decision_node.height / 2 + padding) * scale
            end_x = (body_node.x + padding) * scale
            end_y = (body_node.y - body_node.height / 2 + padding) * scale

            draw.line([(start_x, start_y), (end_x, end_y)], fill=self.line_color, width=2)
            self._draw_arrow(draw, start_x, start_y, end_x, end_y)

            # 绘制标签
            if edge.label:
                label_x = start_x + 10 * scale
                label_y = (start_y + end_y) / 2
                bbox = self.font.getbbox(edge.label)
                text_width = bbox[2] - bbox[0]
                draw.text((label_x - text_width / 2, label_y), edge.label, fill=self.text_color, font=self.font)
            return

        # 判断是否为判断节点到结束节点的边（否分支）
        if edge.from_node == loop_nodes.get('decision') and edge.to_node == loop_nodes.get('end'):
            # 判断 -> 结束：左侧出线（左顶点），先左横半个框长度，再下竖，再右横到结束框上方，最后下连接到结束框
            decision_node = graph.nodes[loop_nodes['decision']]
            end_node = graph.nodes[loop_nodes['end']]
            body_node = graph.nodes[loop_nodes['body']]

            # 从判断框左顶点出线
            start_x = (decision_node.x - decision_node.width / 2 + padding) * scale
            start_y = (decision_node.y + padding) * scale

            # 先向左横半个框长度（确保不超出画布左边界）
            mid_x1 = max(5, start_x - decision_node.width / 2 * scale)
            draw.line([(start_x, start_y), (mid_x1, start_y)], fill=self.line_color, width=2)

            # 向下竖到结束框和处理数据框的中点
            body_bottom_y = (body_node.y + body_node.height / 2 + padding) * scale
            end_top_y = (end_node.y - end_node.height / 2 + padding) * scale
            mid_y1 = (body_bottom_y + end_top_y) / 2
            draw.line([(mid_x1, start_y), (mid_x1, mid_y1)], fill=self.line_color, width=2)

            # 向右横到结束节点正上方
            end_x = (end_node.x + padding) * scale
            draw.line([(mid_x1, mid_y1), (end_x, mid_y1)], fill=self.line_color, width=2)

            # 向下连接到结束节点上方边框中点
            draw.line([(end_x, mid_y1), (end_x, end_top_y)], fill=self.line_color, width=2)

            # 箭头指向结束节点上方边框中点
            self._draw_arrow(draw, end_x, mid_y1, end_x, end_top_y)

            # 绘制标签
            if edge.label:
                label_x = (start_x + mid_x1) / 2
                label_y = start_y - 15 * scale
                bbox = self.font.getbbox(edge.label)
                text_width = bbox[2] - bbox[0]
                draw.text((label_x - text_width / 2, label_y), edge.label, fill=self.text_color, font=self.font)
            return

        # 其他边：直接连接（开始->初始化，初始化->判断）
        if graph.direction == 'TD':
            start_x = (from_node.x + padding) * scale
            start_y = (from_node.y + from_node.height / 2 + padding) * scale
            end_x = (to_node.x + padding) * scale
            end_y = (to_node.y - to_node.height / 2 + padding) * scale
        else:
            start_x = (from_node.x + from_node.width / 2 + padding) * scale
            start_y = (from_node.y + padding) * scale
            end_x = (to_node.x - to_node.width / 2 + padding) * scale
            end_y = (to_node.y + padding) * scale

        draw.line([(start_x, start_y), (end_x, end_y)], fill=self.line_color, width=2)
        self._draw_arrow(draw, start_x, start_y, end_x, end_y)

    def _draw_switch_case_edge(self, draw: ImageDraw.Draw, graph: FlowchartGraph, edge: FlowchartEdge, padding: int, switch_nodes: Dict[str, Any]):
        """绘制Switch case专用边

        走线规范：
        1. 判断框到各分支操作框的连线：
           - 正下方：直接往下
           - 左侧：先向下竖（中点距离），然后向左到执行框中点上方，最后向下
           - 右侧：先向下竖（中点距离），然后向右到执行框中点上方，最后向下
        2. 各执行框到结束框的连线：
           - 正下方：直接往下
           - 左侧：先向下竖（中点距离），然后向左到结束框中点上方，最后向下
           - 右侧：先向下竖（中点距离），然后向右到结束框中点上方，最后向下
        """
        scale = getattr(self, 'scale', 1.0)
        from_node = graph.nodes[edge.from_node]
        to_node = graph.nodes[edge.to_node]

        decision_node = graph.nodes[switch_nodes['decision']]
        end_node = graph.nodes[switch_nodes['end']]
        branch_nodes = switch_nodes['branches']

        # 判断是否为判断框到分支的边
        if edge.from_node == switch_nodes['decision'] and edge.to_node in switch_nodes['branches']:
            # 判断框到分支执行框
            start_x = (decision_node.x + padding) * scale
            start_y = (decision_node.y + decision_node.height / 2 + padding) * scale
            end_x = (to_node.x + padding) * scale
            end_y = (to_node.y - to_node.height / 2 + padding) * scale

            # 计算中点距离
            mid_y = (start_y + end_y) / 2

            if abs(to_node.x - decision_node.x) < 1:
                # 正下方：直接往下
                draw.line([(start_x, start_y), (end_x, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, start_x, start_y, end_x, end_y)
            elif to_node.x < decision_node.x:
                # 左侧：先向下竖，然后向左，最后向下
                draw.line([(start_x, start_y), (start_x, mid_y)], fill=self.line_color, width=2)
                draw.line([(start_x, mid_y), (end_x, mid_y)], fill=self.line_color, width=2)
                draw.line([(end_x, mid_y), (end_x, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, end_x, mid_y, end_x, end_y)
            else:
                # 右侧：先向下竖，然后向右，最后向下
                draw.line([(start_x, start_y), (start_x, mid_y)], fill=self.line_color, width=2)
                draw.line([(start_x, mid_y), (end_x, mid_y)], fill=self.line_color, width=2)
                draw.line([(end_x, mid_y), (end_x, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, end_x, mid_y, end_x, end_y)

            # 绘制标签（放在横线上方，确保字整体在横线上方）
            if edge.label:
                label_x = end_x
                label_y = mid_y - 30 * scale
                bbox = self.font.getbbox(edge.label)
                text_width = bbox[2] - bbox[0]
                draw.text((label_x - text_width / 2, label_y), edge.label, fill=self.text_color, font=self.font)
            return

        # 判断是否为分支到结束框的边
        if edge.from_node in switch_nodes['branches'] and edge.to_node == switch_nodes['end']:
            # 分支执行框到结束框
            start_x = (from_node.x + padding) * scale
            start_y = (from_node.y + from_node.height / 2 + padding) * scale
            end_x = (end_node.x + padding) * scale
            end_y = (end_node.y - end_node.height / 2 + padding) * scale

            # 计算中点距离
            mid_y = (start_y + end_y) / 2

            if abs(from_node.x - end_node.x) < 1:
                # 正下方：直接往下
                draw.line([(start_x, start_y), (end_x, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, start_x, start_y, end_x, end_y)
            elif from_node.x < end_node.x:
                # 左侧：先向下竖，然后向右，最后向下
                draw.line([(start_x, start_y), (start_x, mid_y)], fill=self.line_color, width=2)
                draw.line([(start_x, mid_y), (end_x, mid_y)], fill=self.line_color, width=2)
                draw.line([(end_x, mid_y), (end_x, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, end_x, mid_y, end_x, end_y)
            else:
                # 右侧：先向下竖，然后向左，最后向下
                draw.line([(start_x, start_y), (start_x, mid_y)], fill=self.line_color, width=2)
                draw.line([(start_x, mid_y), (end_x, mid_y)], fill=self.line_color, width=2)
                draw.line([(end_x, mid_y), (end_x, end_y)], fill=self.line_color, width=2)
                self._draw_arrow(draw, end_x, mid_y, end_x, end_y)
            return

        # 其他边（开始->初始化，初始化->判断）
        if graph.direction == 'TD':
            start_x = (from_node.x + padding) * scale
            start_y = (from_node.y + from_node.height / 2 + padding) * scale
            end_x = (to_node.x + padding) * scale
            end_y = (to_node.y - to_node.height / 2 + padding) * scale
        else:
            start_x = (from_node.x + from_node.width / 2 + padding) * scale
            start_y = (from_node.y + padding) * scale
            end_x = (to_node.x - to_node.width / 2 + padding) * scale
            end_y = (to_node.y + padding) * scale

        draw.line([(start_x, start_y), (end_x, end_y)], fill=self.line_color, width=2)
        self._draw_arrow(draw, start_x, start_y, end_x, end_y)


class FlowchartPythonRenderer:
    """Python绘图流程图渲染器"""

    def __init__(self, **options):
        """
        初始化渲染器

        Args:
            **options: 渲染选项
        """
        self.options = options
        self.parser = MermaidParser()
        self.painter = FlowchartPainter(**options)

    def render(self, code: str, output_path: str) -> bool:
        """
        渲染流程图

        Args:
            code: Mermaid代码
            output_path: 输出图片路径

        Returns:
            渲染是否成功
        """
        try:
            # 解析Mermaid代码
            graph = self.parser.parse(code)

            # 如果没有节点，返回失败
            if not graph.nodes:
                print("未找到有效的流程图节点")
                return False

            # 绘制流程图
            return self.painter.paint(graph, output_path)

        except Exception as e:
            print(f"流程图渲染失败: {e}")
            return False

    def is_available(self) -> bool:
        """检查渲染器是否可用"""
        return HAS_PIL
