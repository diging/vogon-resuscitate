"""
TEI-XML Integration utilities for Vogon.

This module provides helper functions for:
1. Parsing TEI-XML documents
2. Converting TEI-XML to a format suitable for display and annotation
3. Creating and resolving XPointer references
4. Managing annotation positions within TEI documents
"""

import re
import json
from lxml import etree
from django.utils.safestring import mark_safe
from annotations.tasks import tokenize

# ===== TEI Parsing Functions =====

def parse_tei_document(xml_content):
    """
    Parse a TEI-XML document and prepare it for annotation in Vogon.
    
    Parameters
    ----------
    xml_content : str
        The TEI-XML content as a string
        
    Returns
    -------
    dict
        A dictionary containing:
        - original_xml: The original XML content
        - clean_xml: Namespace-stripped XML for easier processing
        - display_html: HTML representation for display
        - element_map: Mapping between display positions and XML elements
        - tei_metadata: Extracted metadata from TEI header
    """
    try:
        root = etree.fromstring(xml_content.encode('utf-8'))
        
        # Remove namespaces for easier processing
        clean_root = strip_namespaces(root)
        clean_xml = etree.tostring(clean_root, encoding='unicode')
        
        # Extract metadata from the TEI header
        metadata = extract_tei_metadata(clean_root)
        
        # Create a display version and element map
        display_result = create_display_content(clean_root)
        
        return {
            'original_xml': xml_content,
            'clean_xml': clean_xml,
            'display_html': display_result['display_html'],
            'element_map': display_result['element_map'],
            'tei_metadata': metadata
        }
    except Exception as e:
        raise ValueError(f"Failed to parse TEI-XML: {str(e)}")

def strip_namespaces(root):
    """
    Remove namespaces from XML element tags for easier XPath querying.
    
    Parameters
    ----------
    root : lxml.etree._Element
        The root element of an XML document
        
    Returns
    -------
    lxml.etree._Element
        A copy of the XML tree with namespaces removed from tags
    """
    # Create a new tree without namespaces
    clean_root = etree.Element(root.tag.split('}')[-1] if '}' in root.tag else root.tag)
    
    # Copy attributes
    for name, value in root.attrib.items():
        clean_name = name.split('}')[-1] if '}' in name else name
        clean_root.set(clean_name, value)
    
    # Process children recursively
    for child in root:
        if isinstance(child, etree._Element):
            clean_child = strip_namespaces(child)
            clean_root.append(clean_child)
        else:
            # Text content
            if root.text:
                clean_root.text = root.text
            if root.tail:
                clean_root.tail = root.tail
                
    return clean_root

def extract_tei_metadata(root):
    """
    Extract metadata from the TEI header.
    
    Parameters
    ----------
    root : lxml.etree._Element
        The root element of a TEI document
        
    Returns
    -------
    dict
        Dictionary of metadata fields
    """
    metadata = {
        'title': None,
        'author': None,
        'publisher': None,
        'date': None,
        'source': None,
        'language': None
    }
    
    # Try to extract the title
    title_elem = root.find('.//titleStmt/title')
    if title_elem is not None and title_elem.text:
        metadata['title'] = title_elem.text.strip()
    
    # Try to extract the author
    author_elem = root.find('.//titleStmt/author')
    if author_elem is not None:
        if author_elem.text:
            metadata['author'] = author_elem.text.strip()
        else:
            # Handle complex author elements with name parts
            name_parts = []
            for name_part in author_elem.findall('.//persName/*'):
                if name_part.text:
                    name_parts.append(name_part.text.strip())
            if name_parts:
                metadata['author'] = ' '.join(name_parts)
    
    # Try to extract other metadata
    publisher_elem = root.find('.//publicationStmt/publisher')
    if publisher_elem is not None and publisher_elem.text:
        metadata['publisher'] = publisher_elem.text.strip()
    
    date_elem = root.find('.//publicationStmt/date') or root.find('.//sourceDesc//date')
    if date_elem is not None:
        if date_elem.text:
            metadata['date'] = date_elem.text.strip()
        elif 'when' in date_elem.attrib:
            metadata['date'] = date_elem.attrib['when']
    
    # Extract source information
    source_elem = root.find('.//sourceDesc')
    if source_elem is not None:
        source_text = source_elem.xpath('string()').strip()
        if source_text:
            metadata['source'] = source_text
    
    # Extract language
    language_elem = root.find('.//language')
    if language_elem is not None:
        if language_elem.text:
            metadata['language'] = language_elem.text.strip()
        elif 'ident' in language_elem.attrib:
            metadata['language'] = language_elem.attrib['ident']
    
    return metadata

# ===== TEI to Display Conversion =====

def create_display_content(root):
    """
    Convert a TEI document to HTML for display, tracking element positions.
    
    Parameters
    ----------
    root : lxml.etree._Element
        The root element of a TEI document
        
    Returns
    -------
    dict
        Dictionary containing:
        - display_html: HTML for display in the browser
        - element_map: Mapping between display positions and XML elements
    """
    # Find the text body - this is where the main content is
    body = root.find('.//body') or root.find('.//text')
    
    if body is None:
        # Fallback if no body is found
        body = root
    
    # Process the body content
    result = process_element(body, [], [])
    
    # Combine the HTML fragments and return with element map
    return {
        'display_html': mark_safe(''.join(result['html_parts'])),
        'element_map': result['element_map']
    }

def process_element(element, html_parts, element_map, path=''):
    """
    Recursively process TEI elements and convert to HTML with position tracking.
    
    Parameters
    ----------
    element : lxml.etree._Element
        The current XML element to process
    html_parts : list
        List to collect HTML fragments
    element_map : list
        List to collect element mapping information
    path : str
        Current XPath
        
    Returns
    -------
    dict
        Updated html_parts and element_map
    """
    # Build the current element's path
    current_tag = element.tag
    if not path:
        current_path = f"/{current_tag}"
    else:
        current_path = f"{path}/{current_tag}"
    
    # Add position predicates to make path unique
    current_path = add_position_predicates(element, current_path)
    
    # Handle different TEI elements based on their tag
    if current_tag in ('p', 'paragraph'):
        html_parts.append('<p class="tei-p" data-xpath="' + current_path + '">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'paragraph',
            'start_pos': len(''.join(html_parts))
        })
        
        # Process text content
        if element.text:
            html_parts.append(element.text)
        
        # Process children
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
        
        html_parts.append('</p>')
        
    elif current_tag in ('head', 'heading'):
        html_parts.append('<h3 class="tei-head" data-xpath="' + current_path + '">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'heading',
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</h3>')
        
    elif current_tag == 'lb':
        html_parts.append('<br data-xpath="' + current_path + '" />')
        element_map.append({
            'xpath': current_path,
            'element_type': 'linebreak',
            'start_pos': len(''.join(html_parts))
        })
        
    elif current_tag == 'div':
        html_parts.append('<div class="tei-div" data-xpath="' + current_path + '">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'division',
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</div>')
        
    elif current_tag in ('hi', 'emph'):
        # Extract styling information
        rend = element.get('rend', '')
        style_class = f"tei-{rend}" if rend else "tei-hi"
        
        html_parts.append(f'<span class="{style_class}" data-xpath="{current_path}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'highlight',
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</span>')
        
    elif current_tag in ('list'):
        html_parts.append('<ul class="tei-list" data-xpath="' + current_path + '">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'list',
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</ul>')
        
    elif current_tag in ('item'):
        html_parts.append('<li class="tei-item" data-xpath="' + current_path + '">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'list-item',
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</li>')
        
    # Generic handling for other elements
    else:
        element_map.append({
            'xpath': current_path,
            'element_type': current_tag,
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
    
    return {
        'html_parts': html_parts,
        'element_map': element_map
    }

def add_position_predicates(element, path):
    """
    Add position predicates to make an XPath unique.
    
    Parameters
    ----------
    element : lxml.etree._Element
        The element to create a path for
    path : str
        The base XPath
        
    Returns
    -------
    str
        XPath with position predicates
    """
    # Get the parent element
    parent = element.getparent()
    if parent is None:
        return path
    
    # Count siblings with the same tag to determine position
    position = 1
    for sibling in parent:
        if sibling is element:
            break
        if sibling.tag == element.tag:
            position += 1
    
    # Add the position predicate to the path
    path_parts = path.split('/')
    path_parts[-1] = f"{path_parts[-1]}[{position}]"
    return '/'.join(path_parts)

# ===== XPointer Functions =====

def create_xpointer(xpath, start_offset, end_offset):
    """
    Create an XPointer reference from an XPath and character offsets.
    
    Parameters
    ----------
    xpath : str
        XPath to the element
    start_offset : int
        Character offset from the start of the element
    end_offset : int
        Character offset from the start of the element
        
    Returns
    -------
    str
        XPointer reference
    """
    return f"{xpath}::{start_offset},{end_offset}"

def parse_xpointer(xpointer):
    """
    Parse an XPointer reference into its components.
    
    Parameters
    ----------
    xpointer : str
        XPointer reference
        
    Returns
    -------
    dict
        Dictionary containing:
        - xpath: XPath to the element
        - start_offset: Start character offset
        - end_offset: End character offset
    """
    match = re.match(r'(.+)::(\d+),(\d+)$', xpointer)
    if match:
        xpath, start, end = match.groups()
        return {
            'xpath': xpath,
            'start_offset': int(start),
            'end_offset': int(end)
        }
    raise ValueError(f"Invalid XPointer format: {xpointer}")

def resolve_xpointer(xpointer, document):
    """
    Resolve an XPointer to the corresponding text in a document.
    
    Parameters
    ----------
    xpointer : str
        XPointer reference
    document : lxml.etree._Element
        The XML document
        
    Returns
    -------
    str
        The referenced text
    """
    parts = parse_xpointer(xpointer)
    element = document.xpath(parts['xpath'])[0]
    
    # Get the text content of the element
    text = ''.join(element.xpath('.//text()'))
    
    # Extract the specified range
    return text[parts['start_offset']:parts['end_offset']]

# ===== Tokenization for TEI =====

def tokenize_tei_content(display_html):
    """
    Tokenize the text content within TEI elements for annotation.
    
    This preserves the HTML structure but wraps each word in <word> tags.
    
    Parameters
    ----------
    display_html : str
        The HTML display version of a TEI document
        
    Returns
    -------
    str
        HTML with tokenized words inside elements
    """
    # Parse the HTML
    parser = etree.HTMLParser()
    tree = etree.fromstring(f"<root>{display_html}</root>", parser)
    
    # Process text nodes
    for element in tree.xpath('//*[text()]'):
        # Skip certain elements (like <script>, <style>)
        if element.tag in ('script', 'style'):
            continue
            
        # Tokenize the text content of this element
        if element.text and element.text.strip():
            element.text = tokenize_with_html(element.text)
    
    # Convert back to string
    result = etree.tostring(tree, encoding='unicode', method='html')
    
    # Remove the root wrapper
    result = result.replace('<root>', '').replace('</root>', '')
    
    return result

def tokenize_with_html(text):
    """
    Tokenize text while preserving HTML tags.
    
    Parameters
    ----------
    text : str
        Text content to tokenize
        
    Returns
    -------
    str
        Tokenized content with <word> tags
    """
    # Special case for tokenize function that preserves HTML
    words = text.split()
    result = []
    for i, word in enumerate(words):
        word_html = f'<word id="tei_{i}">{word}</word>'
        result.append(word_html)
    
    return ' '.join(result)

# ===== Document Position for TEI =====

def get_element_at_position(position, element_map):
    """
    Find the TEI element at a given position in the display HTML.
    
    Parameters
    ----------
    position : int
        Character position in the display HTML
    element_map : list
        List of mapped elements with their positions
        
    Returns
    -------
    dict
        The element mapping for the closest element
    """
    # Sort element map by start position
    sorted_map = sorted(element_map, key=lambda x: x['start_pos'])
    
    # Find the closest element before the position
    current_element = sorted_map[0]
    for element in sorted_map:
        if element['start_pos'] <= position:
            current_element = element
        else:
            break
    
    return current_element

def calculate_offset_in_element(position, element, element_map, display_html):
    """
    Calculate character offset within a TEI element.
    
    Parameters
    ----------
    position : int
        Position in display HTML
    element : dict
        Element mapping information
    element_map : list
        Complete element mapping
    display_html : str
        Display HTML content
        
    Returns
    -------
    int
        Character offset within the element
    """
    element_start = element['start_pos']
    
    # Find the content length up to the position
    content_length = 0
    html_up_to_position = display_html[:position]
    
    # Remove HTML tags to get text content length
    text_content = re.sub(r'<[^>]+>', '', html_up_to_position[element_start:])
    
    return len(text_content)

def create_position_from_selection(start_pos, end_pos, element_map, display_html):
    """
    Create a document position from a text selection in the display HTML.
    
    Parameters
    ----------
    start_pos : int
        Start position in display HTML
    end_pos : int
        End position in display HTML
    element_map : list
        Element mapping information
    display_html : str
        Display HTML content
        
    Returns
    -------
    dict
        Document position information with XPointer reference
    """
    # Find the elements at start and end positions
    start_element = get_element_at_position(start_pos, element_map)
    end_element = get_element_at_position(end_pos, element_map)
    
    # If selection spans multiple elements, we need special handling
    if start_element != end_element:
        # simplify by using the common ancestor
        return {
            'position_type': 'TXP',
            'position_value': 'Range spanning multiple elements not fully implemented',
            'start_element': start_element['xpath'],
            'end_element': end_element['xpath']
        }
    
    # Calculate offsets within the element
    start_offset = calculate_offset_in_element(start_pos, start_element, element_map, display_html)
    end_offset = calculate_offset_in_element(end_pos, end_element, element_map, display_html)
    
    # Create XPointer reference
    xpointer = create_xpointer(start_element['xpath'], start_offset, end_offset)
    
    return {
        'position_type': 'TXP',  # TEI XPointer
        'position_value': xpointer
    } 