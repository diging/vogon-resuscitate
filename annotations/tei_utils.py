"""
TEI-XML Integration utilities for Vogon.

This module provides helper functions for:
1. Parsing TEI-XML documents
2. Converting TEI-XML to a format suitable for display and annotation
3. Creating and resolving XPointer references
4. Managing annotation positions within TEI documents
5. Detecting content types in imported texts
"""

import re
import json
from lxml import etree
from django.utils.safestring import mark_safe
from annotations.tasks import tokenize

# ===== Content Type Detection =====

def detect_content_type(text_content):
    """
    Detect the content type of a text by examining its structure.
    
    Parameters
    ----------
    text_content : str
        The content to analyze
        
    Returns
    -------
    dict
        A dictionary containing:
        - is_xml: Boolean indicating if content is XML
        - is_tei: Boolean indicating if content is TEI-XML
        - content_type: Suggested MIME type ('text/xml+tei', 'text/xml', or 'text/plain')
    """
    is_xml = False
    is_tei = False
    
    # Simple checks for XML format
    if text_content.strip().startswith('<?xml') or text_content.strip().startswith('<'):
        is_xml = True
        # Check for TEI namespace or common TEI elements
        if any(marker in text_content for marker in [
            '<TEI', '<tei', '<teiHeader', '<teiheader',
            'xmlns="http://www.tei-c.org"', 'xmlns:tei'
        ]):
            is_tei = True
    
    # Determine content type based on detection results
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
        - css: CSS styles for TEI elements
        - facsimile_data: Information about facsimile images
    """
    try:
        root = etree.fromstring(xml_content.encode('utf-8'))
        
        # Remove namespaces for easier processing
        clean_root = strip_namespaces(root)
        clean_xml = etree.tostring(clean_root, encoding='unicode')
        
        # Extract metadata from the TEI header
        metadata = extract_tei_metadata(clean_root)
        
        # Extract facsimile information if available
        facsimile_data = extract_facsimile_data(clean_root)
        
        # Create a display version and element map
        display_result = create_display_content(clean_root)
        
        return {
            'original_xml': xml_content,
            'clean_xml': clean_xml,
            'display_html': display_result['display_html'],
            'element_map': display_result['element_map'],
            'tei_metadata': metadata,
            'css': display_result['css'],
            'facsimile_data': facsimile_data
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
        'language': None,
        'idno': None,
        'repository': None,
        'institution': None,
        'settlement': None,
        'country': None,
        'msDesc': [],
        'handDesc': []
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
    
    # Extract manuscript description
    for ms_desc in root.findall('.//msDesc'):
        ms_info = {}
        
        if 'xml:id' in ms_desc.attrib:
            ms_info['xml_id'] = ms_desc.attrib['xml:id']
        
        identifier = ms_desc.find('.//msIdentifier')
        if identifier is not None:
            for child in identifier:
                if child.text:
                    ms_info[child.tag] = child.text.strip()
        
        hand_desc = ms_desc.find('.//handDesc')
        if hand_desc is not None:
            hand_notes = []
            for hand_note in hand_desc.findall('.//handNote'):
                hand_info = {}
                for attr, value in hand_note.attrib.items():
                    hand_info[attr] = value
                if hand_note.text:
                    hand_info['description'] = hand_note.text.strip()
                hand_notes.append(hand_info)
            
            ms_info['hands'] = hand_notes
        
        metadata['msDesc'].append(ms_info)
    
    return metadata

def extract_facsimile_data(root):
    """
    Extract information about facsimile images from the TEI document.
    
    Parameters
    ----------
    root : lxml.etree._Element
        The root element of a TEI document
        
    Returns
    -------
    list
        List of dictionaries with facsimile information
    """
    facsimile_data = []
    
    facsimile = root.find('.//facsimile')
    if facsimile is not None:
        for graphic in facsimile.findall('.//graphic'):
            image_info = {}
            
            # Extract attributes
            for attr, value in graphic.attrib.items():
                image_info[attr.split('}')[-1]] = value
            
            facsimile_data.append(image_info)
    
    return facsimile_data

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
        - css: CSS styles for TEI elements
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
        'element_map': result['element_map'],
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
        # Get the facs attribute if present
        facs_attr = element.get('facs', '')
        facs_html = f' data-facs="{facs_attr}"' if facs_attr else ''
        
        html_parts.append(f'<p class="tei-p" data-xpath="{current_path}"{facs_html}>')
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
        html_parts.append(f'<h3 class="tei-head" data-xpath="{current_path}">')
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
    
    # Page breaks 
    elif current_tag == 'pb':
        page_n = element.get('n', '')
        facs = element.get('facs', '')
        html_parts.append(f'<div class="tei-pb" data-xpath="{current_path}" data-n="{page_n}" data-facs="{facs}"><hr/><span class="tei-pb-label">Page {page_n}</span></div>')
        element_map.append({
            'xpath': current_path,
            'element_type': 'pagebreak',
            'page': page_n,
            'facs': facs,
            'start_pos': len(''.join(html_parts))
        })
        
    # Line breaks
    elif current_tag == 'lb':
        break_type = element.get('break', '')
        line_n = element.get('n', '')
        
        classes = ['tei-lb']
        if break_type == 'yes':
            classes.append('tei-lb-break')
        elif break_type == 'no':
            classes.append('tei-lb-nobreak')
            
        lb_html = f'<br class="{" ".join(classes)}" data-xpath="{current_path}" data-n="{line_n}" />'
        if line_n:
            lb_html = f'<span class="tei-line-num">{line_n}</span>{lb_html}'
            
        html_parts.append(lb_html)
        element_map.append({
            'xpath': current_path,
            'element_type': 'linebreak',
            'break_type': break_type,
            'start_pos': len(''.join(html_parts))
        })
        
    # Gaps/lacunae in the text 
    elif current_tag == 'gap':
        reason = element.get('reason', '')
        extent = element.get('extent', '')
        unit = element.get('unit', '')
        
        gap_html = f'<span class="tei-gap" data-xpath="{current_path}" data-reason="{reason}" data-extent="{extent}" data-unit="{unit}" title="Gap: {extent} {unit} - {reason}">[...]</span>'
        html_parts.append(gap_html)
        element_map.append({
            'xpath': current_path,
            'element_type': 'gap',
            'reason': reason,
            'extent': extent,
            'unit': unit,
            'start_pos': len(''.join(html_parts))
        })
        
    # Choice elements (orig/reg, abbr/expan) - scholarly editing
    elif current_tag == 'choice':
        html_parts.append(f'<span class="tei-choice" data-xpath="{current_path}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'choice',
            'start_pos': len(''.join(html_parts))
        })
        
        # We need to process each child, but display them correctly
        orig_elem = element.find('orig')
        reg_elem = element.find('reg')
        abbr_elem = element.find('abbr')
        expan_elem = element.find('expan')
        
        # Process choice between original form and regularized form
        if orig_elem is not None and reg_elem is not None:
            # Add the regularized form (visible by default)
            html_parts.append('<span class="tei-reg">')
            if reg_elem.text:
                html_parts.append(reg_elem.text)
            for child in reg_elem:
                process_element(child, html_parts, element_map, f"{current_path}/reg")
                if child.tail:
                    html_parts.append(child.tail)
            html_parts.append('</span>')
            
            # Add the original form (hidden by default, shown on hover)
            html_parts.append('<span class="tei-orig" style="display:none;">')
            if orig_elem.text:
                html_parts.append(orig_elem.text)
            for child in orig_elem:
                process_element(child, html_parts, element_map, f"{current_path}/orig")
                if child.tail:
                    html_parts.append(child.tail)
            html_parts.append('</span>')
            
        # Process choice between abbreviation and expansion
        elif abbr_elem is not None and expan_elem is not None:
            # Add the expanded form (visible by default)
            html_parts.append('<span class="tei-expan">')
            if expan_elem.text:
                html_parts.append(expan_elem.text)
            for child in expan_elem:
                process_element(child, html_parts, element_map, f"{current_path}/expan")
                if child.tail:
                    html_parts.append(child.tail)
            html_parts.append('</span>')
            
            # Add the abbreviated form (hidden by default, shown on hover)
            html_parts.append('<span class="tei-abbr" style="display:none;">')
            if abbr_elem.text:
                html_parts.append(abbr_elem.text)
            for child in abbr_elem:
                process_element(child, html_parts, element_map, f"{current_path}/abbr")
                if child.tail:
                    html_parts.append(child.tail)
            html_parts.append('</span>')
        
        # If the choice structure doesn't match expected patterns, just process children
        else:
            if element.text:
                html_parts.append(element.text)
            for child in element:
                process_element(child, html_parts, element_map, current_path)
                if child.tail:
                    html_parts.append(child.tail)
        
        html_parts.append('</span>')
    
    # Abbreviations
    elif current_tag == 'abbr':
        # When abbr appears outside of choice
        html_parts.append(f'<span class="tei-abbr standalone" data-xpath="{current_path}" title="Abbreviation">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'abbreviation',
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</span>')
        
    # Expansions
    elif current_tag == 'expan':
        # When expan appears outside of choice
        html_parts.append(f'<span class="tei-expan standalone" data-xpath="{current_path}" title="Expansion">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'expansion',
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</span>')
    
    # Editorial supplied text
    elif current_tag == 'supplied':
        reason = element.get('reason', '')
        html_parts.append(f'<span class="tei-supplied" data-xpath="{current_path}" data-reason="{reason}" title="Supplied: {reason}">[')
        element_map.append({
            'xpath': current_path,
            'element_type': 'supplied',
            'reason': reason,
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append(']</span>')
    
    # Expanded text (ex tag inside expan)
    elif current_tag == 'ex':
        html_parts.append(f'<span class="tei-ex" data-xpath="{current_path}" title="Editorial expansion">(')
        element_map.append({
            'xpath': current_path,
            'element_type': 'expansion_text',
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append(')</span>')
        
    elif current_tag == 'div':
        # Get type and n attributes if present
        div_type = element.get('type', '')
        div_n = element.get('n', '')
        
        div_classes = ['tei-div']
        if div_type:
            div_classes.append(f'tei-div-{div_type}')
        
        div_attrs = f' data-xpath="{current_path}"'
        if div_type:
            div_attrs += f' data-type="{div_type}"'
        if div_n:
            div_attrs += f' data-n="{div_n}"'
        
        html_parts.append(f'<div class="{" ".join(div_classes)}"{div_attrs}>')
        element_map.append({
            'xpath': current_path,
            'element_type': 'division',
            'div_type': div_type,
            'n': div_n,
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
        
        html_parts.append(f'<span class="{style_class}" data-xpath="{current_path}" data-rend="{rend}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'highlight',
            'rend': rend,
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</span>')
        
    # Editorial additions
    elif current_tag == 'add':
        place = element.get('place', '')
        hand = element.get('hand', '')
        
        add_classes = ['tei-add']
        if place:
            add_classes.append(f'tei-add-{place}')
        
        add_attrs = f' data-xpath="{current_path}"'
        if place:
            add_attrs += f' data-place="{place}"'
        if hand:
            add_attrs += f' data-hand="{hand}"'
            add_classes.append('tei-hand')
            
        html_parts.append(f'<span class="{" ".join(add_classes)}"{add_attrs} title="Addition {place} by {hand}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'addition',
            'place': place,
            'hand': hand,
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</span>')
        
    # Editorial deletions
    elif current_tag == 'del':
        hand = element.get('hand', '')
        
        del_classes = ['tei-del']
        if hand:
            del_classes.append('tei-hand')
            
        del_attrs = f' data-xpath="{current_path}"'
        if hand:
            del_attrs += f' data-hand="{hand}"'
            
        html_parts.append(f'<span class="{" ".join(del_classes)}"{del_attrs} title="Deletion by {hand}">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'deletion',
            'hand': hand,
            'start_pos': len(''.join(html_parts))
        })
        
        if element.text:
            html_parts.append(element.text)
            
        for child in element:
            process_element(child, html_parts, element_map, current_path)
            if child.tail:
                html_parts.append(child.tail)
                
        html_parts.append('</span>')
        
    # Substitutions (combined del/add)
    elif current_tag == 'subst':
        html_parts.append(f'<span class="tei-subst" data-xpath="{current_path}" title="Editorial substitution">')
        element_map.append({
            'xpath': current_path,
            'element_type': 'substitution',
            'start_pos': len(''.join(html_parts))
        })
        
        # Process in specific order: first del, then add
        del_elem = element.find('del')
        add_elem = element.find('add')
        
        # Process deletion if present
        if del_elem is not None:
            process_element(del_elem, html_parts, element_map, f"{current_path}/del")
        
        # Process addition if present
        if add_elem is not None:
            process_element(add_elem, html_parts, element_map, f"{current_path}/add")
        
        # Process any other children
        for child in element:
            if child is not del_elem and child is not add_elem:
                process_element(child, html_parts, element_map, current_path)
                if child.tail:
                    html_parts.append(child.tail)
        
        html_parts.append('</span>')
    
    # Lists
    elif current_tag in ('list'):
        html_parts.append(f'<ul class="tei-list" data-xpath="{current_path}">')
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
        
    # List items
    elif current_tag in ('item'):
        html_parts.append(f'<li class="tei-item" data-xpath="{current_path}">')
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
        # Create a generic span for unhandled elements
        html_parts.append(f'<span class="tei-{current_tag}" data-xpath="{current_path}">')
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
                
        html_parts.append('</span>')
    
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
    try:
        tree = etree.fromstring(f"<root>{display_html}</root>", parser)
    except Exception as e:
        # Handle possible parsing errors
        raise ValueError(f"Failed to parse HTML for tokenization: {str(e)}")
    
    word_id_counter = 0
    
    # Process text nodes while preserving structure
    for element in tree.xpath('//*[text()]'):
        # Skip certain elements that shouldn't be tokenized
        if element.tag in ('script', 'style', 'word'):
            continue
            
        # Skip elements with no text content
        if not element.text or not element.text.strip():
            continue
        
        # Skip elements that are already inside tokenized content
        parent = element.getparent()
        is_inside_word = False
        while parent is not None:
            if parent.tag == 'word':
                is_inside_word = True
                break
            parent = parent.getparent()
        
        if is_inside_word:
            continue
            
        # Tokenize the text content of this element
        tokenized_text = []
        for word in element.text.split():
            if not word.strip():  # Skip empty words
                continue
                
            # Create a word tag with a unique ID
            word_elem = etree.Element('word')
            word_elem.set('id', f'tei_{word_id_counter}')
            word_elem.text = word
            tokenized_text.append(etree.tostring(word_elem, encoding='unicode'))
            word_id_counter += 1
            
        # Replace the text with tokenized version
        if tokenized_text:
            element.text = ' '.join(tokenized_text)
    
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
    static_id_counter = [0]  # Use a list for a mutable counter
    
    def replace_word(match):
        word = match.group(0)
        if not word.strip():  # Don't tokenize whitespace
            return word
            
        word_id = f'tei_{static_id_counter[0]}'
        static_id_counter[0] += 1
        
        return f'<word id="{word_id}">{word}</word>'
    
    # Use regex to find words while preserving HTML
    word_pattern = r'\b\w+\b'
    result = re.sub(word_pattern, replace_word, text)
    
    return result

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

# Add a new function to resolve XPointer ranges that span multiple elements

def resolve_xpointer_range(start_xpointer, end_xpointer, document):
    """
    Resolve a range of text specified by two XPointer references.
    
    Parameters
    ----------
    start_xpointer : str
        XPointer reference for the start of the range
    end_xpointer : str
        XPointer reference for the end of the range
    document : lxml.etree._Element
        The XML document
        
    Returns
    -------
    str
        The text in the range
    """
    start_parts = parse_xpointer(start_xpointer)
    end_parts = parse_xpointer(end_xpointer)
    
    # Find the element at the start xpath
    start_element = document.xpath(start_parts['xpath'])[0]
    
    # Find the element at the end xpath
    end_element = document.xpath(end_parts['xpath'])[0]
    
    # Check if they're the same element
    if start_element is end_element:
        # Get the text content
        text = ''.join(start_element.xpath('.//text()'))
        # Extract the specified range
        return text[start_parts['start_offset']:end_parts['end_offset']]
    
    # For different elements, we need to find a common ancestor and gather text
    
    # Get paths to the root for start and end elements
    start_path = [start_element]
    end_path = [end_element]
    
    current = start_element
    while current.getparent() is not None:
        current = current.getparent()
        start_path.append(current)
    
    current = end_element
    while current.getparent() is not None:
        current = current.getparent()
        end_path.append(current)
    
    # Find common ancestor
    common_ancestor = None
    for elem in start_path:
        if elem in end_path:
            common_ancestor = elem
            break
    
    if common_ancestor is None:
        raise ValueError("No common ancestor found between elements")
    
    # Get index of common ancestor in paths
    start_idx = start_path.index(common_ancestor)
    end_idx = end_path.index(common_ancestor)
    
    # Calculate path from common ancestor to start and end
    path_to_start = start_path[:start_idx]  # Elements from start to common ancestor (exclusive)
    path_to_end = end_path[:end_idx]  # Elements from end to common ancestor (exclusive)
    
    # Get all elements between start and end (inclusive)
    elements_in_range = []
    
    # This is a simple approach - will need refinement for complex document structures
    found_start = False
    
    def traverse_for_range(element):
        nonlocal found_start, elements_in_range
        
        if element is start_element:
            found_start = True
        
        if found_start:
            elements_in_range.append(element)
        
        if element is end_element:
            found_start = False
            return True
        
        for child in element:
            if traverse_for_range(child):
                return True
        
        return False
    
    traverse_for_range(common_ancestor)
    
    # Extract text from elements in range
    text_parts = []
    
    # First element - from start_offset to end
    first_text = ''.join(start_element.xpath('.//text()'))
    text_parts.append(first_text[start_parts['start_offset']:])
    
    # Middle elements - entire text content
    for elem in elements_in_range[1:-1]:
        text_parts.append(''.join(elem.xpath('.//text()')))
    
    # Last element - from start to end_offset
    if len(elements_in_range) > 1:
        last_text = ''.join(end_element.xpath('.//text()'))
        text_parts.append(last_text[:end_parts['end_offset']])
    
    return ''.join(text_parts) 