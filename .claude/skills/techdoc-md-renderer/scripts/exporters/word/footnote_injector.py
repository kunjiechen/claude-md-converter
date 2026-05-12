"""Word 原生脚注注入器

将 Markdown 脚注（[^label] + [^label]: definition）转换为 Word 原生 w:footnoteReference。
通过直接操作 docx zip 包注入 word/footnotes.xml。
"""

from typing import Any, Dict, List
import io
import zipfile

from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree


WML_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_NS = 'http://www.w3.org/XML/1998/namespace'


class FootnoteInjector:
    """管理脚注定义、引用和原生 OOXML 注入"""

    def __init__(self):
        self.defs: Dict[str, Dict] = {}          # label → {children, etc}
        self.label_to_id: Dict[str, int] = {}    # label → numeric ID

    def extract_from_ast(self, ast: List[Dict]) -> List[Dict]:
        """从 AST 中提取脚注定义，返回去除 footnote_block 后的 AST"""
        result = []
        for node in ast:
            if node.get('type') == 'footnote_block':
                next_id = 1
                for fn in node.get('children', []):
                    label = fn.get('attributes', {}).get('label', '')
                    if label:
                        self.defs[label] = fn
                        if label not in self.label_to_id:
                            self.label_to_id[label] = next_id
                            next_id += 1
            else:
                result.append(node)
        return result

    def add_reference(self, para, label: str):
        """在段落末尾添加原生 Word 脚注引用"""
        fid = self.label_to_id.get(label)
        if fid is None:
            run = para.add_run(f'[{label}]')
            run.font.superscript = True
            return

        run = OxmlElement('w:r')
        rPr = OxmlElement('w:rPr')
        rStyle = OxmlElement('w:rStyle')
        rStyle.set(qn('w:val'), 'FootnoteReference')
        rPr.append(rStyle)
        run.append(rPr)
        footnoteRef = OxmlElement('w:footnoteReference')
        footnoteRef.set(qn('w:id'), str(fid))
        run.append(footnoteRef)
        para._p.append(run)

    def build_footnotes_xml(self) -> bytes:
        """构建 word/footnotes.xml 内容"""
        w = WML_NS
        nsmap = {
            'w': w,
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
            'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
            'wpc': 'http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas',
        }
        footnotes = etree.Element(f'{{{w}}}footnotes', nsmap=nsmap)

        # 必须的分隔符脚注
        for fid_val, sep_name in [('-1', 'separator'), ('0', 'continuationSeparator')]:
            fn = etree.SubElement(footnotes, f'{{{w}}}footnote')
            fn.set(f'{{{w}}}id', fid_val)
            fn.set(f'{{{w}}}type', 'separator' if fid_val == '-1' else 'continuationSeparator')
            p = etree.SubElement(fn, f'{{{w}}}p')
            pPr = etree.SubElement(p, f'{{{w}}}pPr')
            spacing = etree.SubElement(pPr, f'{{{w}}}spacing')
            spacing.set(f'{{{w}}}after', '0')
            spacing.set(f'{{{w}}}line', '240')
            spacing.set(f'{{{w}}}lineRule', 'auto')
            r = etree.SubElement(p, f'{{{w}}}r')
            etree.SubElement(r, f'{{{w}}}{sep_name}')

        # 内容脚注
        label_order = sorted(self.label_to_id.items(), key=lambda x: x[1])
        for label, fid in label_order:
            fn_data = self.defs.get(label)
            if not fn_data:
                continue

            fn = etree.SubElement(footnotes, f'{{{w}}}footnote')
            fn.set(f'{{{w}}}id', str(fid))

            for child in fn_data.get('children', []):
                if child.get('type') != 'paragraph':
                    continue
                content = child.get('content', '')
                p = etree.SubElement(fn, f'{{{w}}}p')
                pPr = etree.SubElement(p, f'{{{w}}}pPr')
                pStyle = etree.SubElement(pPr, f'{{{w}}}pStyle')
                pStyle.set(f'{{{w}}}val', 'FootnoteText')
                spacing = etree.SubElement(pPr, f'{{{w}}}spacing')
                spacing.set(f'{{{w}}}after', '60')
                spacing.set(f'{{{w}}}line', '240')
                spacing.set(f'{{{w}}}lineRule', 'auto')

                # 脚注编号引用
                r1 = etree.SubElement(p, f'{{{w}}}r')
                rPr1 = etree.SubElement(r1, f'{{{w}}}rPr')
                rStyle1 = etree.SubElement(rPr1, f'{{{w}}}rStyle')
                rStyle1.set(f'{{{w}}}val', 'FootnoteReference')
                etree.SubElement(r1, f'{{{w}}}footnoteRef')

                # 脚注文本
                r2 = etree.SubElement(p, f'{{{w}}}r')
                rPr2 = etree.SubElement(r2, f'{{{w}}}rPr')
                rFonts = etree.SubElement(rPr2, f'{{{w}}}rFonts')
                rFonts.set(f'{{{w}}}eastAsia', '宋体')
                sz = etree.SubElement(rPr2, f'{{{w}}}sz')
                sz.set(f'{{{w}}}val', '18')
                t = etree.SubElement(r2, f'{{{w}}}t')
                t.set(f'{{{XML_NS}}}space', 'preserve')
                t.text = ' ' + content

        return etree.tostring(footnotes, xml_declaration=True, encoding='UTF-8', standalone=True)

    def inject_into_docx(self, doc, output_path: str):
        """在保存的 docx 中注入原生脚注部分"""
        footnotes_xml = self.build_footnotes_xml()

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)

        with zipfile.ZipFile(buf, 'r') as zin:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename in ('word/footnotes.xml', 'word/_rels/footnotes.xml.rels'):
                        continue
                    data = zin.read(item.filename)
                    if item.filename == 'word/_rels/document.xml.rels':
                        data = self._patch_document_rels(data)
                    elif item.filename == '[Content_Types].xml':
                        data = self._patch_content_types(data)
                    zout.writestr(item, data)
                zout.writestr('word/footnotes.xml', footnotes_xml)

    @staticmethod
    def _patch_document_rels(data: bytes) -> bytes:
        """在 document.xml.rels 中添加脚注关系"""
        root = etree.fromstring(data)
        rels_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
        footnotes_type = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes'

        for rel in root.findall(f'{{{rels_ns}}}Relationship'):
            if rel.get('Type') == footnotes_type:
                return data

        max_id = 0
        for rel in root.findall(f'{{{rels_ns}}}Relationship'):
            rid = rel.get('Id', '')
            if rid.startswith('rId'):
                try:
                    max_id = max(max_id, int(rid[3:]))
                except ValueError:
                    pass

        new_rel = etree.SubElement(root, f'{{{rels_ns}}}Relationship')
        new_rel.set('Id', f'rId{max_id + 1}')
        new_rel.set('Type', footnotes_type)
        new_rel.set('Target', 'footnotes.xml')

        return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    @staticmethod
    def _patch_content_types(data: bytes) -> bytes:
        """在 [Content_Types].xml 中添加脚注内容类型"""
        root = etree.fromstring(data)
        ct_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'

        for override in root.findall(f'{{{ct_ns}}}Override'):
            if override.get('PartName') == '/word/footnotes.xml':
                return data

        override = etree.SubElement(root, f'{{{ct_ns}}}Override')
        override.set('PartName', '/word/footnotes.xml')
        override.set('ContentType',
                     'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml')

        return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
