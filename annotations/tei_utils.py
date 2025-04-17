"""
TEI-XML Integration utilities for Vogon.

1. Detects content type (TEI, XML, plain text)
2. Parses TEI-XML
3. Converts TEI to a more "clean" HTML representation:
   - Minimizes raw TEI markup
   - Preserves structural layout (paragraphs, line/page breaks, headings, etc.)
   - Provides a simpler display of editorial tags (e.g., <choice>, <orig>, <reg>)
4. Maintains xpath references for annotation
5. Optionally tokenizes the resulting HTML for word-level annotation
"""

from lxml import etree
from django.utils.safestring import mark_safe

# ===== Content Type Detection =====

def detect_content_type(text_content):
    """
    Detect the content type of a text by examining its structure.

    Returns a dictionary with:
        - is_xml (bool)
        - is_tei (bool)
        - content_type (str) = 'text/xml+tei', 'text/xml', or 'text/plain'
    """
    is_xml = False
    is_tei = False

    if text_content.strip().startswith('<?xml') or text_content.strip().startswith('<'):
        is_xml = True
        # Check for TEI namespace or common TEI markers
        if any(marker in text_content for marker in [
            '<TEI', '<tei', '<teiHeader', '<teiheader',
            # catch all namespace variations:
            'xmlns="http://www.tei-c.org"', 
            'xmlns="http://www.tei-c.org/ns/1.0"',
            'xmlns:tei', 
            'http://www.tei-c.org/ns/1.0'
        ]):
            is_tei = True

    if is_tei:
        content_type = 'text/xml+tei'
    elif is_xml:
        content_type = 'text/xml'
    else:
        content_type = 'text/plain'

    return {
        'is_xml': is_xml,
        'is_tei': is_tei,
        'content_type': content_type
    }

# ===== TEI Parsing Functions =====

def parse_tei_document(xml_content):
    """
    Parse a TEI-XML document and prepare it for annotation.

    Returns a dictionary with:
        - original_xml
        - clean_xml: namespace-stripped XML
        - display_html: improved HTML representation
        - element_map: mapping between display positions and TEI elements
        - tei_metadata: extracted metadata from TEI header
        - css: placeholder for CSS (if any)
        - facsimile_data: info about facsimile images
    """
    try:
        root = etree.fromstring(xml_content.encode('utf-8'))

        # Remove namespaces for easier processing
        clean_root = strip_namespaces(root)
        clean_xml = etree.tostring(clean_root, encoding='unicode')

        # Extract metadata
        metadata = extract_tei_metadata(clean_root)

        # Extract facsimile data
        facsimile_data = extract_facsimile_data(clean_root)

        # Create display version
        display_result = create_display_content(clean_root)

        return {
            'original_xml': xml_content,
            'clean_xml': clean_xml,
            'display_html': display_result['display_html'],
            'element_map': display_result['element_map'],
            'tei_metadata': metadata,
            'css': display_result.get('css', ''),
            'facsimile_data': facsimile_data
        }
    except Exception as e:
        raise ValueError(f"Failed to parse TEI-XML: {str(e)}")

def strip_namespaces(root):
    """
    Recursively remove namespaces from XML element tags.
    """
    new_root = etree.Element(_local_name(root.tag))
    # Copy attributes without namespaces
    for name, value in root.attrib.items():
        new_root.set(_local_name(name), value)

    # Process children
    for child in root:
        if isinstance(child, etree._Element):
            child_clean = strip_namespaces(child)
            new_root.append(child_clean)

    # Also handle text and tail
    new_root.text = root.text
    new_root.tail = root.tail

    return new_root

def _local_name(tag):
    """Helper to remove {namespace} from a tag or attribute name."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag

def extract_tei_metadata(root):
    """
    Extract basic metadata (title, author, date, etc.) from the TEI header.
    Adapt as needed for your TEI schemas.
    """
    metadata = {
        'title': None,
        'author': None,
        'publisher': None,
        'date': None,
        'source': None,
        'language': None,
        'msDesc': []
    }

    # Title
    title_elem = root.find('.//titleStmt/title')
    if title_elem is not None and title_elem.text:
        metadata['title'] = title_elem.text.strip()

    # Author
    author_elem = root.find('.//titleStmt/author')
    if author_elem is not None and author_elem.text:
        metadata['author'] = author_elem.text.strip()

    # Publisher
    publisher_elem = root.find('.//publicationStmt/publisher')
    if publisher_elem is not None and publisher_elem.text:
        metadata['publisher'] = publisher_elem.text.strip()

    # Date
    date_elem = root.find('.//publicationStmt/date') or root.find('.//sourceDesc//date')
    if date_elem is not None:
        if date_elem.text:
            metadata['date'] = date_elem.text.strip()
        elif 'when' in date_elem.attrib:
            metadata['date'] = date_elem.attrib['when']

    # Source
    source_elem = root.find('.//sourceDesc')
    if source_elem is not None:
        source_text = source_elem.xpath('string()').strip()
        if source_text:
            metadata['source'] = source_text

    # Language
    language_elem = root.find('.//language')
    if language_elem is not None:
        if language_elem.text:
            metadata['language'] = language_elem.text.strip()
        elif 'ident' in language_elem.attrib:
            metadata['language'] = language_elem.attrib['ident']

    # Example: gather <msDesc> info
    for ms_desc in root.findall('.//msDesc'):
        ms_info = {}
        if 'xml:id' in ms_desc.attrib:
            ms_info['xml_id'] = ms_desc.attrib['xml:id']
        # You could parse <msIdentifier>, <handDesc>, etc.
        metadata['msDesc'].append(ms_info)

    return metadata

def extract_facsimile_data(root):
    """
    Extract info about facsimile images (<facsimile>/<graphic>).
    """
    facsimile_data = []
    facsimile = root.find('.//facsimile')
    if facsimile is not None:
        for graphic in facsimile.findall('.//graphic'):
            image_info = {}
            for attr, value in graphic.attrib.items():
                image_info[_local_name(attr)] = value
            facsimile_data.append(image_info)
    return facsimile_data

# ===== TEI to Display Conversion =====
def create_display_content(root):
    """
    Convert the TEI tree into a "clean" HTML string + element map.
    """
    # Find main content
    body = root.find('.//body') or root.find('.//text')
    if body is None:
        # fallback
        body = root

    html_parts = []
    element_map = []

    # Recursively process
    result = process_element(body, html_parts, element_map, path='')
    return {
        'display_html': mark_safe(''.join(result['html_parts'])),
        'element_map': result['element_map'],
    }


def process_element(element, html_parts, element_map, path=''):
    tg   = element.tag
    xpth = add_position_predicates(element, path)


    if tg in ('body', 'text'):
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Paragraphs ------------------------------------------------
    if tg in ('p', 'paragraph'):
        html_parts.append(f'<p class="tei-p" data-xpath="{xpth}">')
        element_map.append({'xpath': xpth, 'element_type': 'paragraph',
                            'start_pos': len("".join(html_parts))})
        if element.text: html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: html_parts.append(_escape_html(ch.tail))
        html_parts.append('</p>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Headings --------------------------------------------------
    if tg == 'head':
        html_parts.append(f'<h3 class="tei-head" data-xpath="{xpth}">')
        element_map.append({'xpath': xpth, 'element_type': 'heading',
                            'start_pos': len("".join(html_parts))})
        if element.text: html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: html_parts.append(_escape_html(ch.tail))
        html_parts.append('</h3>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Page / Line breaks ---------------------------------------
    if tg == 'pb':
        n, facs = element.get('n', ''), element.get('facs', '')
        html_parts.append(
            f'<div class="tei-pb" data-xpath="{xpth}" '
            f'data-n="{n}" data-facs="{facs}"><hr/><span class="tei-pb-label">'
            f'Page {n}</span></div>'
        )
        element_map.append({'xpath': xpth, 'element_type': 'pagebreak',
                            'page': n, 'facs': facs,
                            'start_pos': len("".join(html_parts))})
        return {'html_parts': html_parts, 'element_map': element_map}

    if tg == 'lb':
        n = element.get('n', '')
        br = f'<br class="tei-lb" data-xpath="{xpth}" data-n="{n}" />'
        if n: br = f'<span class="tei-line-num">{n}</span>{br}'
        html_parts.append(br)
        element_map.append({'xpath': xpth, 'element_type': 'linebreak',
                            'start_pos': len("".join(html_parts))})
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Gaps ------------------------------------------------------
    if tg == 'gap':
        gap_html = (f'<span class="tei-gap" data-xpath="{xpth}" '
                    f'data-reason="{element.get("reason", "")}" '
                    f'data-extent="{element.get("extent", "")}" '
                    f'data-unit="{element.get("unit", "")}" '
                    f'title="Gap: {element.get("extent", "")} '
                    f'{element.get("unit", "")} - {element.get("reason", "")}">'
                    '[...]</span>')
        html_parts.append(gap_html)
        element_map.append({'xpath': xpth, 'element_type': 'gap',
                            'start_pos': len("".join(html_parts))})
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Choice / Abbreviation / Regularisation -------------------
    if tg == 'choice':
        orig, reg  = element.find('orig'),  element.find('reg')
        abbr, expn = element.find('abbr'), element.find('expan')
        if orig is not None and reg is not None:
            html_parts.append(
                f'<span class="tei-choice" data-xpath="{xpth}" '
                f'title="Original: {_extract_full_text(orig)}">'
                f'{_extract_full_text(reg)}</span>')
        elif abbr is not None and expn is not None:
            html_parts.append(
                f'<span class="tei-choice" data-xpath="{xpth}" '
                f'title="Abbreviation: {_extract_full_text(abbr)}">'
                f'{_extract_full_text(expn)}</span>')
        else:
            for ch in element:
                process_element(ch, html_parts, element_map, xpth)
        element_map.append({'xpath': xpth, 'element_type': 'choice',
                            'start_pos': len("".join(html_parts))})
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Editorial markup (add / del / supplied / subst) ----------
    def _editorial_span(cls, inner_open='[', inner_close=']'):
        html_parts.append(f'<span class="tei-{cls}" data-xpath="{xpth}">')
        element_map.append({'xpath': xpth, 'element_type': cls,
                            'start_pos': len("".join(html_parts))})
        if cls == 'add' or cls == 'supplied':
            html_parts.append(inner_open)

    if tg == 'add':
        _editorial_span('add')
        if element.text: html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: html_parts.append(_escape_html(ch.tail))
        html_parts.append(']</span>')
        return {'html_parts': html_parts, 'element_map': element_map}

    if tg == 'del':
        html_parts.append(f'<span class="tei-del" data-xpath="{xpth}" '
                          f'style="text-decoration:line-through;">')
        element_map.append({'xpath': xpth, 'element_type': 'deletion',
                            'start_pos': len("".join(html_parts))})
        if element.text: html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: html_parts.append(_escape_html(ch.tail))
        html_parts.append('</span>')
        return {'html_parts': html_parts, 'element_map': element_map}

    if tg == 'supplied':
        _editorial_span('supplied')
        if element.text: html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: html_parts.append(_escape_html(ch.tail))
        html_parts.append(']</span>')
        return {'html_parts': html_parts, 'element_map': element_map}

    if tg == 'subst':
        html_parts.append(f'<span class="tei-subst" data-xpath="{xpth}">')
        element_map.append({'xpath': xpth, 'element_type': 'substitution',
                            'start_pos': len("".join(html_parts))})
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: html_parts.append(_escape_html(ch.tail))
        html_parts.append('</span>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Divisions -------------------------------------------------
    if tg == 'div':
        html_parts.append(
            f'<div class="tei-div" data-xpath="{xpth}" '
            f'data-type="{element.get("type", "")}" data-n="{element.get("n", "")}">'
        )
        element_map.append({'xpath': xpth, 'element_type': 'division',
                            'start_pos': len("".join(html_parts))})
        if element.text: html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: html_parts.append(_escape_html(ch.tail))
        html_parts.append('</div>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Highlight (<hi>, <emph>, etc.) ---------------------------
    if tg in ('hi', 'emph'):
        html_parts.append(
            f'<span class="tei-hi" data-xpath="{xpth}" data-rend="{element.get("rend", "")}">'
        )
        element_map.append({'xpath': xpth, 'element_type': 'highlight',
                            'start_pos': len("".join(html_parts))})
        if element.text: html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: html_parts.append(_escape_html(ch.tail))
        html_parts.append('</span>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- QUICK INLINE TAGS that used to disappear -----------------
    if tg in ('num', 'ex', 'sup'):
        html_parts.append(f'<span class="tei-{tg}" data-xpath="{xpth}">')
        element_map.append({'xpath': xpth, 'element_type': tg,
                            'start_pos': len("".join(html_parts))})
        if element.text: html_parts.append(_escape_html(element.text))
        html_parts.append('</span>')
        if element.tail: html_parts.append(_escape_html(element.tail))
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Generic fallback (now keeps element.tail) ----------------
    html_parts.append(f'<span class="tei-{tg}" data-xpath="{xpth}">')
    element_map.append({'xpath': xpth, 'element_type': tg,
                        'start_pos': len("".join(html_parts))})
    if element.text: html_parts.append(_escape_html(element.text))
    for ch in element:
        process_element(ch, html_parts, element_map, xpth)
        if ch.tail: html_parts.append(_escape_html(ch.tail))
    html_parts.append('</span>')
    if element.tail: html_parts.append(_escape_html(element.tail))

    return {'html_parts': html_parts, 'element_map': element_map}

def add_position_predicates(element, path):
    """
    Add position predicates to make an XPath unique, e.g. /TEI[1]/text[1]/p[2].
    """
    parent = element.getparent()
    if parent is None:
        # We are at root
        new_path = f"/{element.tag}"
    else:
        # figure out how many siblings of same tag are before this element
        index = 1
        for sibling in parent:
            if sibling.tag == element.tag:
                if sibling is element:
                    break
                index += 1
        # build up
        new_path = path + '/' + f"{element.tag}[{index}]"
    return new_path

def _extract_full_text(elem):
    """Return concatenated text content from elem and its children."""
    # includes .text and children's .text
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts).strip()

def _escape_html(txt):
    """Minimal HTML escape for safety."""
    if not txt:
        return ''
    return (txt.replace('&', '&amp;')
               .replace('<', '&lt;')
               .replace('>', '&gt;'))

# ===== Tokenization for TEI =====
def tokenize_tei_content(display_html):
    """
    Wrap every whitespace‑separated token in <word id="…">…</word>.
    *Real* sub‑elements are inserted so lxml does NOT escape them.
    """
    parser = etree.HTMLParser()
    root   = etree.fromstring(f'<root>{display_html}</root>', parser)

    # Escape any HTML tags found in text nodes to prevent XSS and invalid HTML
    # This handles both direct text content of elements (parent.text) and 
    # tail text after child elements (child.tail)
    for text_node in root.xpath('//text()'):
        if '<' in text_node and '>' in text_node:
            parent = text_node.getparent()
            if parent.tag not in ('script', 'style'):
                new_text = _escape_html(text_node)
                if parent is not None:
                    if text_node == parent.text:
                        parent.text = new_text
                    else:
                        # Must be tail text of some child
                        for child in parent:
                            if text_node == child.tail:
                                child.tail = new_text
                                break

    next_id = 0
    # all nodes that directly own text (skip <script>, <style>, <word>)
    for node in root.xpath('//*[text()]'):
        if node.tag in ('script', 'style', 'word'):
            continue
        if node.xpath('ancestor::word'):
            continue

        text = node.text or ''
        words = [w for w in text.split() if w]
        if not words:
            continue

        node.text = None
        for i, token in enumerate(words):
            w = etree.Element('word')
            w.set('id', f'tei_{next_id}')
            next_id += 1
            w.text = token
            node.insert(i, w)
            # preserve spaces between tokens
            if i < len(words) - 1:
                w.tail = ' '

    html = etree.tostring(root, encoding='unicode', method='html')
    # strip the artificial <root> wrapper
    return html.replace('<root>', '').replace('</root>', '')