"""
TEI-XML Integration utilities for Vogon.

This module provides functionality to:
1. Detect content type (TEI, XML, plain text)
2. Parse TEI-XML documents with proper namespace handling
3. Convert TEI to clean HTML representation while:
   - Minimizing raw TEI markup
   - Preserving structural layout (paragraphs, line/page breaks, headings, etc.)
   - Providing simpler display of editorial tags (e.g., <choice>, <orig>, <reg>)
4. Maintain XPath references for annotation purposes
"""

from lxml import etree
from django.utils.safestring import mark_safe
import re

# Default TEI namespace URI
TEI_NAMESPACE = "http://www.tei-c.org/ns/1.0"
DEFAULT_NAMESPACE_MAP = {'tei': TEI_NAMESPACE}


def _create_xml_parser():
    """
    Create an XML parser that's tolerant of common TEI issues.
    
    Returns:
        etree.XMLParser: Configured parser with error recovery enabled
    """
    return etree.XMLParser(
        remove_comments=True,
        remove_pis=False,
        recover=True,
        huge_tree=True,
        no_network=True,
        load_dtd=False
    )


def _escape_html(text):
    """
    Escape HTML special characters for safe display.
    
    Args:
        text (str): Text to escape
        
    Returns:
        str: HTML-escaped text
    """
    if not text:
        return ''
    return (text.replace('&', '&amp;')
               .replace('<', '&lt;')
               .replace('>', '&gt;'))


def _extract_text_content(element):
    """
    Extract all text content from an element and its descendants.
    
    Args:
        element: lxml Element or None
        
    Returns:
        str: Concatenated text content, stripped of whitespace
    """
    if element is None:
        return ''
    # itertext() recursively yields all text content
    return ''.join(element.itertext()).strip()


class TEIProcessor:
    """
    Converts TEI XML elements to HTML with proper namespace support.
    
    This processor walks through a TEI document tree and converts each
    element to an appropriate HTML representation while maintaining
    XPath references for annotation purposes.
    """
    
    def __init__(self, namespace_map=None):
        """
        Initialize the TEI processor.
        
        Args:
            namespace_map (dict): Mapping of namespace prefixes to URIs
        """
        self.html_parts = []
        self.element_map = []
        self.namespace_map = namespace_map or DEFAULT_NAMESPACE_MAP
        
        # Prepare namespace context for XPath queries
        self.namespaces = {'tei': self.namespace_map.get('tei', TEI_NAMESPACE)}
        
        # Handle default namespace (None key in namespace map)
        if None in self.namespace_map:
            self.namespaces['tei'] = self.namespace_map[None]
    
    def process_element(self, element, parent_xpath=''):
        """
        Process a TEI element and convert to HTML representation.
        
        Args:
            element: lxml Element to process
            parent_xpath (str): XPath of the parent element
            
        Returns:
            dict: Contains 'html_parts' list and 'element_map' list
        """
        # Get local tag name without namespace
        tag = etree.QName(element).localname
        
        # Build unique XPath for this element
        xpath = self._build_element_xpath(element, parent_xpath)
        
        # Dispatch to appropriate handler method
        handler_method = f"_process_{tag}"
        handler = getattr(self, handler_method, self._process_default)
        
        return handler(element, tag, xpath)
    
    def _build_element_xpath(self, element, parent_xpath):
        """
        Build a unique XPath for the element with position predicates.
        
        Args:
            element: lxml Element
            parent_xpath (str): XPath string of the parent
            
        Returns:
            str: Unique XPath string like "/body[1]/div[2]/p[3]"
        """
        parent = element.getparent()
        if parent is None:
            return f"/{element.tag}[1]"
        
        # Count position among siblings with same tag
        position = 1
        for sibling in parent.iterchildren(element.tag):
            if sibling is element:
                break
            position += 1
        
        # Use local name for cleaner XPath (without namespace)
        local_tag = etree.QName(element).localname
        return f"{parent_xpath}/{local_tag}[{position}]"
    
    def _find_child_element(self, parent_element, child_tag):
        """
        Find child element with namespace support.
        
        Tries to find the child element using registered namespaces,
        falling back to no namespace if needed.
        
        Args:
            parent_element: Parent lxml Element
            child_tag (str): Local name of child element to find
            
        Returns:
            lxml Element or None
        """
        # Try with each registered namespace
        for prefix, uri in self.namespaces.items():
            namespaced_tag = f"{{{uri}}}{child_tag}"
            child = parent_element.find(namespaced_tag)
            if child is not None:
                return child
        
        # Try without namespace as fallback
        return parent_element.find(child_tag)
    
    def _process_text_and_children(self, element, xpath):
        """
        Process text content and child elements recursively.
        
        This handles the common pattern of processing an element's
        text, then its children, then any tail text after each child.
        
        Args:
            element: lxml Element to process
            xpath (str): XPath of the current element
        """
        # Process leading text
        if element.text:
            self.html_parts.append(_escape_html(element.text))
        
        # Process each child element
        for child in element:
            self.process_element(child, xpath)
            # Process tail text that follows the child
            if child.tail:
                self.html_parts.append(_escape_html(child.tail))
    
    # ===== Element-specific handlers =====
    
    def _process_TEI(self, element, tag, xpath):
        """Process TEI root element."""
        self.html_parts.append(f'<div class="tei-document" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'document',
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_body(self, element, tag, xpath):
        """Process body element."""
        self.html_parts.append(f'<div class="tei-body" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'body',
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_text(self, element, tag, xpath):
        """Process text element (main content container)."""
        self.html_parts.append(f'<div class="tei-text" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'text',
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_teiHeader(self, element, tag, xpath):
        """Process TEI header - record but don't display."""
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'header',
            'start_pos': len(''.join(self.html_parts))
        })
        # Skip processing header content for display
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_p(self, element, tag, xpath):
        """Process paragraph elements."""
        self.html_parts.append(f'<p class="tei-p" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'paragraph',
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</p>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_div(self, element, tag, xpath):
        """Process div elements with type attribute."""
        div_type = element.get('type', '')
        type_class = f" tei-div-{div_type}" if div_type else ""
        
        self.html_parts.append(f'<div class="tei-div{type_class}" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'div',
            'div_type': div_type,
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_head(self, element, tag, xpath):
        """Process heading elements."""
        self.html_parts.append(f'<h3 class="tei-head" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'heading',
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</h3>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_lb(self, element, tag, xpath):
        """
        Process line break elements.
        
        Handles both breaking and non-breaking line breaks based on
        the 'break' attribute. Also displays line numbers if present.
        """
        line_number = element.get('n', '')
        is_breaking = element.get('break', 'yes') != 'no'
        
        if not is_breaking:
            # Non-breaking line break (word continuation)
            self.html_parts.append(f'<span class="tei-lb-nobreak" data-xpath="{xpath}"></span>')
        else:
            # Regular line break
            if line_number:
                self.html_parts.append(f'<span class="tei-line-num">{line_number}</span>')
            self.html_parts.append(f'<br class="tei-lb" data-xpath="{xpath}" />')
        
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'linebreak',
            'line_number': line_number,
            'is_breaking': is_breaking,
            'start_pos': len(''.join(self.html_parts))
        })
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_pb(self, element, tag, xpath):
        """Process page break elements with page number and facsimile reference."""
        page_number = element.get('n', '')
        facsimile_ref = element.get('facs', '')
        
        self.html_parts.append(
            f'<div class="tei-pb" data-xpath="{xpath}" '
            f'data-n="{page_number}" data-facs="{facsimile_ref}">'
            f'<hr class="tei-pb-line"/>'
            f'<span class="tei-pb-label">Page {page_number}</span>'
            f'</div>'
        )
        
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'pagebreak',
            'page': page_number,
            'facs': facsimile_ref,
            'start_pos': len(''.join(self.html_parts))
        })
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_hi(self, element, tag, xpath):
        """
        Process highlighted/emphasized text.
        
        Maps TEI rendition values to CSS styles where possible.
        """
        rendition = element.get('rend', '')
        
        # Map common TEI rendition values to CSS
        style_mapping = {
            'italic': 'font-style: italic',
            'bold': 'font-weight: bold',
            'underline': 'text-decoration: underline',
            'overline': 'text-decoration: overline',
            'superscript': 'vertical-align: super; font-size: 0.8em',
            'subscript': 'vertical-align: sub; font-size: 0.8em'
        }
        
        css_style = style_mapping.get(rendition, '')
        style_attr = f' style="{css_style}"' if css_style else ''
        rendition_class = f" tei-hi-{rendition}" if rendition else ""
        
        self.html_parts.append(
            f'<span class="tei-hi{rendition_class}"{style_attr} data-xpath="{xpath}">'
        )
        
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'highlight',
            'rendition': rendition,
            'start_pos': len(''.join(self.html_parts))
        })
        
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</span>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_del(self, element, tag, xpath):
        """Process deleted text using HTML del element."""
        self.html_parts.append(f'<del class="tei-del" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'deletion',
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</del>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_add(self, element, tag, xpath):
        """Process text additions with placement information."""
        place = element.get('place', '')
        hand = element.get('hand', '')
        
        place_class = f" tei-add-{place}" if place else ""
        title = f'Added {place}' if place else 'Added text'
        
        self.html_parts.append(
            f'<span class="tei-add{place_class}" data-xpath="{xpath}" title="{title}">'
        )
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'addition',
            'place': place,
            'hand': hand,
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</span>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_gap(self, element, tag, xpath):
        """
        Process gap elements indicating missing or illegible text.
        
        Shows description if available, otherwise shows [...].
        """
        reason = element.get('reason', '')
        extent = element.get('extent', '')
        unit = element.get('unit', '')
        
        # Look for descriptive content
        desc_element = self._find_child_element(element, 'desc')
        description = _extract_text_content(desc_element) if desc_element is not None else ''
        
        # Build display text and title
        display_text = f'[{description}]' if description else '[...]'
        title_parts = []
        if extent and unit:
            title_parts.append(f"{extent} {unit}")
        if reason:
            title_parts.append(reason)
        title = f"Gap: {' - '.join(title_parts)}" if title_parts else "Gap in text"
        
        self.html_parts.append(
            f'<span class="tei-gap" data-xpath="{xpath}" '
            f'data-reason="{reason}" data-extent="{extent}" '
            f'data-unit="{unit}" title="{_escape_html(title)}">'
            f'{_escape_html(display_text)}</span>'
        )
        
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'gap',
            'reason': reason,
            'extent': extent,
            'unit': unit,
            'description': description,
            'start_pos': len(''.join(self.html_parts))
        })
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_note(self, element, tag, xpath):
        """
        Process note elements (footnotes, marginal notes, etc.).
        
        Footnotes are rendered as superscript references with the
        note content collected for display at the document end.
        """
        place = element.get('place', 'inline')
        note_type = element.get('type', place)
        
        if place == 'foot':
            # Handle footnotes specially
            footnote_count = sum(1 for m in self.element_map if m.get('type') == 'footnote')
            footnote_number = footnote_count + 1
            footnote_id = f"fn-{footnote_number}"
            
            # Add superscript reference
            self.html_parts.append(
                f'<sup id="ref-{footnote_id}" class="tei-fn-ref" data-xpath="{xpath}">'
                f'{footnote_number}</sup>'
            )
            
            # Store footnote content for later rendering
            self.element_map.append({
                'type': 'footnote',
                'text': _extract_text_content(element),
                'id': footnote_id,
                'num': footnote_number,
                'xpath': xpath
            })
        else:
            # Handle inline or marginal notes
            self.html_parts.append(
                f'<span class="tei-note tei-note-{note_type}" '
                f'data-xpath="{xpath}" title="Note ({note_type})">'
            )
            self._process_text_and_children(element, xpath)
            self.html_parts.append('</span>')
            
            self.element_map.append({
                'xpath': xpath,
                'element_type': 'note',
                'note_type': note_type,
                'start_pos': len(''.join(self.html_parts))
            })
        
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_choice(self, element, tag, xpath):
        """
        Process choice elements containing editorial alternatives.
        
        Handles common patterns:
        - orig/reg: shows regularized, tooltip shows original
        - sic/corr: shows correction, tooltip shows error
        - abbr/expan: shows expansion, tooltip shows abbreviation
        """
        # Find child elements for different choice types
        orig = self._find_child_element(element, 'orig')
        reg = self._find_child_element(element, 'reg')
        sic = self._find_child_element(element, 'sic')
        corr = self._find_child_element(element, 'corr')
        abbr = self._find_child_element(element, 'abbr')
        expan = self._find_child_element(element, 'expan')
        
        choice_processed = False
        
        # Handle regularization
        if reg is not None and orig is not None:
            orig_text = _extract_text_content(orig)
            reg_text = _extract_text_content(reg)
            self.html_parts.append(
                f'<span class="tei-choice tei-reg" data-xpath="{xpath}" '
                f'title="Original: {_escape_html(orig_text)}">'
                f'{_escape_html(reg_text)}</span>'
            )
            choice_processed = True
            
        # Handle corrections
        elif corr is not None and sic is not None:
            sic_text = _extract_text_content(sic)
            corr_text = _extract_text_content(corr)
            self.html_parts.append(
                f'<span class="tei-choice tei-corr" data-xpath="{xpath}" '
                f'title="Error: {_escape_html(sic_text)}">'
                f'{_escape_html(corr_text)}</span>'
            )
            choice_processed = True
            
        # Handle abbreviation expansions
        elif expan is not None and abbr is not None:
            abbr_text = _extract_text_content(abbr)
            expan_text = _extract_text_content(expan)
            self.html_parts.append(
                f'<span class="tei-choice tei-expan" data-xpath="{xpath}" '
                f'title="Abbreviation: {_escape_html(abbr_text)}">'
                f'{_escape_html(expan_text)}</span>'
            )
            choice_processed = True
        
        # Fallback for unrecognized choice patterns
        if not choice_processed:
            self.html_parts.append(f'<span class="tei-choice" data-xpath="{xpath}">')
            self._process_text_and_children(element, xpath)
            self.html_parts.append('</span>')
        
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'choice',
            'start_pos': len(''.join(self.html_parts))
        })
        
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_milestone(self, element, tag, xpath):
        """
        Process milestone elements (structural markers).
        
        Milestones can contain text or be empty markers.
        """
        milestone_number = element.get('n', '')
        milestone_type = element.get('type', element.get('unit', ''))
        
        # Check if milestone contains text content
        text_content = _extract_text_content(element)
        
        type_class = f" tei-milestone-{milestone_type}" if milestone_type else ""
        
        if text_content:
            # Milestone with content
            self.html_parts.append(
                f'<span class="tei-milestone{type_class}" '
                f'data-xpath="{xpath}" data-n="{milestone_number}">'
                f'{_escape_html(text_content)}</span>'
            )
        else:
            # Empty milestone marker
            title = f"Milestone {milestone_number}" if milestone_number else "Milestone"
            self.html_parts.append(
                f'<span class="tei-milestone{type_class}" '
                f'data-xpath="{xpath}" data-n="{milestone_number}" '
                f'title="{title}"></span>'
            )
        
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'milestone',
            'milestone_type': milestone_type,
            'n': milestone_number,
            'start_pos': len(''.join(self.html_parts))
        })
        
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_lg(self, element, tag, xpath):
        """Process line group (verse/poetry container)."""
        self.html_parts.append(f'<div class="tei-lg" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'line_group',
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_l(self, element, tag, xpath):
        """Process verse line with optional line number."""
        line_number = element.get('n', '')
        
        self.html_parts.append(f'<div class="tei-l" data-xpath="{xpath}">')
        
        # Display line number if present
        if line_number:
            self.html_parts.append(f'<span class="tei-line-number">{line_number}</span>')
        
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'verse_line',
            'line_number': line_number,
            'start_pos': len(''.join(self.html_parts))
        })
        
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</div>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_list(self, element, tag, xpath):
        """Process list elements as ordered or unordered HTML lists."""
        list_type = element.get('type', '')
        # Use ordered list for numbered/ordered types
        html_tag = 'ol' if list_type in ['ordered', 'numbered'] else 'ul'
        
        self.html_parts.append(f'<{html_tag} class="tei-list" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'list',
            'list_type': list_type,
            'start_pos': len(''.join(self.html_parts))
        })
        
        # Process children (typically <item> elements)
        for child in element:
            self.process_element(child, xpath)
            
        self.html_parts.append(f'</{html_tag}>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_item(self, element, tag, xpath):
        """Process list item."""
        self.html_parts.append(f'<li class="tei-item" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': 'item',
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</li>')
        return {'html_parts': self.html_parts, 'element_map': self.element_map}
    
    def _process_default(self, element, tag, xpath):
        """
        Default handler for TEI elements not explicitly handled.
        
        Some elements are skipped (like header elements), others
        are wrapped in a generic span with their tag as a class.
        """
        # Elements to skip in display output
        skip_elements = {
            'teiHeader', 'fileDesc', 'titleStmt', 'publicationStmt',
            'sourceDesc', 'encodingDesc', 'profileDesc', 'revisionDesc',
            'facsimile', 'surface', 'graphic', 'handDesc', 'handNote',
            'physDesc', 'msDesc', 'msIdentifier', 'repository',
            'settlement', 'country', 'institution', 'collection', 'idno'
        }
        
        if tag in skip_elements:
            # Record in element map but don't add to HTML
            self.element_map.append({
                'xpath': xpath,
                'element_type': tag,
                'start_pos': len(''.join(self.html_parts))
            })
            return {'html_parts': self.html_parts, 'element_map': self.element_map}
        
        # For other elements, wrap in span with appropriate class
        self.html_parts.append(f'<span class="tei-{tag}" data-xpath="{xpath}">')
        self.element_map.append({
            'xpath': xpath,
            'element_type': tag,
            'start_pos': len(''.join(self.html_parts))
        })
        self._process_text_and_children(element, xpath)
        self.html_parts.append('</span>')
        
        return {'html_parts': self.html_parts, 'element_map': self.element_map}


# ===== Main Functions =====

def detect_content_type(text_content: str) -> dict:
    """
    Detect if content is XML and/or TEI.
    
    Args:
        text_content: The text to analyze
        
    Returns:
        dict: Contains 'is_xml', 'is_tei', and 'content_type' keys
    """
    stripped = text_content.lstrip()
    is_xml = stripped.startswith('<?xml') or stripped.startswith('<')
    is_tei = False
    
    if is_xml:
        # Check for TEI markers
        tei_markers = [
            '<TEI', '<tei', 'xmlns="http://www.tei-c.org',
            'xmlns:tei', 'tei-c.org/ns/1.0'
        ]
        is_tei = any(marker in text_content for marker in tei_markers)
    
    return {
        'is_xml': is_xml,
        'is_tei': is_tei,
        'content_type': 'text/xml+tei' if is_tei else 'text/xml' if is_xml else 'text/plain'
    }


def parse_tei_document(xml_content: str) -> dict:
    """
    Parse TEI-XML document with proper namespace handling.
    
    Args:
        xml_content: TEI-XML content as string
        
    Returns:
        dict: Parsed document with keys:
            - original_xml: The input XML
            - clean_xml: Currently same as original (for compatibility)
            - display_html: HTML representation for display
            - element_map: Mapping of elements to positions
            - tei_metadata: Extracted metadata
            - css: Empty string (placeholder)
            - facsimile_data: List of facsimile information
            - namespaces: Detected namespace mappings
            
    Raises:
        ValueError: If XML parsing fails
    """
    parser = _create_xml_parser()
    
    try:
        root = etree.fromstring(xml_content.encode('utf-8'), parser)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"XML syntax error at line {e.lineno}: {e.msg}")
    
    # Extract namespace map from root element
    namespace_map = root.nsmap.copy() if root.nsmap else {}
    
    # Find the TEI namespace
    tei_namespace_uri = None
    for prefix, uri in namespace_map.items():
        if 'tei-c.org' in uri:
            tei_namespace_uri = uri
            break
    
    # If root is TEI but no namespace declared, assume default
    if not tei_namespace_uri and etree.QName(root).localname in ['TEI', 'tei']:
        tei_namespace_uri = TEI_NAMESPACE
        namespace_map[None] = TEI_NAMESPACE
    
    # Create processor with detected namespaces
    processor = TEIProcessor(namespace_map)
    
    # Find main content element (body or text)
    content_element = _find_content_element(root, namespace_map)
    
    # Process the content tree
    result = processor.process_element(content_element)
    
    # Build final HTML with footnotes if present
    html_content = _build_final_html(result)
    
    # Extract metadata and facsimile data
    metadata = extract_tei_metadata(root, namespace_map)
    facsimile_data = extract_facsimile_data(root, namespace_map)
    
    return {
        'original_xml': xml_content,
        'clean_xml': xml_content,  # Kept for backward compatibility
        'display_html': mark_safe(html_content),
        'element_map': result['element_map'],
        'tei_metadata': metadata,
        'css': '',  # Placeholder for custom CSS
        'facsimile_data': facsimile_data,
        'namespaces': namespace_map
    }


def _find_content_element(root, namespace_map):
    """
    Find the main content element (body or text) in the TEI document.
    
    Args:
        root: Root element of the document
        namespace_map: Namespace mappings
        
    Returns:
        lxml Element: The content element, or root if not found
    """
    # Prepare namespace prefixes for searching
    possible_prefixes = [None, 'tei', '']
    
    for prefix in possible_prefixes:
        if prefix is None and None in namespace_map:
            ns = namespace_map[None]
        elif prefix in namespace_map:
            ns = namespace_map[prefix]
        else:
            ns = TEI_NAMESPACE
        
        # Try to find body or text elements
        for element_name in ['body', 'text']:
            # Try with namespace
            path = f'.//{{{ns}}}{element_name}'
            element = root.find(path)
            if element is not None:
                return element
            
            # Try without namespace
            element = root.find(f'.//{element_name}')
            if element is not None:
                return element
    
    # Fallback to root if no body/text found
    return root


def _build_final_html(processing_result):
    """
    Build final HTML including footnotes section if needed.
    
    Args:
        processing_result: Result from TEIProcessor
        
    Returns:
        str: Complete HTML content
    """
    html_content = ''.join(processing_result['html_parts'])
    
    # Extract and append footnotes if any
    footnotes = [m for m in processing_result['element_map'] if m.get('type') == 'footnote']
    
    if footnotes:
        html_content += '<hr class="tei-fn-rule"/>\n<ol class="tei-footnotes">'
        
        for footnote in sorted(footnotes, key=lambda x: x.get('num', 0)):
            footnote_id = footnote['id']
            footnote_num = footnote.get('num', '*')
            footnote_text = _escape_html(footnote['text'])
            
            html_content += (
                f'\n<li id="{footnote_id}" class="tei-footnote" value="{footnote_num}">'
                f'<a href="#ref-{footnote_id}">{footnote_num}</a>. '
                f'{footnote_text}</li>'
            )
        
        html_content += '\n</ol>'
    
    return html_content


def extract_tei_metadata(root, namespace_map=None):
    """
    Extract metadata from TEI header using namespace-aware XPath.
    
    Args:
        root: Root element of TEI document
        namespace_map: Namespace mappings
        
    Returns:
        dict: Extracted metadata fields
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
    
    # Prepare namespace context for XPath
    xpath_namespaces = _prepare_xpath_namespaces(namespace_map)
    
    # Helper to find elements with multiple path variations
    def find_element(paths):
        for path in paths:
            try:
                elements = root.xpath(path, namespaces=xpath_namespaces)
                if elements:
                    return elements[0]
            except:
                # Try without namespace prefix
                try:
                    elements = root.xpath(path.replace('tei:', ''))
                    if elements:
                        return elements[0]
                except:
                    pass
        return None
    
    # Extract each metadata field
    title_element = find_element([
        './/tei:titleStmt/tei:title',
        './/titleStmt/title'
    ])
    if title_element is not None and title_element.text:
        metadata['title'] = title_element.text.strip()
    
    author_element = find_element([
        './/tei:titleStmt/tei:author',
        './/titleStmt/author'
    ])
    if author_element is not None and author_element.text:
        metadata['author'] = author_element.text.strip()
    
    publisher_element = find_element([
        './/tei:publicationStmt/tei:publisher',
        './/publicationStmt/publisher'
    ])
    if publisher_element is not None and publisher_element.text:
        metadata['publisher'] = publisher_element.text.strip()
    
    date_element = find_element([
        './/tei:publicationStmt/tei:date',
        './/publicationStmt/date',
        './/tei:sourceDesc//tei:date',
        './/sourceDesc//date'
    ])
    if date_element is not None:
        metadata['date'] = date_element.text.strip() if date_element.text else date_element.get('when', '')
    
    source_element = find_element([
        './/tei:sourceDesc',
        './/sourceDesc'
    ])
    if source_element is not None:
        metadata['source'] = _extract_text_content(source_element)
    
    return metadata


def extract_facsimile_data(root, namespace_map=None):
    """
    Extract facsimile/graphic information from TEI document.
    
    Args:
        root: Root element of TEI document
        namespace_map: Namespace mappings
        
    Returns:
        list: List of dicts containing facsimile data
    """
    facsimile_data = []
    
    # Prepare namespace context
    xpath_namespaces = _prepare_xpath_namespaces(namespace_map)
    
    try:
        # Try namespace-aware search first
        graphics = root.xpath('.//tei:facsimile//tei:graphic', namespaces=xpath_namespaces)
        if not graphics:
            # Fallback to no namespace
            graphics = root.xpath('.//facsimile//graphic')
        
        for graphic in graphics:
            graphic_data = {}
            for attr_name, attr_value in graphic.attrib.items():
                # Remove namespace from attribute name if present
                clean_attr_name = attr_name.split('}')[-1] if '}' in attr_name else attr_name
                graphic_data[clean_attr_name] = attr_value
            
            if graphic_data:
                facsimile_data.append(graphic_data)
    except:
        # Silently ignore XPath errors
        pass
    
    return facsimile_data


def _prepare_xpath_namespaces(namespace_map):
    """
    Prepare namespace context for XPath queries.
    
    Args:
        namespace_map: Original namespace mappings
        
    Returns:
        dict: Namespace mappings suitable for XPath
    """
    xpath_ns = {}
    
    if namespace_map:
        # Handle default namespace
        if None in namespace_map:
            xpath_ns['tei'] = namespace_map[None]
        elif 'tei' in namespace_map:
            xpath_ns['tei'] = namespace_map['tei']
        else:
            # Find TEI namespace with different prefix
            for prefix, uri in namespace_map.items():
                if 'tei-c.org' in uri:
                    xpath_ns['tei'] = uri
                    break
    
    # Ensure we have TEI namespace
    if 'tei' not in xpath_ns:
        xpath_ns['tei'] = TEI_NAMESPACE
    
    return xpath_ns


def tokenize_tei_content(display_html):
    """
    Tokenize displayed HTML content for word-level annotation.
    
    Wraps each word in a <word> element with unique ID.
    
    Args:
        display_html: HTML string to tokenize
        
    Returns:
        str: Tokenized HTML with word elements
    """
    if not isinstance(display_html, str):
        display_html = str(display_html)
    
    if not display_html.strip():
        return display_html
    
    try:
        # Parse HTML into element tree
        parser = etree.HTMLParser()
        doc = etree.HTML(f'<div>{display_html}</div>', parser)
        if doc is None:
            return display_html
        
        # Find root div
        root = doc.find('.//div')
        if root is None:
            root = doc
        
        # Process all text-containing elements
        word_counter = 0
        
        for element in root.xpath('.//*[text()]'):
            # Skip if already tokenized or in excluded elements
            if element.tag in ['script', 'style', 'word'] or element.xpath('ancestor::word'):
                continue
            
            # Process element's text content
            if element.text and element.text.strip():
                tokenized_content = _tokenize_text(element.text, word_counter)
                word_counter = tokenized_content['next_id']
                
                # Replace element's text with tokenized version
                element.text = None
                for i, item in enumerate(tokenized_content['tokens']):
                    if isinstance(item, str):
                        if i == 0:
                            element.text = item
                        else:
                            # Add as tail of previous word element
                            if i > 0 and isinstance(tokenized_content['tokens'][i-1], etree._Element):
                                tokenized_content['tokens'][i-1].tail = item
                    else:
                        element.insert(i, item)
        
        # Convert back to HTML string
        html_string = etree.tostring(root, encoding='unicode', method='html')
        
        # Remove wrapper div tags
        html_string = html_string.replace('<div>', '', 1)
        html_string = html_string.rsplit('</div>', 1)[0]
        
        return html_string
        
    except Exception as e:
        print(f"Tokenization error: {e}")
        return display_html


def _tokenize_text(text, start_id):
    """
    Tokenize a text string into words and whitespace.
    
    Args:
        text: Text to tokenize
        start_id: Starting ID for word elements
        
    Returns:
        dict: Contains 'tokens' list and 'next_id' counter
    """
    tokens = []
    current_id = start_id
    
    # Find all words using regex
    last_end = 0
    for match in re.finditer(r'\S+', text):
        # Add whitespace before word if any
        if match.start() > last_end:
            tokens.append(text[last_end:match.start()])
        
        # Create word element
        word_element = etree.Element('word')
        word_element.set('id', f'tei_{current_id}')
        word_element.text = match.group()
        tokens.append(word_element)
        current_id += 1
        
        last_end = match.end()
    
    # Add trailing whitespace if any
    if last_end < len(text):
        tokens.append(text[last_end:])
    
    return {
        'tokens': tokens,
        'next_id': current_id
    }