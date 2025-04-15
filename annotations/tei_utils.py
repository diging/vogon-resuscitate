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

import re
import json
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
            'xmlns="http://www.tei-c.org"', 'xmlns:tei'
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
    """
    Recursively convert TEI to minimal HTML, storing data-xpath.\
      - Hides raw TEI markup
      - For <choice>, defaults to <reg> text (with tooltip for <orig>)
      - For editorial tags (<add>, <del>, etc.), shows text in brackets or toggles
      - Adds <br> for <lb>, <hr> + label for <pb>, <p> for <p> tags, etc.
    """
    current_tag = element.tag
    # Build unique path with position predicates
    current_path = add_position_predicates(element, path)

    # Decide how to handle each TEI tag
    if current_tag in ('body', 'text'):
        # Just process children, no new HTML wrapper
        for child in element:
            process_element(child, html_parts, element_map, current_path)
        return {
            'html_parts': html_parts,
            'element_map': element_map
        }

    if current_tag in ('p', 'paragraph'):
        # Start paragraph
        html_parts.append(f'<p class="tei-p" data-xpath="{current_path}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'paragraph',
            'start_pos': len(''.join(html_parts))
        })

        # Text before children
        if element.text:
            html_parts.append(_escape_html(element.text))

        # Recurse children
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))

        html_parts.append('</p>')

    elif current_tag == 'head':
        html_parts.append(f'<h3 class="tei-head" data-xpath="{current_path}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'heading',
            'start_pos': len(''.join(html_parts))
        })

        if element.text:
            html_parts.append(_escape_html(element.text))
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))
        html_parts.append('</h3>')

    elif current_tag == 'pb':
        page_n = element.get('n', '')
        facs = element.get('facs', '')
        html_parts.append(
            f'<div class="tei-pb" data-xpath="{current_path}" data-n="{page_n}" data-facs="{facs}">'
            f'<hr/><span class="tei-pb-label">Page {page_n}</span></div>'
        )
        element_map.append({
            'xpath': current_path,
            'element_type': 'pagebreak',
            'page': page_n,
            'facs': facs,
            'start_pos': len(''.join(html_parts))
        })

    elif current_tag == 'lb':
        line_n = element.get('n', '')
        html_str = f'<br class="tei-lb" data-xpath="{current_path}" data-n="{line_n}" />'
        if line_n:
            # optionally display line number
            html_str = f'<span class="tei-line-num">{line_n}</span>{html_str}'
        html_parts.append(html_str)
        element_map.append({
            'xpath': current_path,
            'element_type': 'linebreak',
            'start_pos': len(''.join(html_parts))
        })

    elif current_tag == 'gap':
        reason = element.get('reason', '')
        extent = element.get('extent', '')
        unit = element.get('unit', '')
        gap_html = f'<span class="tei-gap" data-xpath="{current_path}" data-reason="{reason}" data-extent="{extent}" data-unit="{unit}" title="Gap: {extent} {unit} - {reason}">[...]</span>'
        html_parts.append(gap_html)
        element_map.append({
            'xpath': current_path,
            'element_type': 'gap',
            'start_pos': len(''.join(html_parts))
        })

    elif current_tag == 'choice':
        orig_elem = element.find('orig')
        reg_elem = element.find('reg')
        abbr_elem = element.find('abbr')
        expan_elem = element.find('expan')

        if orig_elem is not None and reg_elem is not None:
            # Use reg text, store orig in a tooltip
            original_txt = _extract_full_text(orig_elem).strip()
            regular_txt = _extract_full_text(reg_elem).strip()
            html_parts.append(
                f'<span class="tei-choice" data-xpath="{current_path}" '
                f'title="Original: {original_txt}">{regular_txt}</span>'
            )
            element_map.append({
                'xpath': current_path,
                'element_type': 'choice',
                'start_pos': len(''.join(html_parts))
            })
        elif abbr_elem is not None and expan_elem is not None:
            # Show expansion, tooltip for abbreviation
            abbr_txt = _extract_full_text(abbr_elem).strip()
            expan_txt = _extract_full_text(expan_elem).strip()
            html_parts.append(
                f'<span class="tei-choice" data-xpath="{current_path}" '
                f'title="Abbreviation: {abbr_txt}">{expan_txt}</span>'
            )
            element_map.append({
                'xpath': current_path,
                'element_type': 'choice',
                'start_pos': len(''.join(html_parts))
            })
        else:
            # Fallback - just process children as plain text
            for child in element:
                process_element(child, html_parts, element_map, current_path)
            element_map.append({
                'xpath': current_path,
                'element_type': 'choice',
                'start_pos': len(''.join(html_parts))
            })

    elif current_tag == 'add':
        # Show additions in brackets (or inline)
        reason = element.get('place') or element.get('reason', '')
        html_parts.append(f'<span class="tei-add" data-xpath="{current_path}" title="Add: {reason}">[')
        element_map.append({
            'xpath': current_path,
            'element_type': 'addition',
            'start_pos': len(''.join(html_parts))
        })

        if element.text:
            html_parts.append(_escape_html(element.text))
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))
        html_parts.append(']</span>')

    elif current_tag == 'del':
        # Show deletions with strikethrough or inline
        html_parts.append(f'<span class="tei-del" data-xpath="{current_path}" style="text-decoration: line-through;">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'deletion',
            'start_pos': len(''.join(html_parts))
        })
        if element.text:
            html_parts.append(_escape_html(element.text))
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))
        html_parts.append('</span>')

    elif current_tag == 'supplied':
        reason = element.get('reason', '')
        html_parts.append(f'<span class="tei-supplied" data-xpath="{current_path}" title="Supplied: {reason}">[')
        element_map.append({
            'xpath': current_path,
            'element_type': 'supplied',
            'start_pos': len(''.join(html_parts))
        })
        if element.text:
            html_parts.append(_escape_html(element.text))
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))
        html_parts.append(']</span>')

    elif current_tag == 'subst':
        # Typically <subst> includes <del> and <add> inside
        # We'll just process them in order or show them in sequence
        html_parts.append(f'<span class="tei-subst" data-xpath="{current_path}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'substitution',
            'start_pos': len(''.join(html_parts))
        })
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))
        html_parts.append('</span>')

    elif current_tag == 'div':
        # A higher-level division
        div_type = element.get('type', '')
        div_n = element.get('n', '')
        html_parts.append(f'<div class="tei-div" data-xpath="{current_path}" data-type="{div_type}" data-n="{div_n}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'division',
            'start_pos': len(''.join(html_parts))
        })

        if element.text:
            html_parts.append(_escape_html(element.text))
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))
        html_parts.append('</div>')

    elif current_tag in ('hi', 'emph'):
        # For bold, italic, or some styling indicated by rend?
        rend = element.get('rend', '')
        html_parts.append(f'<span class="tei-hi" data-xpath="{current_path}" data-rend="{rend}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'highlight',
            'start_pos': len(''.join(html_parts))
        })
        if element.text:
            html_parts.append(_escape_html(element.text))
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))
        html_parts.append('</span>')

    else:
        # Generic fallback for unhandled elements
        html_parts.append(f'<span class="tei-{current_tag}" data-xpath="{current_path}">')
        element_map.append({
            'xpath': current_path,
            'element_type': current_tag,
            'start_pos': len(''.join(html_parts))
        })
        if element.text:
            html_parts.append(_escape_html(element.text))
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(_escape_html(child.tail))
        html_parts.append('</span>')

    return {
        'html_parts': html_parts,
        'element_map': element_map
    }

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
    Tokenize the text content within the display HTML for word-level annotation.

    This preserves the HTML structure but wraps each word in <word> tags with unique IDs.
    """
    parser = etree.HTMLParser()
    try:
        tree = etree.fromstring(f"<root>{display_html}</root>", parser)
    except Exception as e:
        raise ValueError(f"Failed to parse HTML for tokenization: {str(e)}")

    word_id_counter = 0

    # Find elements that have text
    text_nodes = tree.xpath('//*[text()]')
    for element in text_nodes:
        # Skip certain tags
        if element.tag in ('script', 'style', 'word'):
            continue

        # Check if it's already inside a <word>
        ancestor_word = element.xpath('ancestor::word')
        if ancestor_word:
            # Already tokenized
            continue

        text_val = element.text
        if text_val and text_val.strip():
            tokens = text_val.split()
            tokenized_parts = []
            for t in tokens:
                if t.strip():
                    # Create a <word> element
                    word_el = etree.Element('word')
                    word_el.set('id', f'tei_{word_id_counter}')
                    word_el.text = t
                    word_id_counter += 1
                    tokenized_parts.append(etree.tostring(word_el, encoding='unicode'))
            # Replace the text node with tokenized content
            
            if tokenized_parts:
                element.text = ' '.join(tokenized_parts)

    # Convert back to string
    result_html = etree.tostring(tree, encoding='unicode', method='html')
    # Remove <root> wrapper
    # <root> might appear as a top-level element
    result_html = result_html.replace('<root>', '').replace('</root>', '')
    return result_html
