"""
TEI-XML Integration utilities for Vogon.

1. Detects content type (TEI, XML, plain text)
2. Parses TEI-XML
3. Converts TEI to a more "clean" HTML representation:
   - Minimizes raw TEI markup
   - Preserves structural layout (paragraphs, line/page breaks, headings, etc.)
   - Provides a simpler display of editorial tags (e.g., <choice>, <orig>, <reg>)
4. Maintains xpath references for annotation
"""

from lxml import etree
from django.utils.safestring import mark_safe
import re


def _local_name(tag):
    """Helper to remove {namespace} from a tag or attribute name."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag

def _extract_full_text(elem):
    """Return concatenated text content from elem and its children."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if hasattr(child, 'text') and child.text:
            parts.append(child.text)
        if hasattr(child, 'tail') and child.tail:
            parts.append(child.tail)
    return ''.join(parts).strip()

def _escape_html(txt):
    """Minimal HTML escape for safety."""
    if not txt:
        return ''
    return (txt.replace('&', '&amp;')
               .replace('<', '&lt;')
               .replace('>', '&gt;'))

# ===== TEI to Display Conversion =====
class TEIProcessor:
    """Handler for converting TEI elements to HTML with mapping information and namespace awareness."""
    
    def __init__(self, namespaces=None):
        self.html_parts = []
        self.element_map = []
        self.namespaces = namespaces if namespaces is not None else {}
        self.tei_prefix = next((p for p, u in self.namespaces.items() if u == "http://www.tei-c.org/ns/1.0"), "tei")
        if "http://www.tei-c.org/ns/1.0" in self.namespaces.values() and self.namespaces.get(self.tei_prefix) != "http://www.tei-c.org/ns/1.0":
            tei_uri_actual_prefix = next((p for p, u in self.namespaces.items() if u == "http://www.tei-c.org/ns/1.0"), None)
            if tei_uri_actual_prefix :
                 self.namespaces[self.tei_prefix] = "http://www.tei-c.org/ns/1.0"
            elif self.namespaces.get(None) == "http://www.tei-c.org/ns/1.0":
                 self.namespaces[self.tei_prefix] = "http://www.tei-c.org/ns/1.0"

    def _add_position_predicates_ns(self, element, parent_xpath_str):
        """Add position predicates to make an XPath unique, using prefixes (e.g., /tei:p[1])."""
        ns_uri = element.namespace
        node_prefix_in_xml = None
        if ns_uri:
            for p, u in element.nsmap.items(): 
                if u == ns_uri:
                    node_prefix_in_xml = p 
                    break
        
        xpath_prefix_to_use = None
        if ns_uri == "http://www.tei-c.org/ns/1.0":
            xpath_prefix_to_use = self.tei_prefix
        elif ns_uri and node_prefix_in_xml:
             xpath_prefix_to_use = node_prefix_in_xml
        elif ns_uri :
            xpath_prefix_to_use = next((p for p, u in self.namespaces.items() if u == ns_uri and p is not None), None)

        local_tag_name = _local_name(element.tag)
        prefixed_tag = f"{xpath_prefix_to_use}:{local_tag_name}" if xpath_prefix_to_use else local_tag_name

        parent = element.getparent()
        if parent is None:
            xpath_str = f"/{prefixed_tag}[1]" 
        else:
            index = 1
            for sibling in parent.iterchildren(element.tag): 
                if sibling is element: break
                index += 1
            xpath_str = f"{parent_xpath_str}/{prefixed_tag}[{index}]"
        return xpath_str

    def process_element(self, element, parent_xpath_str=''):
        tag = _local_name(element.tag)
        current_element_xpath = self._add_position_predicates_ns(element, parent_xpath_str)
        handler_name = f"_process_{tag}"
        handler = getattr(self, handler_name, self._process_default_ns)
        return handler(element, tag, current_element_xpath)

    def _process_default_ns(self, element, tag, current_element_xpath):
        """Default handler for TEI elements: wraps in a span with TEI class and processes children."""
        self.html_parts.append(f'<span class="tei-{tag}" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
            if child_element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append(f'</span>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}

    def _process_tei_passthrough(self, element, tag, current_element_xpath):
        """Generic handler for inline TEI elements that should pass through their content within a styled span."""
        self.html_parts.append(f'<span class="tei-{tag}" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
            if child_element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append(f'</span>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}

   
    def _process_body(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<div class="tei-body" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element: self.process_element(child_element, current_element_xpath)
        if element.tail: self.html_parts.append(_escape_html(element.tail))
        self.html_parts.append(f'</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_text(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<div class="tei-text" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element: self.process_element(child_element, current_element_xpath)
        if element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append(f'</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}

    def _process_div_common(self, element, tag, current_element_xpath):
        div_class = f"tei-{tag} tei-div-common"
        self.html_parts.append(f'<div class="{div_class}" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element: self.process_element(child_element, current_element_xpath)
        if element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append(f'</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}


    
    def _process_p(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<p class="tei-p" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': 'paragraph', 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element: self.process_element(child_element, current_element_xpath)
        if element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append('</p>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    _process_paragraph = _process_p
    
    def _process_head(self, element, tag, current_element_xpath):
        heading_level = "h3" # Default heading level
        self.html_parts.append(f'<{heading_level} class="tei-head" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': 'heading', 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element: self.process_element(child_element, current_element_xpath)
        if element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append(f'</{heading_level}>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}

    def _process_pb(self, element, tag, current_element_xpath):
        n, facs = element.get('n', ''), element.get('facs', '')
        self.html_parts.append(
            f'<div class="tei-pb" data-xpath="{current_element_xpath}" '
            f'data-n="{n}" data-facs="{facs}">'
            f'<hr class="tei-pb-line"/><span class="tei-pb-label">Page {n}</span></div>'
            '<span class="pb-spacer"></span>'
        )
        self.element_map.append({'xpath': current_element_xpath, 'element_type': 'pagebreak', 'page': n, 'facs': facs, 'start_pos': len("".join(self.html_parts))})
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_lb(self, element, tag, current_element_xpath):
        n = element.get('n', '')
        br_html = f'<br class="tei-lb" data-xpath="{current_element_xpath}" data-n="{n}" />'
        if n and element.get('break') != 'no':
            br_html = f'<span class="tei-line-num" data-line-n="{n}">{n}</span>{br_html}'
        
        if element.get('break') == 'no':
            self.html_parts.append(f'<span class="tei-lb-nobreak" data-xpath="{current_element_xpath}" data-n="{n}"></span>')
        else:
            self.html_parts.append(br_html)
        self.element_map.append({'xpath': current_element_xpath, 'element_type': 'linebreak', 'line_number': n, 'is_break': element.get('break') != 'no', 'start_pos': len("".join(self.html_parts))})
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_gap(self, element, tag, current_element_xpath):
        desc_child = element.find(f'{self.tei_prefix}:desc', self.namespaces)
        desc_text = _extract_full_text(desc_child) if desc_child is not None else ""
        reason, extent, unit = element.get("reason", ""), element.get("extent", ""), element.get("unit", "")
        title_parts = [f"Description: {desc_text}" if desc_text else "", f"Reason: {reason}" if reason else "", f"Extent: {extent} {unit}".strip() if extent else ""]
        title_attr = "; ".join(filter(None, title_parts)) or "Gap"
        display_text = f"[{desc_text}]" if desc_text else "[...]"

        self.html_parts.append(f'<span class="tei-gap" data-xpath="{current_element_xpath}" data-reason="{reason}" data-extent="{extent}" data-unit="{unit}" title="{_escape_html(title_attr)}">{_escape_html(display_text)}</span>')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': 'gap', 'reason': reason, 'extent': extent, 'unit': unit, 'description': desc_text, 'start_pos': len("".join(self.html_parts))})
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_choice(self, element, tag, current_element_xpath):
        orig = element.find(f'{self.tei_prefix}:orig', self.namespaces)
        reg = element.find(f'{self.tei_prefix}:reg', self.namespaces)
        sic = element.find(f'{self.tei_prefix}:sic', self.namespaces)
        corr = element.find(f'{self.tei_prefix}:corr', self.namespaces)
        abbr = element.find(f'{self.tei_prefix}:abbr', self.namespaces)
        expan = element.find(f'{self.tei_prefix}:expan', self.namespaces)

        processed = False
        if reg is not None and (orig is not None or sic is not None):
            main_el, alt_el, alt_label = reg, orig if orig is not None else sic, "Original" if orig is not None else "Sic"
            self.html_parts.append(f'<span class="tei-choice tei-choice-regcorr" data-xpath="{current_element_xpath}" title="{alt_label}: {_escape_html(_extract_full_text(alt_el))}">{_extract_full_text(main_el)}</span>')
            processed = True
        elif sic is not None and corr is not None:
            self.html_parts.append(f'<span class="tei-choice tei-choice-siccorr" data-xpath="{current_element_xpath}" title="Correction: {_escape_html(_extract_full_text(corr))}">{_extract_full_text(sic)}</span>')
            processed = True
        elif expan is not None and abbr is not None:
            self.html_parts.append(f'<span class="tei-choice tei-choice-abbrexpan" data-xpath="{current_element_xpath}" title="Abbreviation: {_escape_html(_extract_full_text(abbr))}">{_extract_full_text(expan)}</span>')
            processed = True

        if not processed: # Generic fallback
            self.html_parts.append(f'<span class="tei-choice tei-choice-generic" data-xpath="{current_element_xpath}">')
            if element.text: self.html_parts.append(_escape_html(element.text))
            for child_element in element: self.process_element(child_element, current_element_xpath)
            if element.tail: self.html_parts.append(_escape_html(element.tail))
            self.html_parts.append('</span>')
            
        self.element_map.append({'xpath': current_element_xpath, 'element_type': 'choice', 'start_pos': len("".join(self.html_parts))})
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_list(self, element, tag, current_element_xpath):
        list_tag = "ol" if element.get("type") in ["ordered", "numbered"] else "ul"
        self.html_parts.append(f'<{list_tag} class="tei-list" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        for child_element in element: self.process_element(child_element, current_element_xpath)
        self.html_parts.append(f'</{list_tag}>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_item(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<li class="tei-item" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element: self.process_element(child_element, current_element_xpath)
        if element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append('</li>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
        
    def _process_label(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<span class="tei-label" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element: self.process_element(child_element, current_element_xpath)
        if element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append('</span>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_table(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<table class="tei-table" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        for child_element in element: self.process_element(child_element, current_element_xpath)
        self.html_parts.append('</table>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_row(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<tr class="tei-row" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        for child_element in element: self.process_element(child_element, current_element_xpath)
        self.html_parts.append('</tr>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
        
    _process_rowGrp = _process_row 

    def _process_cell(self, element, tag, current_element_xpath):
        cell_tag = "th" if element.get('role') == 'label' or _local_name(element.getparent().tag if element.getparent() is not None else '') == 'head' else "td"
        self.html_parts.append(f'<{cell_tag} class="tei-cell" data-xpath="{current_element_xpath}">')
        self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'start_pos': len("".join(self.html_parts))})
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element: self.process_element(child_element, current_element_xpath)
        if element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append(f'</{cell_tag}>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
        
    _process_entry = _process_cell 
    
    def _process_note(self, element, tag, current_element_xpath):
        note_place = element.get('place', 'inline') # Default to inline if no @place
        note_type = element.get('type', note_place) # Use @type or fallback to @place

        if note_place == 'foot':
            footnote_count = sum(1 for m in self.element_map if m.get('type') == 'footnote')
            fn_id = f"fn-{footnote_count + 1}"
            self.html_parts.append(f'<sup id="ref-{fn_id}" class="tei-fn-ref" data-xpath="{current_element_xpath}">{footnote_count + 1}</sup>')
            self.element_map.append({'type': 'footnote', 'text': _extract_full_text(element), 'id': fn_id, 'num': footnote_count + 1, 'xpath': current_element_xpath})
        else: # Inline, margin, or other types of notes
            self.html_parts.append(f'<span class="tei-note tei-note-{note_type}" data-xpath="{current_element_xpath}" title="Note ({note_type})">')
            self.element_map.append({'xpath': current_element_xpath, 'element_type': tag, 'note_type': note_type, 'start_pos': len("".join(self.html_parts))})
            if element.text: self.html_parts.append(_escape_html(element.text))
            for child_element in element: self.process_element(child_element, current_element_xpath)
            if element.tail: self.html_parts.append(_escape_html(child_element.tail))
            self.html_parts.append('</span>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}

# ===== Content Type Detection =====
def detect_content_type(text_content):
    """Detect the content type of a text by examining its structure."""
    is_xml, is_tei = False, False
    if text_content.strip().startswith('<?xml'):
        is_xml = True
        if any(marker in text_content for marker in ['<TEI', '<tei', 'xmlns="http://www.tei-c.org/ns/1.0"']):
            is_tei = True
    content_type = 'text/xml+tei' if is_tei else ('text/xml' if is_xml else 'text/plain')
    return {'is_xml': is_xml, 'is_tei': is_tei, 'content_type': content_type}

# ===== TEI Parsing Functions =====
def parse_tei_document(xml_content):
    """Parse a TEI-XML document and prepare it for annotation."""
    try:
        parser = etree.XMLParser(remove_comments=True, remove_pis=True, recover=True)
        root = etree.fromstring(xml_content.encode('utf-8'), parser)
        
        namespaces = {}
        tei_standard_uri = "http://www.tei-c.org/ns/1.0"
        # Populate namespaces map from the root element, ensure 'tei' is preferred for TEI URI
        if root.nsmap:
            for prefix, uri in root.nsmap.items():
                actual_prefix = prefix if prefix else 'tei' # Use 'tei' for default namespace
                namespaces[actual_prefix] = uri
                if uri == tei_standard_uri and actual_prefix != 'tei': # If TEI URI found under different prefix
                    namespaces['tei'] = tei_standard_uri # Also ensure 'tei' is mapped

        # If 'tei' not mapped but TEI is default, or if content type is TEI and no ns map from root
        if namespaces.get('tei') != tei_standard_uri:
            if namespaces.get(None) == tei_standard_uri: namespaces['tei'] = tei_standard_uri
            elif not namespaces and detect_content_type(xml_content)['is_tei'] : namespaces['tei'] = tei_standard_uri
        
        # For backward compatibility: generate namespace-stripped XML string.
        clean_root_for_legacy_output = strip_namespaces(root)
        clean_xml = etree.tostring(clean_root_for_legacy_output, encoding='unicode')

        metadata = extract_tei_metadata(root, namespaces)
        facsimile_data = extract_facsimile_data(root, namespaces)
        display_result = create_display_content_ns(root, namespaces) # Use namespace-aware function

        return {
            'original_xml': xml_content, 'clean_xml': clean_xml, 
            'display_html': display_result['display_html'], 'element_map': display_result['element_map'],
            'tei_metadata': metadata, 'css': display_result.get('css', ''),
            'facsimile_data': facsimile_data, 'namespaces': namespaces 
        }
    except Exception as e:
        raise ValueError(f"Failed to parse TEI-XML: {str(e)}. Input snippet: {xml_content[:500]}...")

def strip_namespaces(node):
    """Deep-copy *node* with all namespaces removed (for 'clean_xml' output)."""
    if not isinstance(node, etree._Element): return None
    new_node = etree.Element(_local_name(node.tag))
    for k, v in node.attrib.items(): new_node.set(_local_name(k), v)
    for child in node:
        cleaned_child = strip_namespaces(child)
        if cleaned_child is not None: new_node.append(cleaned_child)
    new_node.text = node.text
    new_node.tail = node.tail
    return new_node

def extract_tei_metadata(root, namespaces=None):
    """Extract basic metadata from the TEI header, namespace-aware."""
    if namespaces is None: namespaces = {}
    metadata = {'title': None, 'author': None, 'publisher': None, 'date': None,
                'source': None, 'language': None, 'msDesc': []}
    
    tei_prefix = next((p for p, u in namespaces.items() if u == "http://www.tei-c.org/ns/1.0" and p is not None), 'tei')
    query_ns = namespaces.copy()
    if namespaces.get(None) == "http://www.tei-c.org/ns/1.0" and tei_prefix not in namespaces : # Ensure 'tei' can be used if default
        query_ns[tei_prefix] = "http://www.tei-c.org/ns/1.0"


    def get_el_text_or_attr(element, path_list, attr=None):
        for path in path_list if isinstance(path_list, list) else [path_list]:
            try:
                # Ensure path is relative to the current element if it doesn't start with / or .//
                current_path = path if path.startswith(('.','/')) else f'.//{tei_prefix}:{path}'
                # If path has no prefix and we have one, add it.
                if ':' not in current_path.split('/')[-1] and not current_path.split('/')[-1].startswith('@') and tei_prefix :
                    parts = current_path.split('/')
                    last_part = parts[-1]
                    if not last_part.startswith(('@','*')): parts[-1] = f"{tei_prefix}:{last_part}"
                    current_path = "/".join(parts)

                res_list = element.xpath(current_path, namespaces=query_ns)
                if res_list:
                    res = res_list[0]
                    if attr: # If specific attribute requested
                        val = res.get(attr)
                        if val: return val.strip()
                    if res.text: return res.text.strip() # Prioritize text content
                    if attr is None and res.get('when'): return res.get('when') # Fallback for date/@when
            except Exception: continue
        return None

    tei_header = root.find(f'.//{tei_prefix}:teiHeader', query_ns)
    if tei_header is None: return metadata

    file_desc = tei_header.find(f'.//{tei_prefix}:fileDesc', query_ns)
    if file_desc:
        title_stmt = file_desc.find(f'.//{tei_prefix}:titleStmt', query_ns)
        if title_stmt:
            metadata['title'] = get_el_text_or_attr(title_stmt, 'title')
            metadata['author'] = get_el_text_or_attr(title_stmt, 'author')

        publication_stmt = file_desc.find(f'.//{tei_prefix}:publicationStmt', query_ns)
        if publication_stmt:
            metadata['publisher'] = get_el_text_or_attr(publication_stmt, 'publisher')
            metadata['date'] = get_el_text_or_attr(publication_stmt, 'date')

        source_desc = file_desc.find(f'.//{tei_prefix}:sourceDesc', query_ns)
        if source_desc:
            if not metadata.get('date'): metadata['date'] = get_el_text_or_attr(source_desc, './/date') # .// for deeper search
            source_str = source_desc.xpath('string(.)', namespaces=query_ns)
            if source_str: metadata['source'] = " ".join(str(source_str).strip().split())
            
            for ms_desc_el in source_desc.xpath(f'.//{tei_prefix}:msDesc', namespaces=query_ns):
                ms_info = {'xml_id': ms_desc_el.get('{http://www.w3.org/XML/1998/namespace}id')}
                ms_info['settlement'] = get_el_text_or_attr(ms_desc_el, f'.//{tei_prefix}:msIdentifier/{tei_prefix}:settlement')
                metadata['msDesc'].append({k:v for k,v in ms_info.items() if v})


    profile_desc = tei_header.find(f'.//{tei_prefix}:profileDesc', query_ns)
    if profile_desc:
        lang_usage = profile_desc.find(f'.//{tei_prefix}:langUsage', query_ns)
        if lang_usage:
             metadata['language'] = get_el_text_or_attr(lang_usage, f'{tei_prefix}:language', attr='ident') or get_el_text_or_attr(lang_usage, f'{tei_prefix}:language')
    return metadata

def extract_facsimile_data(root, namespaces=None):
    """Extract info about facsimile images (<facsimile>/<surface>/<graphic>), namespace-aware."""
    if namespaces is None: namespaces = {}
    facsimile_data = []
    tei_prefix = next((p for p, u in namespaces.items() if u == "http://www.tei-c.org/ns/1.0"), "tei")
    
    for facs_elem in root.xpath(f'.//{tei_prefix}:facsimile', namespaces=namespaces):
        for surface_elem in facs_elem.xpath(f'./{tei_prefix}:surface | .//{tei_prefix}:surface', namespaces=namespaces):
            surface_attrs = {_local_name(attr): value for attr, value in surface_elem.attrib.items()}
            graphic_elem = surface_elem.find(f'./{tei_prefix}:graphic', namespaces=namespaces) 
            if graphic_elem is not None:
                graphic_attrs = {_local_name(attr): value for attr, value in graphic_elem.attrib.items()}
                combined_attrs = {**surface_attrs, **graphic_attrs} # Graphic attrs override surface
                if combined_attrs.get('url'): facsimile_data.append(combined_attrs)
            elif surface_attrs.get('url'):
                facsimile_data.append(surface_attrs)
        for graphic_direct in facs_elem.xpath(f'./{tei_prefix}:graphic[not(parent::{tei_prefix}:surface)]', namespaces=namespaces):
            graphic_attrs = {_local_name(attr): value for attr, value in graphic_direct.attrib.items()}
            if graphic_attrs.get('url'): facsimile_data.append(graphic_attrs)
    return facsimile_data

def create_display_content_ns(root_with_ns, namespaces_map):
    """Convert the TEI tree into HTML, using namespace-aware processing."""
    tei_prefix = next((p for p, u in namespaces_map.items() if u == "http://www.tei-c.org/ns/1.0"), "tei")
    body_element = root_with_ns.find(f'.//{tei_prefix}:body', namespaces_map) or \
                   root_with_ns.find(f'.//{tei_prefix}:text', namespaces_map) or \
                   root_with_ns # Fallback to root
    processor = TEIProcessor(namespaces=namespaces_map)
    result = processor.process_element(body_element) 
    html_content = ''.join(result['html_parts'])
    fnotes = [m for m in result["element_map"] if m.get("type") == "footnote"]
    if fnotes:
        html_content += '<hr class="tei-fn-rule"/><ol class="tei-footnotes">'
        for fn in sorted(fnotes, key=lambda x: x.get('num', 0)):
            html_content += (f'<li id="{fn["id"]}" class="tei-footnote" value="{fn.get("num", "")}">'
                             f'<a href="#ref-{fn["id"]}">{fn.get("num", "*")}</a>. {_escape_html(fn["text"])}</li>')
        html_content += '</ol>'
    return {'display_html': mark_safe(html_content), 'element_map': result['element_map']}

# ===== Tokenization for TEI =====
def tokenize_tei_content(display_html):
    """Wrap every whitespace-separated token in <word id="…">…</word> in the HTML output."""
    if not isinstance(display_html, str): display_html = str(display_html)
    if not display_html.strip(): return display_html

    try:
        # Parse the HTML string. Using a wrapper div for fragments.
        temp_wrapper_tag = "body_content_wrapper" # Unique enough
        # lxml.html.fromstring is good for full docs, but for fragments, behavior can vary.
        # etree.HTML will create <html><body> if not present.
        parsed_doc_root = etree.HTML(f"<{temp_wrapper_tag}>{display_html}</{temp_wrapper_tag}>")
        content_container = parsed_doc_root.find(f'.//{temp_wrapper_tag}') 
        if content_container is None : content_container = parsed_doc_root # Fallback
    except Exception as e:
        print(f"Error parsing HTML for tokenization: {str(e)}. Content: {display_html[:200]}")
        return display_html 
    
    next_id_counter = 0
    # Find elements containing text nodes to be tokenized.
    for text_parent_node in content_container.xpath('.//*[text()[normalize-space()] and not(self::script or self::style or self::word or ancestor::word)]'):
        text_to_tokenize = text_parent_node.text
        if not text_to_tokenize or not text_to_tokenize.strip(): continue

        new_content_parts = [] # Stores strings (whitespace) and <word> elements
        current_char_pos = 0
        for match in re.finditer(r'\S+', text_to_tokenize):
            if match.start() > current_char_pos: new_content_parts.append(text_to_tokenize[current_char_pos:match.start()])
            word_element = etree.Element('word')
            word_element.set('id', f'tei_{next_id_counter}'); next_id_counter += 1
            word_element.text = match.group(0)
            new_content_parts.append(word_element)
            current_char_pos = match.end()
        if current_char_pos < len(text_to_tokenize): new_content_parts.append(text_to_tokenize[current_char_pos:])
        
        # Replace the original text content of text_parent_node with new parts
        text_parent_node.text = None 
        last_inserted_el = None
        for i, item in enumerate(new_content_parts):
            if isinstance(item, str): # Text part
                if last_inserted_el is not None: last_inserted_el.tail = (last_inserted_el.tail or "") + item
                elif i == 0: text_parent_node.text = (text_parent_node.text or "") + item
                else: # Text follows text (should ideally not happen often if logic is fine)
                    if len(text_parent_node) > 0: text_parent_node[-1].tail = (text_parent_node[-1].tail or "") + item
                    else: text_parent_node.text = (text_parent_node.text or "") + item
            else: # <word> element
                text_parent_node.append(item)
                last_inserted_el = item
    
    # Serialize the content of our temporary wrapper back to a string
    final_html = ""
    if content_container is not None:
        if content_container.text: final_html += _escape_html(content_container.text)
        for child in content_container:
            final_html += etree.tostring(child, encoding='unicode', method='html')
    return final_html