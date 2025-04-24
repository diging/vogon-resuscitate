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
        # Use a parser that removes processing instructions (XML declarations, etc.)
        # This prevents issues with <?xml ...?> and <?xml-model ...?> tags 
        parser = etree.XMLParser(remove_comments=True, remove_pis=True)
        root = etree.fromstring(xml_content.encode('utf-8'), parser)

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
        # Simple error reporting
        raise ValueError(f"Failed to parse TEI-XML: {str(e)}")

def strip_namespaces(node):
    """
    Deep-copy *node* with all namespaces removed.
    • Ordinary element nodes are copied and cleaned.
    • Processing instructions, comments, and text nodes that are
      NOT children (.text / .tail) are skipped – they don't belong
      in the cleaned tree and would otherwise raise TypeError
      when appended.
    """
    # Skip non-element nodes (like processing instructions) to prevent errors
    if not isinstance(node, etree._Element):
        return None

    # ── create namespace-free copy of *this* element ────────────────────
    if node.tag.startswith('{'):
        _, tag = node.tag[1:].split('}', 1)
        new_node = etree.Element(tag)
    else:
        new_node = etree.Element(node.tag)

    # copy attributes without namespaces
    for k, v in node.attrib.items():
        if k.startswith('{'):
            _, attr = k[1:].split('}', 1)
            new_node.set(attr, v)
        else:
            new_node.set(k, v)

    # ── recurse on children ─────────────────────────────────────────────
    for child in node:
        cleaned_child = strip_namespaces(child)
        if cleaned_child is not None:          # skip PI / comments
            new_node.append(cleaned_child)

    # preserve text and tail
    new_node.text = node.text
    new_node.tail = node.tail
    return new_node

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

    # Generate XML representation for debugging
    try:
        xml_string = etree.tostring(body, encoding='unicode', pretty_print=True)
        # We'll include this in a comment for debugging if needed
        # html_parts.append(f'<!-- Original XML structure:\n{xml_string}\n-->')
    except:
        pass

    # Recursively process
    result = process_element(body, html_parts, element_map, path='')
    
    # Ensure we're returning valid HTML
    html_content = ''.join(result['html_parts'])
    
    # Pull footnotes out of element_map and append
    fnotes = [m for m in result["element_map"] if m.get("type") == "footnote"]
    if fnotes:
        html_content += '<hr class="tei-fn-rule"/><ol class="tei-footnotes">'
        for i, fn in enumerate(fnotes, 1):
            html_content += (
                f'<li id="{fn["id"]}" class="tei-footnote">'
                f'<a href="#ref-{fn["id"]}">{i}</a>. '
                f'{_escape_html(fn["text"])}'
                '</li>'
            )
        html_content += '</ol>'
    
    return {
        'display_html': mark_safe(html_content),
        'element_map': result['element_map'],
    }

def process_element(element, html_parts, element_map, path=''):
    """
    Process each element in the TEI-XML tree and convert to HTML representation.
    This function preserves the structure while creating annotatable content.
    
    Args:
        element: The current XML element
        html_parts: List of HTML string parts being constructed
        element_map: List of mappings from positions to XPaths
        path: Current XPath
        
    Returns:
        Dict with 'html_parts' and 'element_map'
    """
    tg = element.tag
    xpth = add_position_predicates(element, path)
    
    # Log the tag and path for debugging
    # print(f"Processing element: {tg} at path: {xpth}")

    # Handle body and text containers
    if tg in ('body', 'text'):
        # Create a containing element but process children
        html_parts.append(f'<div class="tei-{tg}" data-xpath="{xpth}">')
        element_map.append({'xpath': xpth, 'element_type': tg,
                            'start_pos': len("".join(html_parts))})
        if element.text:
            html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail:
                html_parts.append(_escape_html(ch.tail))
        html_parts.append(f'</div>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Paragraphs ------------------------------------------------
    if tg in ('p', 'paragraph'):
        html_parts.append(f'<p class="tei-p" data-xpath="{xpth}">')
        element_map.append({'xpath': xpth, 'element_type': 'paragraph',
                            'start_pos': len("".join(html_parts))})
        if element.text: 
            html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: 
                html_parts.append(_escape_html(ch.tail))
        html_parts.append('</p>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Headings --------------------------------------------------
    if tg == 'head':
        html_parts.append(f'<h3 class="tei-head" data-xpath="{xpth}">')
        element_map.append({'xpath': xpth, 'element_type': 'heading',
                            'start_pos': len("".join(html_parts))})
        if element.text: 
            html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail: 
                html_parts.append(_escape_html(ch.tail))
        html_parts.append('</h3>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # -------- Page / Line breaks ---------------------------------------
    if tg == 'pb':
        n, facs = element.get('n', ''), element.get('facs', '')
        html_parts.append(
            f'<div class="tei-pb" data-xpath="{xpth}" '
            f'data-n="{n}" data-facs="{facs}">'
            f'<hr/><span class="tei-pb-label">Page {n}</span></div>'
            '<span class="pb-spacer"></span>'   #  adds visual gap
        )
        element_map.append({'xpath': xpth, 'element_type': 'pagebreak',
                            'page': n, 'facs': facs,
                            'start_pos': len("".join(html_parts))})
        return {'html_parts': html_parts, 'element_map': element_map}

    if tg == 'lb':
        n = element.get('n', '')
        br = f'<br class="tei-lb" data-xpath="{xpth}" data-n="{n}" />'
        if n: 
            br = f'<span class="tei-line-num">{n}</span>{br}'
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
            # Process other elements in choice
            html_parts.append(f'<span class="tei-choice" data-xpath="{xpth}">')
            if element.text:
                html_parts.append(_escape_html(element.text))
            for ch in element:
                process_element(ch, html_parts, element_map, xpth)
                if ch.tail:
                    html_parts.append(_escape_html(ch.tail))
            html_parts.append('</span>')
        element_map.append({'xpath': xpth, 'element_type': 'choice',
                            'start_pos': len("".join(html_parts))})
        return {'html_parts': html_parts, 'element_map': element_map}
    
    # ───────────────────────────────────────────────────────────────
    # Lists and items
    if tg == 'list':
        html_parts.append(f'<ul class="tei-list" data-xpath="{xpth}">')
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
        html_parts.append('</ul>')
        return {'html_parts': html_parts, 'element_map': element_map}

    if tg in ('item', 'label'):
        html_parts.append(f'<li class="tei-item" data-xpath="{xpth}">')
        if element.text:
            html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail:
                html_parts.append(_escape_html(ch.tail))
        html_parts.append('</li>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # ───────────────────────────────────────────────────────────────
    # Tables
    if tg == 'table':
        html_parts.append(f'<table class="tei-table" data-xpath="{xpth}">')
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
        html_parts.append('</table>')
        return {'html_parts': html_parts, 'element_map': element_map}

    if tg in ('row', 'rowGrp'):
        html_parts.append('<tr>')
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
        html_parts.append('</tr>')
        return {'html_parts': html_parts, 'element_map': element_map}

    if tg in ('cell', 'entry'):
        html_parts.append('<td>')
        if element.text:
            html_parts.append(_escape_html(element.text))
        for ch in element:
            process_element(ch, html_parts, element_map, xpth)
            if ch.tail:
                html_parts.append(_escape_html(ch.tail))
        html_parts.append('</td>')
        return {'html_parts': html_parts, 'element_map': element_map}

    # ───────────────────────────────────────────────────────────────
    # Footnotes
    if tg == 'note' and element.get('place') == 'foot':
        # create a unique id for cross-reference
        fn_id = f"fn-{len(element_map)}"
        marker = f'<sup id="ref-{fn_id}" class="tei-fn-ref" data-xpath="{xpth}"></sup>'
        html_parts.append(marker)

        # collect footnote text to append later (store at element_map level)
        note_text = _extract_full_text(element)
        element_map.append({'type': 'footnote', 'text': note_text, 'id': fn_id})

        return {'html_parts': html_parts, 'element_map': element_map}

    # Handle other elements generically
    html_parts.append(f'<span class="tei-{tg}" data-xpath="{xpth}">')
    element_map.append({'xpath': xpth, 'element_type': tg,
                        'start_pos': len("".join(html_parts))})
    if element.text:
        html_parts.append(_escape_html(element.text))
    for ch in element:
        process_element(ch, html_parts, element_map, xpth)
        if ch.tail:
            html_parts.append(_escape_html(ch.tail))
    html_parts.append(f'</span>')
    
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
    # Make sure the input is a string
    if isinstance(display_html, bytes):
        display_html = display_html.decode('utf-8')
        
    # Parse using HTML parser that preserves structure
    parser = etree.HTMLParser(remove_blank_text=False, remove_comments=False, recover=True)
    try:
        root = etree.fromstring(f'<root>{display_html}</root>', parser)
    except Exception as e:
        # If parsing fails, return the original content
        print(f"Error parsing HTML: {str(e)}")
        return display_html

    # We no longer escape XML tags - removed that code as it was causing problems
    
    next_id = 0
    # Process all text nodes that are not inside script or style
    for node in root.xpath('//*[text() and not(self::script) and not(self::style) and not(self::word)]'):
        if node.xpath('ancestor::word'):
            continue
            
        text = node.text
        if not text or not text.strip():
            continue
            
        # Split by whitespace while preserving it
        tokens = []
        current_pos = 0
        for match in re.finditer(r'\S+', text):
            # Add any whitespace before this token
            if match.start() > current_pos:
                tokens.append((text[current_pos:match.start()], True))  # True = is whitespace
            # Add the token itself
            tokens.append((match.group(), False))  # False = not whitespace
            current_pos = match.end()
        # Add any trailing whitespace
        if current_pos < len(text):
            tokens.append((text[current_pos:], True))
            
        # Replace the text with tokenized elements
        node.text = None
        
        # Insert tokens and whitespace
        for i, (token, is_whitespace) in enumerate(tokens):
            if is_whitespace:
                # For whitespace, just add it as text
                if i == 0:
                    node.text = token
                else:
                    prev = node[i-1] if i-1 < len(node) else None
                    if prev is not None:
                        prev.tail = token
            else:
                # For actual tokens, create a word element
                w = etree.Element('word')
                w.set('id', f'tei_{next_id}')
                next_id += 1
                w.text = token
                node.append(w)
    
    # Convert back to HTML string
    html = etree.tostring(root, encoding='unicode', method='html')
    
    # strip the artificial <root> wrapper
    result = html.replace('<root>', '').replace('</root>', '')
    
    return result