"""
非 flowchart 图表的 Python/Pillow 渲染器
支持：sequenceDiagram（时序图）、pie（饼图）、gantt（甘特图）
"""

import re
import math
from typing import List, Dict, Optional
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ---------------------------------------------------------------------------
# 字体工具
# ---------------------------------------------------------------------------

def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取中文字体"""
    if not HAS_PIL:
        raise ImportError("Pillow is required")

    candidates = [
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        'C:\\Windows\\Fonts\\simhei.ttf',
        'C:\\Windows\\Fonts\\msyh.ttc',
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """简单文本换行"""
    lines = []
    for para in text.split('\n'):
        if not para:
            lines.append('')
            continue
        words = list(para)
        current = ''
        for ch in words:
            test = current + ch
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# 颜色方案
# ---------------------------------------------------------------------------

COLORS = {
    'text': (0, 44, 62),
    'line': (52, 73, 94),
    'fill': (236, 240, 241),
    'accent': (41, 128, 185),
    'bg': (255, 255, 255),
    'alt1': (231, 76, 60),
    'alt2': (46, 204, 113),
    'alt3': (241, 196, 15),
    'alt4': (155, 89, 182),
    'alt5': (52, 152, 219),
    'alt6': (230, 126, 34),
    'lifeline': (189, 195, 199),
    'activation': (236, 240, 241),
    'section_bg': (245, 245, 245),
    'grid_line': (220, 220, 220),
}

PALETTE = [COLORS['alt1'], COLORS['alt2'], COLORS['alt3'],
           COLORS['alt4'], COLORS['alt5'], COLORS['alt6'],
           COLORS['accent']]


# ===================================================================
# 时序图渲染器
# ===================================================================

class SequenceDiagramRenderer:
    """Mermaid sequenceDiagram → Pillow 渲染器"""

    PARTICIPANT_H = 36
    LIFELINE_TOP = 60
    PARTICIPANT_PAD = 80
    MARGIN = 60
    MESSAGE_H = 48
    ARROW_SIZE = 8
    ACTIVATION_W = 12

    def __init__(self, **options):
        self.font_size = options.get('font_size', 13)
        self.small_size = options.get('small_font_size', 11)
        self._font = None
        self._small = None

    def render(self, code: str, output_path: str) -> bool:
        if not HAS_PIL:
            return False

        self._font = _get_font(self.font_size)
        self._small = _get_font(self.small_size)
        draw_dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))

        # 解析
        participants, messages = self._parse(code)

        # 计算布局
        participant_names = list(participants.keys())
        if not participant_names:
            return False

        pw = self.PARTICIPANT_PAD
        n = len(participant_names)

        # 度量参与者名称宽度
        name_widths = {}
        for pname, alias in participants.items():
            display = f'{alias}\n<<{pname}>>' if alias != pname else pname
            max_w = 0
            for line in display.split('\n'):
                bbox = draw_dummy.textbbox((0, 0), line, font=self._font)
                max_w = max(max_w, bbox[2] - bbox[0])
            name_widths[pname] = max_w + 20

        total_w = max(
            self.MARGIN * 2 + n * pw,
            self.MARGIN * 2 + sum(name_widths.values()) + (n - 1) * pw
        )
        total_h = self.LIFELINE_TOP + len(messages) * self.MESSAGE_H + self.MARGIN + 40

        img = Image.new('RGB', (int(total_w), int(total_h)), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # 计算参与者 X 位置
        positions = {}
        x = self.MARGIN
        for i, pname in enumerate(participant_names):
            positions[pname] = x + name_widths[pname] / 2
            x += max(pw, name_widths[pname]) + pw

        # 绘制参与者矩形
        for pname, alias in participants.items():
            cx = positions[pname]
            display = alias if alias != pname else pname
            tw = name_widths[pname]
            rect = (cx - tw / 2, 10, cx + tw / 2, 10 + self.PARTICIPANT_H)
            draw.rectangle(rect, fill=COLORS['fill'], outline=COLORS['line'], width=2)
            bbox = draw.textbbox((0, 0), display, font=self._font)
            tx = cx - (bbox[2] - bbox[0]) / 2
            draw.text((tx, 12), display, fill=COLORS['text'], font=self._font)

        # 绘制生命线
        lifeline_bottom = self.LIFELINE_TOP + len(messages) * self.MESSAGE_H + 20
        for pname in participant_names:
            cx = positions[pname]
            ly = self.LIFELINE_TOP - 5
            draw.line([(cx, ly), (cx, lifeline_bottom)], fill=COLORS['lifeline'], width=1)
            # 虚线效果
            dash_len = 8
            for dy in range(0, int(lifeline_bottom - ly), dash_len * 2):
                y1 = ly + dy
                y2 = min(ly + dy + dash_len, lifeline_bottom)
                draw.line([(cx, y1), (cx, y2)], fill=COLORS['lifeline'], width=1)

        # 绘制消息
        for mi, msg in enumerate(messages):
            y = self.LIFELINE_TOP + mi * self.MESSAGE_H + 10
            a_name = msg['from']
            b_name = msg['to']
            if a_name not in positions or b_name not in positions:
                continue

            x1 = positions[a_name]
            x2 = positions[b_name]
            arrow_type = msg.get('arrow', '->>')
            label_text = msg.get('label', '')

            # 绘制消息箭头
            self._draw_message_arrow(draw, x1, x2, y, arrow_type, label_text, participants)

        # 保存
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output), 'PNG')
        return True

    def _parse(self, code: str):
        """解析 sequenceDiagram 语法"""
        participants = {}
        messages = []
        aliases = {}

        for line in code.strip().split('\n'):
            line = line.strip()
            if not line or line == 'sequenceDiagram':
                continue

            # participant Actor as "Display Name"
            m = re.match(r'participant\s+(\w+)(?:\s+as\s+(.+))?', line, re.IGNORECASE)
            if m:
                pid = m.group(1)
                alias = (m.group(2) or pid).strip().strip('"')
                participants[pid] = alias
                continue

            # actor Actor
            m = re.match(r'actor\s+(\w+)(?:\s+as\s+(.+))?', line, re.IGNORECASE)
            if m:
                pid = m.group(1)
                alias = (m.group(2) or pid).strip().strip('"')
                participants[pid] = alias
                continue

            # Message: A->>B: Text  or  A-->>B: Text  etc
            msg_match = re.match(
                r'(\w+)\s*(->>|-->>|->|-->|-\)>|\)-x|-x)\s*(\w+)\s*:\s*(.+)', line)
            if msg_match:
                a, arrow, b, label = msg_match.groups()
                if a not in participants:
                    participants[a] = a
                if b not in participants:
                    participants[b] = b
                messages.append({'from': a, 'to': b, 'arrow': arrow, 'label': label.strip()})
                continue

            # Message without label
            msg_match = re.match(r'(\w+)\s*(->>|-->>|->|-->|-\)>|\)-x|-x)\s*(\w+)\s*$', line)
            if msg_match:
                a, arrow, b = msg_match.groups()
                if a not in participants:
                    participants[a] = a
                if b not in participants:
                    participants[b] = b
                messages.append({'from': a, 'to': b, 'arrow': arrow, 'label': ''})
                continue

            # activate/deactivate
            if re.match(r'(activate|deactivate)\s+\w+', line, re.IGNORECASE):
                continue

            # note over
            if re.match(r'note\s+(over|right of|left of)', line, re.IGNORECASE):
                continue

        return participants, messages

    def _draw_message_arrow(self, draw, x1, x2, y, arrow_type, label, participants):
        """绘制消息箭头"""
        is_dashed = '--' in arrow_type or 'x' in arrow_type
        is_async = arrow_type.endswith('>>')
        is_lost = arrow_type.endswith('x')

        left_to_right = x1 < x2
        if not left_to_right:
            arrow_type = arrow_type.replace('>', '<').replace('-<', '->').replace('<<', '>>')

        # 文本标签
        label_y = y - 18
        if label:
            bbox = draw.textbbox((0, 0), label, font=self._font)
            tw = bbox[2] - bbox[0]
            label_x = (x1 + x2) / 2 - tw / 2
            draw.text((label_x, label_y), label, fill=COLORS['text'], font=self._font)

        # 连线
        if left_to_right:
            line_start = (x1 + self.ACTIVATION_W, y)
            line_end = (x2 - self.ACTIVATION_W - self.ARROW_SIZE, y)
        else:
            line_start = (x1 - self.ACTIVATION_W, y)
            line_end = (x2 + self.ACTIVATION_W + self.ARROW_SIZE, y)

        if is_dashed:
            self._draw_dashed_line(draw, line_start, line_end, COLORS['line'])
        else:
            draw.line([line_start, line_end], fill=COLORS['line'], width=2)

        # 箭头
        if left_to_right:
            tip = line_end
            points = [
                (tip[0], tip[1]),
                (tip[0] - self.ARROW_SIZE, tip[1] - self.ARROW_SIZE / 2),
                (tip[0] - self.ARROW_SIZE, tip[1] + self.ARROW_SIZE / 2),
            ]
        else:
            tip = line_end
            points = [
                (tip[0], tip[1]),
                (tip[0] + self.ARROW_SIZE, tip[1] - self.ARROW_SIZE / 2),
                (tip[0] + self.ARROW_SIZE, tip[1] + self.ARROW_SIZE / 2),
            ]

        if is_lost:
            x_line = (line_end[0] + (line_start[0] - line_end[0]) / 2)
            draw.line([(x_line, y - 8), (x_line + 8, y + 8)], fill=COLORS['alt1'], width=2)
            draw.line([(x_line, y + 8), (x_line + 8, y - 8)], fill=COLORS['alt1'], width=2)
        elif is_async:
            draw.polygon(points, fill=COLORS['bg'], outline=COLORS['line'])
        else:
            draw.polygon(points, fill=COLORS['line'])

    @staticmethod
    def _draw_dashed_line(draw, pt1, pt2, color, dash=6, gap=4):
        """绘制虚线"""
        x1, y1 = pt1
        x2, y2 = pt2
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return
        ux, uy = dx / length, dy / length
        pos = 0.0
        while pos < length:
            seg_end = min(pos + dash, length)
            draw.line([
                (x1 + ux * pos, y1 + uy * pos),
                (x1 + ux * seg_end, y1 + uy * seg_end)
            ], fill=color, width=2)
            pos = seg_end + gap


# ===================================================================
# 饼图渲染器
# ===================================================================

class PieChartRenderer:
    """Mermaid pie → Pillow 渲染器"""

    RADIUS = 180
    CENTER_MARGIN = 240
    LEGEND_X = 420
    LEGEND_LINE_H = 28

    def __init__(self, **options):
        self.font_size = options.get('font_size', 14)
        self.title_size = options.get('title_font_size', 22)
        self._font = None
        self._title_font = None

    def render(self, code: str, output_path: str) -> bool:
        if not HAS_PIL:
            return False

        self._font = _get_font(self.font_size)
        self._title_font = _get_font(self.title_size)
        draw_dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))

        title, slices = self._parse(code)
        if not slices:
            return False

        # 布局计算
        legend_items = []
        max_lw = 0
        for label, val in slices:
            pct = val / sum(s[1] for s in slices) * 100
            item = f'{label} ({val} / {pct:.1f}%)'
            legend_items.append((item, PALETTE[len(legend_items) % len(PALETTE)]))
            bbox = draw_dummy.textbbox((0, 0), item, font=self._font)
            max_lw = max(max_lw, bbox[2] - bbox[0])

        legend_h = len(legend_items) * self.LEGEND_LINE_H + 20
        total_w = self.LEGEND_X + max_lw + 60
        total_h = max(self.CENTER_MARGIN * 2 + self.RADIUS * 2 + 60, legend_h + 80)

        # 标题
        title_h = 0
        if title:
            title_h = self.title_size + 20

        img = Image.new('RGB', (int(total_w), int(total_h + title_h)), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # 绘制标题
        if title:
            tb = draw.textbbox((0, 0), title, font=self._title_font)
            tx = (total_w - (tb[2] - tb[0])) / 2
            draw.text((tx, 15), title, fill=COLORS['text'], font=self._title_font)

        # 饼图圆心
        cx = self.CENTER_MARGIN
        cy = self.CENTER_MARGIN + title_h

        # 绘制扇形
        total = sum(s[1] for s in slices)
        start_angle = -90
        for i, (label, val) in enumerate(slices):
            angle = val / total * 360
            end_angle = start_angle + angle
            color = PALETTE[i % len(PALETTE)]

            # 用多边形近似弧
            steps = max(int(angle * 2), 20)
            points = []
            for step in range(steps + 1):
                a = math.radians(start_angle + angle * step / steps)
                x = cx + self.RADIUS * math.cos(a)
                y = cy + self.RADIUS * math.sin(a)
                points.append((x, y))
            points.insert(0, (cx, cy))

            if points:
                draw.polygon(points, fill=color, outline=COLORS['bg'], width=1)

            # 百分比标签（在扇形中间）
            if angle > 15:
                mid_a = math.radians(start_angle + angle / 2)
                lx = cx + self.RADIUS * 0.65 * math.cos(mid_a)
                ly = cy + self.RADIUS * 0.65 * math.sin(mid_a)
                pct_text = f'{angle:.1f}%' if angle < 360 else ''
                if pct_text:
                    pbbox = draw.textbbox((0, 0), pct_text, font=self._font)
                    draw.text(
                        (lx - (pbbox[2] - pbbox[0]) / 2, ly - (pbbox[3] - pbbox[1]) / 2),
                        pct_text, fill=COLORS['bg'], font=self._font)

            start_angle = end_angle

        # 绘制图例
        leg_x = self.LEGEND_X
        leg_y = title_h + 30
        for i, (item, color) in enumerate(legend_items):
            ly = leg_y + i * self.LEGEND_LINE_H
            draw.rectangle([(leg_x, ly), (leg_x + 16, ly + 16)], fill=color, outline=COLORS['line'])
            draw.text((leg_x + 24, ly - 2), item, fill=COLORS['text'], font=self._font)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output), 'PNG')
        return True

    def _parse(self, code: str):
        """解析 pie 语法"""
        title = ''
        slices = []
        for line in code.strip().split('\n'):
            line = line.strip()
            if not line or line == 'pie':
                continue
            if line.lower().startswith('title '):
                title = line[6:].strip()
                continue
            # "Label": value
            m = re.match(r'"([^"]*)"\s*:\s*([\d.]+)', line)
            if m:
                name = m.group(1)
                val = float(m.group(2))
                slices.append((name, val))
        return title, slices


# ===================================================================
# 甘特图渲染器
# ===================================================================

class GanttChartRenderer:
    """Mermaid gantt → Pillow 渲染器（简化版）"""

    TASK_H = 30
    MARGIN_LEFT = 220
    MARGIN_TOP = 80
    DAY_W = 2.0  # 每天像素宽度
    HEADER_H = 30

    def __init__(self, **options):
        self.font_size = options.get('font_size', 11)
        self.title_size = options.get('title_font_size', 16)
        self._font = None
        self._title_font = None

    def render(self, code: str, output_path: str) -> bool:
        if not HAS_PIL:
            return False

        self._font = _get_font(self.font_size)
        self._title_font = _get_font(self.title_size)

        title, sections = self._parse(code)
        if not sections:
            return False

        # 计算日期范围
        all_dates = []
        for sec_name, tasks in sections:
            for t in tasks:
                if t['start_date']:
                    all_dates.append(t['start_date'])
                if t['end_date']:
                    all_dates.append(t['end_date'])

        if not all_dates:
            return False

        min_date = min(all_dates)
        max_date = max(all_dates)
        total_days = max((max_date - min_date).days, 1)

        # 总任务数
        total_tasks = sum(len(tasks) for _, tasks in sections)

        # 画布尺寸
        day_w_px = max(self.DAY_W, 800.0 / total_days) if total_days > 0 else 2
        gantt_w = total_days * day_w_px + 40
        total_w = self.MARGIN_LEFT + gantt_w + 20
        section_header_h = 26
        total_h = self.MARGIN_TOP + sum(
            section_header_h + len(tasks) * self.TASK_H
            for _, tasks in sections
        ) + 60

        title_h = self.title_size + 20 if title else 0
        img = Image.new('RGB', (int(total_w), int(total_h + title_h)), COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # 标题
        y_offset = title_h
        if title:
            tb = draw.textbbox((0, 0), title, font=self._title_font)
            tx = (total_w - (tb[2] - tb[0])) / 2
            draw.text((tx, 10), title, fill=COLORS['text'], font=self._title_font)

        # 网格线
        cy = self.MARGIN_TOP + y_offset
        month_names = ['1月', '2月', '3月', '4月', '5月', '6月',
                       '7月', '8月', '9月', '10月', '11月', '12月']

        # 月头
        prev_month = None
        for d in range(total_days + 1):
            dt = min_date + __import__('datetime').timedelta(days=d)
            x = self.MARGIN_LEFT + d * day_w_px
            if dt.month != prev_month:
                prev_month = dt.month
                month_str = month_names[dt.month - 1]
                draw.text((x - 4, self.MARGIN_TOP + y_offset - self.HEADER_H + 4),
                          month_str, fill=COLORS['text'], font=self._font)
                draw.line([(x, self.MARGIN_TOP + y_offset - 5),
                           (x, total_h - 10)], fill=COLORS['grid_line'], width=1)

        # 今日线
        today = __import__('datetime').date.today()
        if min_date <= today <= max_date:
            td = (today - min_date).days
            tx = self.MARGIN_LEFT + td * day_w_px
            draw.line([(tx, self.MARGIN_TOP + y_offset), (tx, total_h - 10)],
                      fill=COLORS['alt1'], width=2)

        # 绘制各节
        cur_y = self.MARGIN_TOP + y_offset
        color_idx = 0
        for sec_name, tasks in sections:
            # 节标题
            draw.rectangle(
                [(self.MARGIN_LEFT - 10, cur_y),
                 (total_w - 10, cur_y + section_header_h)],
                fill=COLORS['section_bg'], outline=COLORS['grid_line'])
            draw.text((10, cur_y + 4), sec_name, fill=COLORS['text'], font=self._font)
            cur_y += section_header_h

            for task in tasks:
                # 任务标签
                label = task['name'][:24]
                bbox = draw.textbbox((0, 0), label, font=self._font)
                tw = bbox[2] - bbox[0]
                draw.text((self.MARGIN_LEFT - tw - 14, cur_y + 5),
                          label, fill=COLORS['text'], font=self._font)

                # 任务条
                if task['start_date'] and task['end_date']:
                    s_days = (task['start_date'] - min_date).days
                    e_days = (task['end_date'] - min_date).days
                    bar_x = self.MARGIN_LEFT + s_days * day_w_px
                    bar_w = max((e_days - s_days) * day_w_px, 4)
                    bar_y = cur_y + 4
                    bar_h = self.TASK_H - 8

                    color = PALETTE[color_idx % len(PALETTE)]
                    if task.get('critical'):
                        color = COLORS['alt1']

                    draw.rectangle(
                        [(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)],
                        fill=color, outline=self._darken(color), width=1)

                    # 任务名显示在条内（如果够宽）
                    if bar_w > tw + 10:
                        draw.text((bar_x + (bar_w - tw) / 2, bar_y + 3),
                                  label, fill=COLORS['bg'], font=self._font)

                cur_y += self.TASK_H
                color_idx += 1

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output), 'PNG')
        return True

    @staticmethod
    def _darken(color, factor=0.7):
        return tuple(int(c * factor) for c in color)

    def _parse(self, code: str):
        """解析 gantt 语法"""
        import datetime

        title = ''
        sections = []
        current_section = 'Tasks'
        current_tasks = []

        lines = code.strip().split('\n')
        date_format = '%Y-%m-%d'

        for line in lines:
            line = line.strip()
            if not line or line == 'gantt':
                continue
            if line.lower().startswith('title '):
                title = line[6:].strip()
                continue
            if line.lower().startswith('dateformat '):
                fmt = line[11:].strip()
                # 简化：只处理 YYYY-MM-DD
                if 'YYYY' in fmt and 'MM' in fmt and 'DD' in fmt:
                    date_format = '%Y-%m-%d'
                continue
            if line.lower().startswith('section '):
                if current_tasks:
                    sections.append((current_section, current_tasks))
                current_section = line[8:].strip()
                current_tasks = []
                continue

            # 任务行: TaskName :id, start, duration  或  TaskName :after id, duration
            task_match = re.match(
                r'([^:]+?)\s*:(?:\s*(\w+)\s*,\s*)?(.+)', line)
            if task_match:
                name = task_match.group(1).strip()
                task_id = task_match.group(2) or ''
                rest = task_match.group(3).strip()

                # 解析日期/时长
                parts = [p.strip() for p in rest.split(',')]
                start_date = None
                end_date = None
                duration_days = 0

                if len(parts) >= 2:
                    try:
                        # <date>, <days>d
                        start_date = datetime.datetime.strptime(parts[0], date_format).date()
                        dur_str = parts[1].strip()
                        if dur_str.endswith('d'):
                            duration_days = int(dur_str[:-1])
                        elif dur_str.endswith('w'):
                            duration_days = int(dur_str[:-1]) * 7
                        end_date = start_date + datetime.timedelta(days=duration_days)
                    except (ValueError, IndexError):
                        pass
                elif len(parts) == 1:
                    try:
                        # 可能是单个日期
                        start_date = datetime.datetime.strptime(parts[0], date_format).date()
                        duration_days = 7  # 默认一周
                        end_date = start_date + datetime.timedelta(days=duration_days)
                    except ValueError:
                        pass

                current_tasks.append({
                    'name': name,
                    'id': task_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration': duration_days,
                    'critical': 'crit' in line.lower(),
                })

        if current_tasks:
            sections.append((current_section, current_tasks))

        return title, sections


# ===================================================================
# 统一入口
# ===================================================================

class NonFlowchartRenderer:
    """非 flowchart 图表的统一 Python 渲染器"""

    def __init__(self, **options):
        self.sequence = SequenceDiagramRenderer(**options)
        self.pie = PieChartRenderer(**options)
        self.gantt = GanttChartRenderer(**options)

    def render(self, code: str, chart_type: str, output_path: str) -> bool:
        """根据 chart_type 路由到对应渲染器"""
        if chart_type == 'sequenceDiagram':
            return self.sequence.render(code, output_path)
        elif chart_type == 'pie':
            return self.pie.render(code, output_path)
        elif chart_type == 'gantt':
            return self.gantt.render(code, output_path)
        return False

    @staticmethod
    def is_available() -> bool:
        return HAS_PIL
