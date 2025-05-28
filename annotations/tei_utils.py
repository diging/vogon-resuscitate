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
        if hasattr(child, 'text') and child.text: # Check if child has text (elements do, comments might not)
            parts.append(child.text)
        if hasattr(child, 'tail') and child.tail: # Check for tail
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
        # Determine the primary TEI prefix to use, defaulting to 'tei'
        self.tei_prefix = next((p for p, u in self.namespaces.items() if u == "http://www.tei-c.org/ns/1.0"), "tei")
        # Ensure 'tei' is in the map if the standard URI is present, even if under a different prefix or default
        if "http://www.tei-c.org/ns/1.0" in self.namespaces.values() and self.namespaces.get(self.tei_prefix) != "http://www.tei-c.org/ns/1.0":
            # If 'tei' is mapped to something else, or not mapped, but the URI exists, find original prefix for standard URI
            original_tei_prefix_for_uri = next((p for p, u in self.namespaces.items() if u == "http://www.tei-c.org/ns/1.0"), None)
            if original_tei_prefix_for_uri: # If found under another prefix
                 if self.tei_prefix != original_tei_prefix_for_uri : # if 'tei' was a guess and is wrong
                      # This case is tricky; implies 'tei' might be used for non-TEI NS.
                      # For robust TEI element finding, we rely on self.tei_prefix correctly representing TEI.
                      # The namespace map should ideally have {'tei': 'http://www.tei-c.org/ns/1.0'}
                      pass # Assuming self.tei_prefix is the one to use for constructing tei:element queries
            elif self.namespaces.get(None) == "http://www.tei-c.org/ns/1.0": # Default namespace is TEI
                 self.namespaces[self.tei_prefix] = "http://www.tei-c.org/ns/1.0" # Ensure 'tei' prefix is available


    def _add_position_predicates_ns(self, element, parent_xpath_str):
        """
        Add position predicates to make an XPath unique, using prefixes.
        e.g., /tei:TEI[1]/tei:text[1]/tei:p[2].
        """
        ns_uri = element.namespace  # lxml property: gets the namespace URI of the element
        
        node_actual_prefix = None # The prefix found in the source XML for this element's ns_uri
        if ns_uri:
            for p, u in element.nsmap.items(): # Check element's own nsmap first
                if u == ns_uri:
                    node_actual_prefix = p
                    break
        
        # Determine the prefix to USE in XPath (prefer self.tei_prefix for standard TEI)
        xpath_prefix_to_use = None
        if ns_uri == "http://www.tei-c.org/ns/1.0":
            xpath_prefix_to_use = self.tei_prefix
        elif ns_uri and node_actual_prefix: # For other namespaces, use their actual prefix if known
             xpath_prefix_to_use = node_actual_prefix
        elif ns_uri : # A namespace URI exists, but no prefix in element's nsmap (e.g. inherited default)
            # Try to find a prefix from the global namespace map
            for p_global, u_global in self.namespaces.items():
                if u_global == ns_uri:
                    xpath_prefix_to_use = p_global
                    break


        local_tag_name = _local_name(element.tag)
        
        if xpath_prefix_to_use: # If we determined a prefix to use (like 'tei' or another)
            prefixed_tag = f"{xpath_prefix_to_use}:{local_tag_name}"
        else: # No namespace or no prefix determined for its namespace
            prefixed_tag = local_tag_name 

        parent = element.getparent()
        if parent is None:
            xpath_str = f"/{prefixed_tag}[1]" 
        else:
            index = 1
            # Count preceding siblings with the same expanded tag name ({ns}tag)
            for sibling in parent.iterchildren(element.tag): 
                if sibling is element:
                    break
                index += 1
            xpath_str = f"{parent_xpath_str}/{prefixed_tag}[{index}]"
        return xpath_str

    def process_element(self, element, parent_xpath_str=''):
        tag = _local_name(element.tag)
        current_element_xpath = self._add_position_predicates_ns(element, parent_xpath_str)

        handler_name = f"_process_{tag}"
        handler = getattr(self, handler_name, self._process_default_ns) # Default to namespace-aware version
        
        return handler(element, tag, current_element_xpath)

    def _process_default_ns(self, element, tag, current_element_xpath):
        """Default handler for all other elements, namespace-aware."""
        self.html_parts.append(f'<span class="tei-{tag}" data-xpath="{current_element_xpath}">')
        self.element_map.append({
            'xpath': current_element_xpath, 
            'element_type': tag,
            'start_pos': len("".join(self.html_parts))
        })
        
        if element.text:
            self.html_parts.append(_escape_html(element.text))
            
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
            if child_element.tail:
                self.html_parts.append(_escape_html(child_element.tail))
                
        self.html_parts.append(f'</span>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}

    def _process_body(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<div class="tei-{tag}" data-xpath="{current_element_xpath}">')
        self.element_map.append({
            'xpath': current_element_xpath, 
            'element_type': tag,
            'start_pos': len("".join(self.html_parts))
        })
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
            if child_element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append(f'</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_text(self, element, tag, current_element_xpath):
        return self._process_body(element, tag, current_element_xpath)
    
    def _process_p(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<p class="tei-p" data-xpath="{current_element_xpath}">')
        self.element_map.append({
            'xpath': current_element_xpath, 
            'element_type': 'paragraph',
            'start_pos': len("".join(self.html_parts))
        })
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
            if child_element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append('</p>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_paragraph(self, element, tag, current_element_xpath):
        return self._process_p(element, tag, current_element_xpath)
    
    def _process_head(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<h3 class="tei-head" data-xpath="{current_element_xpath}">')
        self.element_map.append({
            'xpath': current_element_xpath, 
            'element_type': 'heading',
            'start_pos': len("".join(self.html_parts))
        })
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
            if child_element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append('</h3>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}

    def _process_pb(self, element, tag, current_element_xpath):
        n, facs = element.get('n', ''), element.get('facs', '')
        self.html_parts.append(
            f'<div class="tei-pb" data-xpath="{current_element_xpath}" '
            f'data-n="{n}" data-facs="{facs}">'
            f'<hr/><span class="tei-pb-label">Page {n}</span></div>'
            '<span class="pb-spacer"></span>'
        )
        self.element_map.append({
            'xpath': current_element_xpath, 
            'element_type': 'pagebreak', 'page': n, 'facs': facs,
            'start_pos': len("".join(self.html_parts))
        })
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_lb(self, element, tag, current_element_xpath):
        n = element.get('n', '')
        br = f'<br class="tei-lb" data-xpath="{current_element_xpath}" data-n="{n}" />'
        if n: br = f'<span class="tei-line-num">{n}</span>{br}'
        self.html_parts.append(br)
        self.element_map.append({
            'xpath': current_element_xpath, 
            'element_type': 'linebreak',
            'start_pos': len("".join(self.html_parts))
        })
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_gap(self, element, tag, current_element_xpath):
        gap_html = (
            f'<span class="tei-gap" data-xpath="{current_element_xpath}" '
            f'data-reason="{element.get("reason", "")}" '
            f'data-extent="{element.get("extent", "")}" '
            f'data-unit="{element.get("unit", "")}" '
            f'title="Gap: {element.get("extent", "")} '
            f'{element.get("unit", "")} - {element.get("reason", "")}">'
            '[...]</span>'
        )
        self.html_parts.append(gap_html)
        self.element_map.append({
            'xpath': current_element_xpath, 
            'element_type': 'gap',
            'start_pos': len("".join(self.html_parts))
        })
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_choice(self, element, tag, current_element_xpath):
        orig = element.find(f'{self.tei_prefix}:orig', self.namespaces)
        reg = element.find(f'{self.tei_prefix}:reg', self.namespaces)
        abbr = element.find(f'{self.tei_prefix}:abbr', self.namespaces)
        expn = element.find(f'{self.tei_prefix}:expan', self.namespaces)
        
        processed_choice_content = False
        if orig is not None and reg is not None:
            self.html_parts.append(
                f'<span class="tei-choice" data-xpath="{current_element_xpath}" '
                f'title="Original: {_extract_full_text(orig)}">'
                f'{_extract_full_text(reg)}</span>'
            )
            processed_choice_content = True
        elif abbr is not None and expn is not None:
            self.html_parts.append(
                f'<span class="tei-choice" data-xpath="{current_element_xpath}" '
                f'title="Abbreviation: {_extract_full_text(abbr)}">'
                f'{_extract_full_text(expn)}</span>'
            )
            processed_choice_content = True
        
        if not processed_choice_content: # Fallback for other structures or if specific pairs not found
            self.html_parts.append(f'<span class="tei-choice" data-xpath="{current_element_xpath}">')
            if element.text: self.html_parts.append(_escape_html(element.text))
            for child_element in element:
                self.process_element(child_element, current_element_xpath)
                if child_element.tail: self.html_parts.append(_escape_html(child_element.tail))
            self.html_parts.append('</span>')
            
        self.element_map.append({
            'xpath': current_element_xpath, 
            'element_type': 'choice',
            'start_pos': len("".join(self.html_parts))
        })
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_list(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<ul class="tei-list" data-xpath="{current_element_xpath}">')
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
        self.html_parts.append('</ul>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_item(self, element, tag, current_element_xpath):
        return self._process_list_item(element, tag, current_element_xpath)
        
    def _process_label(self, element, tag, current_element_xpath):
        return self._process_list_item(element, tag, current_element_xpath)
    
    def _process_list_item(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<li class="tei-item" data-xpath="{current_element_xpath}">')
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
            if child_element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append('</li>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_table(self, element, tag, current_element_xpath):
        self.html_parts.append(f'<table class="tei-table" data-xpath="{current_element_xpath}">')
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
        self.html_parts.append('</table>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_row(self, element, tag, current_element_xpath):
        return self._process_table_row(element, tag, current_element_xpath)
        
    def _process_rowGrp(self, element, tag, current_element_xpath):
        return self._process_table_row(element, tag, current_element_xpath)
    
    def _process_table_row(self, element, tag, current_element_xpath):
        # Storing xpath on <tr> might be useful
        self.html_parts.append(f'<tr data-xpath="{current_element_xpath}">')
        self.element_map.append({ # Optional: map rows if needed
            'xpath': current_element_xpath, 'element_type': tag,
            'start_pos': len("".join(self.html_parts))
        })
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
        self.html_parts.append('</tr>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_cell(self, element, tag, current_element_xpath):
        return self._process_table_cell(element, tag, current_element_xpath)
        
    def _process_entry(self, element, tag, current_element_xpath):
        return self._process_table_cell(element, tag, current_element_xpath)
    
    def _process_table_cell(self, element, tag, current_element_xpath):
         # Storing xpath on <td> might be useful
        self.html_parts.append(f'<td data-xpath="{current_element_xpath}">')
        self.element_map.append({ # Optional: map cells if needed
            'xpath': current_element_xpath, 'element_type': tag,
            'start_pos': len("".join(self.html_parts))
        })
        if element.text: self.html_parts.append(_escape_html(element.text))
        for child_element in element:
            self.process_element(child_element, current_element_xpath)
            if child_element.tail: self.html_parts.append(_escape_html(child_element.tail))
        self.html_parts.append('</td>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_note(self, element, tag, current_element_xpath):
        if element.get('place') == 'foot':
            fn_id = f"fn-{len([m for m in self.element_map if m.get('type') == 'footnote']) + 1}"
            marker = f'<sup id="ref-{fn_id}" class="tei-fn-ref" data-xpath="{current_element_xpath}"></sup>'
            self.html_parts.append(marker)
            note_text = _extract_full_text(element)
            self.element_map.append({
                'type': 'footnote', 'text': note_text, 'id': fn_id,
                'xpath': current_element_xpath 
            })
        else: # Inline notes or other types of notes
            return self._process_default_ns(element, tag, current_element_xpath)
        return {'html_parts': self.html_parts, 'element_map': self.element_map}

# ===== Content Type Detection =====
def detect_content_type(text_content):
    """Detect the content type of a text by examining its structure."""
    is_xml = False
    is_tei = False
    if text_content.strip().startswith('<?xml'):
        is_xml = True
        if any(marker in text_content for marker in [
            '<TEI', '<tei', '<teiHeader', '<teiheader',
            'xmlns="http://www.tei-c.org/ns/1.0"', # Default TEI namespace
            'xmlns:tei="http://www.tei-c.org/ns/1.0"', # Prefixed TEI namespace
            'tei-c.org/ns/1.0' # Namespace URI itself might appear in xsi:schemaLocation etc.
        ]):
            is_tei = True
    content_type = 'text/plain'
    if is_tei: content_type = 'text/xml+tei'
    elif is_xml: content_type = 'text/xml'
    return {'is_xml': is_xml, 'is_tei': is_tei, 'content_type': content_type}

# ===== TEI Parsing Functions =====
def parse_tei_document(xml_content):
    """Parse a TEI-XML document and prepare it for annotation."""
    try:
        # Using recover=True makes the parser more tolerant of minor errors
        parser = etree.XMLParser(remove_comments=True, remove_pis=True, recover=True)
        root = etree.fromstring(xml_content.encode('utf-8'), parser)
        
        # Build a namespace map, ensuring 'tei' is used for the standard TEI URI if present.
        nsmap_from_ต้น = root.nsmap.copy() # nsmap from the root element
        namespaces = {}
        tei_standard_uri = "http://www.tei-c.org/ns/1.0"
        
        # Check if 'tei' prefix is already correctly defined or if TEI is default
        tei_prefix_found = None
        if nsmap_from_ต้น: # nsmap_from_ต้น might be None for empty or malformed XML
            for prefix, uri in nsmap_from_ต้น.items():
                if uri == tei_standard_uri:
                    namespaces[prefix if prefix else 'tei'] = uri # Use 'tei' for default NS mapping
                    if not prefix: tei_prefix_found = 'tei' # Default NS is TEI
                    else: tei_prefix_found = prefix
                elif prefix: # other prefixes
                    namespaces[prefix] = uri
            
            # If TEI URI was present but not under 'tei' prefix specifically, ensure 'tei' is mapped
            if tei_standard_uri in nsmap_from_ต้น.values() and 'tei' not in namespaces:
                namespaces['tei'] = tei_standard_uri
        
        # Fallback: If no namespaces found on root but we detect TEI content, assume default TEI
        if not namespaces and detect_content_type(xml_content)['is_tei']:
            namespaces['tei'] = tei_standard_uri


        # For backward compatibility: generate namespace-stripped XML string.
        # This is useful if other parts of a system expect this simplified version.
        clean_root_for_legacy_output = strip_namespaces(root)
        clean_xml = etree.tostring(clean_root_for_legacy_output, encoding='unicode')

        # Extract semantic metadata (now uses the potentially more complete `namespaces` map)
        metadata = extract_tei_metadata(root, namespaces)

        # Extract image/facsimile information
        facsimile_data = extract_facsimile_data(root, namespaces)

        # Create display HTML using the original root (with namespaces)
        display_result = create_display_content_ns(root, namespaces)

        return {
            'original_xml': xml_content,
            'clean_xml': clean_xml, 
            'display_html': display_result['display_html'],
            'element_map': display_result['element_map'],
            'tei_metadata': metadata,
            'css': display_result.get('css', ''),
            'facsimile_data': facsimile_data,
            'namespaces': namespaces 
        }
    except Exception as e:
        # Provide more context in the error if possible
        raise ValueError(f"Failed to parse TEI-XML: {str(e)}. Input snippet: {xml_content[:200]}...")

def strip_namespaces(node):
    """
    Deep-copy *node* with all namespaces removed.
    Used for 'clean_xml' output for backward compatibility.
    """
    if not isinstance(node, etree._Element):
        return None # Skip comments, PIs, etc.

    new_tag = _local_name(node.tag)
    new_node = etree.Element(new_tag)

    for k, v in node.attrib.items():
        new_attr_name = _local_name(k)
        new_node.set(new_attr_name, v)

    for child in node: # Recurse on children
        cleaned_child = strip_namespaces(child)
        if cleaned_child is not None:
            new_node.append(cleaned_child)

    new_node.text = node.text
    new_node.tail = node.tail
    return new_node

def extract_tei_metadata(root, namespaces=None):
    """Extract basic metadata from the TEI header, namespace-aware."""
    if namespaces is None: namespaces = {}
    metadata = {
        'title': None, 'author': None, 'publisher': None, 'date': None,
        'source': None, 'language': None, 'msDesc': []
    }
    
    # Determine the prefix for TEI, defaulting to 'tei' if mapped, otherwise try None (for default ns)
    # This assumes 'tei' is the conventional prefix for "http://www.tei-c.org/ns/1.0"
    tei_prefix = next((p for p, u in namespaces.items() if u == "http://www.tei-c.org/ns/1.0"), None)
    if not tei_prefix and namespaces.get("tei") == "http://www.tei-c.org/ns/1.0": # If 'tei' is specifically mapped
        tei_prefix = "tei"
    elif not tei_prefix and namespaces.get(None) == "http://www.tei-c.org/ns/1.0": # If TEI is default ns
        tei_prefix = "tei" # Use 'tei' for constructing XPath internally

    def ns_xpath_query(path_str):
        """Constructs a namespace-prefixed XPath if tei_prefix is known."""
        if not tei_prefix: return path_str # Fallback for non-TEI or unmapped scenarios
        
        # Helper to prefix individual path components if they are element names
        def prefix_part(part):
            if not part or part == '.' or part.startswith('@') or part.startswith('*') or ':' in part:
                return part
            return f"{tei_prefix}:{part}"

        # Handle absolute paths carefully
        if path_str.startswith('/'):
            return '/' + '/'.join(prefix_part(p) for p in path_str.strip('/').split('/'))
        # Handle relative paths (e.g. .// )
        if path_str.startswith('.//'):
            return './/' + '/'.join(prefix_part(p) for p in path_str[3:].split('/'))
        return '/'.join(prefix_part(p) for p in path_str.split('/'))


    # Find teiHeader once
    tei_header = root.find(ns_xpath_query('teiHeader'), namespaces)
    if tei_header is None: return metadata # No header, no metadata

    # Title
    title_stmt = tei_header.find(ns_xpath_query('fileDesc/titleStmt'), namespaces)
    if title_stmt is not None:
        title_el = title_stmt.find(ns_xpath_query('title'), namespaces)
        if title_el is not None and title_el.text: metadata['title'] = title_el.text.strip()
        author_el = title_stmt.find(ns_xpath_query('author'), namespaces)
        if author_el is not None and author_el.text: metadata['author'] = author_el.text.strip()

    # Publisher
    publication_stmt = tei_header.find(ns_xpath_query('fileDesc/publicationStmt'), namespaces)
    if publication_stmt is not None:
        publisher_el = publication_stmt.find(ns_xpath_query('publisher'), namespaces)
        if publisher_el is not None and publisher_el.text: metadata['publisher'] = publisher_el.text.strip()
        date_el = publication_stmt.find(ns_xpath_query('date'), namespaces)
        if date_el is not None:
            if date_el.text: metadata['date'] = date_el.text.strip()
            elif date_el.get('when'): metadata['date'] = date_el.get('when')

    # Source Description (if date not found in publicationStmt)
    source_desc = tei_header.find(ns_xpath_query('fileDesc/sourceDesc'), namespaces)
    if source_desc is not None:
        if not metadata.get('date'): # Try date from sourceDesc if not already set
            date_el_source = source_desc.find(ns_xpath_query('.//date'), namespaces) # .// for deeper search
            if date_el_source is not None:
                if date_el_source.text: metadata['date'] = date_el_source.text.strip()
                elif date_el_source.get('when'): metadata['date'] = date_el_source.get('when')
        metadata['source'] = " ".join(source_desc.xpath('string(.)', namespaces=namespaces).strip().split())


    # Language from profileDesc/langUsage/language
    profile_desc = tei_header.find(ns_xpath_query('profileDesc'), namespaces)
    if profile_desc is not None:
        lang_usage = profile_desc.find(ns_xpath_query('langUsage'), namespaces)
        if lang_usage is not None:
            language_el = lang_usage.find(ns_xpath_query('language'), namespaces)
            if language_el is not None:
                if language_el.text: metadata['language'] = language_el.text.strip()
                elif language_el.get('ident'): metadata['language'] = language_el.get('ident')
    
    # Fallback for language if not in profileDesc (older TEI might have it directly in teiHeader)
    if not metadata.get('language'):
        language_el_fallback = tei_header.find(ns_xpath_query('language'), namespaces=namespaces)
        if language_el_fallback is not None:
            if language_el_fallback.text: metadata['language'] = language_el_fallback.text.strip()
            elif language_el_fallback.get('ident'): metadata['language'] = language_el_fallback.get('ident')


    # msDesc
    if source_desc is not None: # msDesc is usually within sourceDesc
        for ms_desc_el in source_desc.xpath(ns_xpath_query('msDesc'), namespaces=namespaces):
            ms_info = {}
            xml_id_val = ms_desc_el.get('{http://www.w3.org/XML/1998/namespace}id')
            if xml_id_val: ms_info['xml_id'] = xml_id_val
            # Further parsing of msIdentifier, physDesc/handDesc etc. can be added here
            ms_identifier = ms_desc_el.find(ns_xpath_query('msIdentifier/settlement'), namespaces)
            if ms_identifier is not None and ms_identifier.text: ms_info['settlement'] = ms_identifier.text.strip()
            metadata['msDesc'].append(ms_info)
            
    return metadata

def extract_facsimile_data(root, namespaces=None):
    """Extract info about facsimile images (<facsimile>/<surface>/<graphic>), namespace-aware."""
    if namespaces is None: namespaces = {}
    facsimile_data = []
    
    tei_prefix = next((p for p, u in namespaces.items() if u == "http://www.tei-c.org/ns/1.0"), "tei")
    
    # Find all <facsimile> elements using the determined TEI prefix
    for facs_elem in root.xpath(f'.//{tei_prefix}:facsimile', namespaces=namespaces):
        # Find <surface> elements within each <facsimile>
        for surface_elem in facs_elem.xpath(f'./{tei_prefix}:surface', namespaces=namespaces):
            surface_attribs = {_local_name(attr): value for attr, value in surface_elem.attrib.items()}
            # Try to find a <graphic> element within the <surface>
            graphic_elem = surface_elem.find(f'./{tei_prefix}:graphic', namespaces=namespaces)
            if graphic_elem is not None:
                graphic_attribs = {_local_name(attr): value for attr, value in graphic_elem.attrib.items()}
                # Prioritize graphic's URL, fallback to surface's URL
                final_attrs = surface_attribs.copy() # Start with surface attributes
                final_attrs.update(graphic_attribs)   # Override/add with graphic attributes
                if final_attrs.get('url'):
                    facsimile_data.append(final_attrs)
            elif surface_attribs.get('url'): # If no <graphic>, but <surface> has a URL
                facsimile_data.append(surface_attribs)
        # Also check for <graphic> directly under <facsimile> (less common but possible)
        for graphic_direct in facs_elem.xpath(f'./{tei_prefix}:graphic[not(parent::{tei_prefix}:surface)]', namespaces=namespaces):
            graphic_attrs = {_local_name(attr): value for attr, value in graphic_direct.attrib.items()}
            if graphic_attrs.get('url'):
                facsimile_data.append(graphic_attrs)

    return facsimile_data


def create_display_content_ns(root_with_ns, namespaces_map):
    """
    Convert the TEI tree into a "clean" HTML string + element map, using namespace-aware processing.
    (This function was previously named create_display_content in the prompt but adapted for namespaces)
    """
    tei_prefix = next((p for p, u in namespaces_map.items() if u == "http://www.tei-c.org/ns/1.0"), "tei")

    body_element = root_with_ns.find(f'.//{tei_prefix}:body', namespaces_map)
    if body_element is None:
        body_element = root_with_ns.find(f'.//{tei_prefix}:text', namespaces_map)
    
    if body_element is None: # Fallback to the root element if no body or text found
        body_element = root_with_ns 

    processor = TEIProcessor(namespaces=namespaces_map)
    # Start processing from the determined body_element, parent_xpath is initially empty
    result = processor.process_element(body_element, '') 
    
    html_content = ''.join(result['html_parts'])
    
    # Append footnotes if any were collected
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

# Original standalone add_position_predicates (not used by TEIProcessor anymore, could be removed if unused elsewhere)
def add_position_predicates(element, path):
    """
    Original function to add position predicates for non-namespace-aware paths.
    Kept for reference or if other parts of the system might still use it.
    """
    parent = element.getparent()
    if parent is None:
        new_path = f"/{element.tag}" # element.tag would be non-namespaced here
    else:
        index = 1
        for sibling in parent:
            if sibling.tag == element.tag:
                if sibling is element:
                    break
                index += 1
        new_path = path + '/' + f"{element.tag}[{index}]"
    return new_path


# ===== Tokenization for TEI =====
def tokenize_tei_content(display_html):
    """
    Wrap every whitespace‑separated token in <word id="…">…</word>.
    This function operates on the generated HTML output.
    """
    if not isinstance(display_html, str): # Ensure input is a string
        if isinstance(display_html, bytes):
            display_html = display_html.decode('utf-8')
        else: # If it's some other type (like SafeText), try to convert to string
            display_html = str(display_html)

    if not display_html or not display_html.strip():
        return display_html

    try:
        # Use lxml.html.fragments_fromstring to handle potential multiple root elements in the fragment
        # and to avoid lxml adding <html><body> tags if not a full document.
        # We'll process each top-level fragment.
        
        # To handle fragments correctly, we often need a single root for parsing.
        # Let's wrap in a temporary div if it's not a single rooted structure.
        # A simple check: if it doesn't start with < and end with >, or has multiple roots.
        # For simplicity, always wrap for initial parsing, then extract.
        
        temp_wrapper_tag = "div"
        # Ensure display_html is treated as a fragment within the wrapper
        # Using etree.HTML to parse, as it's more robust for potentially malformed HTML.
        # It will add <html> and <body> if they are missing.
        parsed_doc_root = etree.HTML(f"<{temp_wrapper_tag}>{display_html}</{temp_wrapper_tag}>")
        
        # The content we want to process is inside the body, within our wrapper
        content_nodes_to_process = parsed_doc_root.xpath(f'/html/body/{temp_wrapper_tag}')
        if not content_nodes_to_process: # Fallback if structure is different
            content_nodes_to_process = parsed_doc_root.xpath(f'/html/body') # process whole body
            if not content_nodes_to_process:
                 content_nodes_to_process = [parsed_doc_root] # process whatever was parsed

    except Exception as e:
        print(f"Error parsing HTML for tokenization: {str(e)}. Original content returned.")
        return display_html
    
    next_id_counter = 0

    for container_node in content_nodes_to_process:
        # Find relevant text nodes within this container:
        # - text() exists and is not just whitespace
        # - not inside script, style, or an existing word tag
        # - not a descendant of an existing word tag
        for text_parent_node in container_node.xpath('.//*[text()[normalize-space()] and not(self::script or self::style or self::word or ancestor::word)]'):
            text_to_tokenize = text_parent_node.text
            if not text_to_tokenize or not text_to_tokenize.strip():
                continue

            new_content_parts = []
            current_char_pos = 0
            for match in re.finditer(r'\S+', text_to_tokenize):
                # Append whitespace before the current token
                if match.start() > current_char_pos:
                    new_content_parts.append(text_to_tokenize[current_char_pos:match.start()])
                
                # Create and append the <word> element
                word_element = etree.Element('word')
                word_element.set('id', f'tei_{next_id_counter}')
                next_id_counter += 1
                word_element.text = match.group(0)
                new_content_parts.append(word_element)
                current_char_pos = match.end()
            
            # Append any trailing whitespace
            if current_char_pos < len(text_to_tokenize):
                new_content_parts.append(text_to_tokenize[current_char_pos:])
            
            # Replace the original text content of text_parent_node
            text_parent_node.text = None # Clear original text
            
            last_inserted_el = None
            for i, part in enumerate(new_content_parts):
                if isinstance(part, str): # Text node part
                    if last_inserted_el is not None:
                        last_inserted_el.tail = (last_inserted_el.tail or '') + part
                    elif i == 0: # First part is text
                        text_parent_node.text = (text_parent_node.text or '') + part
                    else: # Should not happen if logic is sound (text should follow an element or be first)
                         # This might indicate an edge case or that previous part was also text.
                         # Append to the text of the parent node if it's the first actual content.
                         existing_text = text_parent_node.text if text_parent_node.text else ""
                         text_parent_node.text = existing_text + part
                else: # Element (<word>) part
                    if i == 0 and text_parent_node.text is None: # If word is first and no preceding text for parent
                        # This is complex. We need to insert the element.
                        # If node.text was cleared, and word is first, it must be appended.
                         text_parent_node.insert(0, part) # Insert at the beginning if it's the first child
                    else:
                        text_parent_node.append(part)
                    last_inserted_el = part
    
    # Serialize the content of our original wrapper div(s)
    final_html_parts = []
    for container_node in content_nodes_to_process:
        if container_node.tag.lower() == temp_wrapper_tag :
            if container_node.text: # Text directly in wrapper before first child
                final_html_parts.append(_escape_html(container_node.text))
            for child in container_node:
                final_html_parts.append(etree.tostring(child, encoding='unicode', method='html'))
        else: # Fallback, serialize the container itself (e.g. if it was body)
             final_html_parts.append(etree.tostring(container_node, encoding='unicode', method='html'))


    return "".join(final_html_parts)