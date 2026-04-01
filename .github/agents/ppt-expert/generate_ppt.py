from pptx import Presentation
from pptx.util import Inches
from pptx.util import Pt
from pptx.enum.text import PP_ALIGN
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
import os
from datetime import datetime


SLIDE_BG = RGBColor(255, 255, 255)
TITLE_BG = RGBColor(15, 23, 42)
TITLE_COLOR = RGBColor(255, 255, 255)
BODY_COLOR = RGBColor(31, 41, 55)
ACCENT = RGBColor(59, 130, 246)
MAX_POINTS_PER_SLIDE = 8
MAX_POINT_LENGTH = 250


def inspect_template(template_path):
    """
    Helper function to inspect available layouts in a PowerPoint template.
    Useful for understanding what layouts are available before using them.
    
    Usage:
        inspect_template("templates/corporate_template.pptx")
    
    Output:
        Layout 0: Title Slide
        Layout 1: Title and Content
        Layout 2: Section Header
        Layout 3: Two Content
        Layout 4: Comparison
        Layout 5: Title Only
        Layout 6: Blank
        ...
    """
    if not os.path.exists(template_path):
        print(f"Template not found: {template_path}")
        return
    
    prs = Presentation(template_path)
    print(f"\n{'='*60}")
    print(f"Template: {template_path}")
    print(f"Slide dimensions: {prs.slide_width / 914400:.2f}\" x {prs.slide_height / 914400:.2f}\"")
    print(f"{'='*60}")
    print(f"\nAvailable Layouts ({len(prs.slide_layouts)} total):\n")
    
    for idx, layout in enumerate(prs.slide_layouts):
        print(f"  Layout {idx}: {layout.name}")
        print(f"    - Placeholders: {len(layout.placeholders)}")
        if layout.placeholders:
            for ph in layout.placeholders:
                print(f"      • {ph.name} (type: {ph.placeholder_format.type})")
    
    print(f"\n{'='*60}\n")


def _add_content_to_template_slide(slide, slide_data):
    """
    Add content to a template slide by extracting placeholder info, removing placeholders,
    and creating regular text boxes with the content.
    
    Args:
        slide: PowerPoint slide object
        slide_data: Dictionary with 'title' and 'points'
    
    Returns:
        True if content was added successfully, False otherwise
    """
    title = slide_data.get("title", "Untitled")
    points = slide_data.get("points", [])
    
    # Check if slide has placeholders
    if not slide.shapes.placeholders:
        return False
    
    # Find placeholders and extract their properties
    title_info = None
    content_info = None
    
    for shape in slide.shapes.placeholders:
        # Title placeholder (type 0 or 1)
        if shape.placeholder_format.type in (0, 1):
            title_info = {
                'left': shape.left,
                'top': shape.top,
                'width': shape.width,
                'height': shape.height,
            }
            # Try to get text formatting
            if shape.has_text_frame and shape.text_frame.paragraphs:
                p = shape.text_frame.paragraphs[0]
                if p.runs:
                    title_info['font_size'] = p.runs[0].font.size
                    title_info['font_bold'] = p.runs[0].font.bold
        # Content/Body placeholder (type 2 or 7)
        elif shape.placeholder_format.type in (2, 7):
            content_info = {
                'left': shape.left,
                'top': shape.top,
                'width': shape.width,
                'height': shape.height,
            }
            # Try to get text formatting
            if shape.has_text_frame and shape.text_frame.paragraphs:
                p = shape.text_frame.paragraphs[0]
                if p.runs:
                    content_info['font_size'] = p.runs[0].font.size
    
    # Must have at least title placeholder info
    if not title_info:
        return False
    
    # Remove ALL placeholders
    placeholders_removed = 0
    for shape in list(slide.shapes):
        if shape.is_placeholder:
            try:
                sp = shape.element
                sp.getparent().remove(sp)
                placeholders_removed += 1
            except Exception as e:
                print(f"  [ppt_gen] Warning: Could not remove placeholder: {e}")
    
    print(f"  [ppt_gen] Removed {placeholders_removed} placeholders, adding custom content")
    
    # Add title as a regular text box
    title_box = slide.shapes.add_textbox(
        title_info['left'],
        title_info['top'],
        title_info['width'],
        title_info['height']
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    
    if title_info.get('font_size'):
        p.font.size = title_info['font_size']
    else:
        p.font.size = Pt(28)
    
    if title_info.get('font_bold') is not None:
        p.font.bold = title_info['font_bold']
    else:
        p.font.bold = True
    
    # Add content as a regular text box if we have content placeholder info
    if content_info and points:
        content_box = slide.shapes.add_textbox(
            content_info['left'],
            content_info['top'],
            content_info['width'],
            content_info['height']
        )
        tf = content_box.text_frame
        tf.word_wrap = True
        
        # Limit points
        trimmed_points = []
        for point in points[:MAX_POINTS_PER_SLIDE]:
            text = str(point).strip()
            if len(text) > MAX_POINT_LENGTH:
                text = text[:MAX_POINT_LENGTH - 1].rstrip() + "…"
            trimmed_points.append(text)
        
        # Add points as bullet list
        if trimmed_points:
            p = tf.paragraphs[0]
            p.text = f"• {trimmed_points[0]}"
            p.level = 0
            
            if content_info.get('font_size'):
                p.font.size = content_info['font_size']
            else:
                p.font.size = Pt(16)
            
            for point_text in trimmed_points[1:]:
                p = tf.add_paragraph()
                p.text = f"• {point_text}"
                p.level = 0
                if content_info.get('font_size'):
                    p.font.size = content_info['font_size']
                else:
                    p.font.size = Pt(16)
    
    return True


def apply_slide_background(slide):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = SLIDE_BG


def add_styled_title(slide, title):
    title_box = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.06),
        Inches(0.06),
        Inches(13.20),
        Inches(0.86),
    )
    title_box.fill.solid()
    title_box.fill.fore_color.rgb = TITLE_BG
    title_box.line.fill.background()

    tf = title_box.text_frame
    tf.clear()
    tf.margin_bottom = Inches(0.06)
    tf.margin_left = Inches(0.35)
    tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.06)
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    
    p = tf.paragraphs[0]
    p.text = title
    p.alignment = PP_ALIGN.LEFT
    p.font.bold = True
    p.font.size = Pt(26)
    p.font.color.rgb = TITLE_COLOR


def add_body_points(slide, points):
    body_box = slide.shapes.add_textbox(
        Inches(0.7),
        Inches(1.2),
        Inches(11.9),
        Inches(5.7),
    )
    tf = body_box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.05)
    tf.margin_right = Inches(0.05)
    tf.margin_top = Inches(0.05)
    tf.margin_bottom = Inches(0.05)
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

    if not points:
        return tf

    trimmed_points = []
    for point in points[:MAX_POINTS_PER_SLIDE]:
        text = str(point).strip()
        if len(text) > MAX_POINT_LENGTH:
            text = text[: MAX_POINT_LENGTH - 1].rstrip() + "…"
        trimmed_points.append(text)

    tf.text = f"• {trimmed_points[0]}"
    for point in trimmed_points[1:]:
        paragraph = tf.add_paragraph()
        paragraph.text = f"• {point}"

    return tf


def style_body_text_frame(text_frame):
    for paragraph in text_frame.paragraphs:
        paragraph.level = 0
        paragraph.font.size = Pt(15)
        paragraph.font.color.rgb = BODY_COLOR
        paragraph.font.bold = False
        paragraph.space_after = Pt(8)


def add_accent_bar(slide):
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.06),
        Inches(7.20),
        Inches(13.20),
        Inches(0.20),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()


def add_title_slide(prs, project_title="Project Presentation", use_template=False):
    """
    Add a professional title slide at the beginning.
    If using a template, fills template placeholders and preserves template design.
    If not using a template, creates custom styled title slide.
    """
    try:
        layout = prs.slide_layouts[0]  # Title Slide layout
    except IndexError:
        layout = prs.slide_layouts[0]
    
    slide = prs.slides.add_slide(layout)
    
    if use_template:
        # Template mode: fill placeholders and preserve template design
        title_placeholder = None
        subtitle_placeholder = None
        
        # Find title and subtitle/body placeholders
        # TITLE types: 1=TITLE, 3=CENTER_TITLE
        # BODY types: 2=BODY, 4=SUBTITLE, 7=OBJECT
        for placeholder in slide.placeholders:
            try:
                p_type = int(placeholder.placeholder_format.type)
                if p_type in (1, 3) and title_placeholder is None and placeholder.has_text_frame:
                    title_placeholder = placeholder
                elif p_type in (2, 4, 7) and subtitle_placeholder is None and placeholder.has_text_frame:
                    subtitle_placeholder = placeholder
            except Exception:
                continue
        
        # Fill title placeholder if found
        if title_placeholder:
            title_tf = title_placeholder.text_frame
            title_tf.clear()
            p = title_tf.paragraphs[0]
            p.text = project_title
            p.font.size = Pt(36)
            p.font.bold = True
        
        # Fill subtitle/body with date if found
        if subtitle_placeholder:
            subtitle_tf = subtitle_placeholder.text_frame
            subtitle_tf.clear()
            p = subtitle_tf.paragraphs[0]
            p.text = f"Date: {datetime.now().strftime('%B %d, %Y')}"
            p.font.size = Pt(18)
            p.font.bold = False
        
        # Remove only unused placeholders to preserve template design
        for shape in list(slide.shapes):
            if shape.is_placeholder:
                try:
                    if shape not in [title_placeholder, subtitle_placeholder]:
                        sp = shape.element
                        sp.getparent().remove(sp)
                except Exception:
                    pass
    else:
        # No template: use custom styled approach with white background
        apply_slide_background(slide)
        
        # Remove all placeholders
        for shape in list(slide.shapes):
            if shape.is_placeholder:
                try:
                    sp = shape.element
                    sp.getparent().remove(sp)
                except Exception:
                    pass

        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5),
            Inches(2.5),
            Inches(12.333),
            Inches(1.5),
        )
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = project_title
        p.alignment = PP_ALIGN.CENTER
        p.font.size = Pt(54)
        p.font.bold = True
        p.font.color.rgb = TITLE_BG

        # Date
        date_box = slide.shapes.add_textbox(
            Inches(0.5),
            Inches(4.3),
            Inches(12.333),
            Inches(0.8),
        )
        tf = date_box.text_frame
        p = tf.paragraphs[0]
        p.text = f"Date: {datetime.now().strftime('%B %d, %Y')}"
        p.alignment = PP_ALIGN.CENTER
        p.font.size = Pt(20)
        p.font.color.rgb = BODY_COLOR

        # Organization/Name
        org_box = slide.shapes.add_textbox(
            Inches(0.5),
            Inches(5.5),
            Inches(12.333),
            Inches(0.8),
        )
        tf = org_box.text_frame
        p = tf.paragraphs[0]
        # p.text = "NICE Ltd"
        p.alignment = PP_ALIGN.CENTER
        p.font.size = Pt(18)
        p.font.color.rgb = ACCENT

        # Add accent bar
        add_accent_bar(slide)


def add_thank_you_slide(prs, thank_you_path=None):
    """
    Add a thank-you slide at the end using the 'Thank You black' layout
    from the main template (layout 35). Falls back to a plain slide if not found.
    """
    # Find 'Thank You black' layout in the current presentation
    thank_you_layout = None
    for layout in prs.slide_layouts:
        if 'thank you' in layout.name.lower():
            thank_you_layout = layout
            break

    if thank_you_layout is not None:
        slide = prs.slides.add_slide(thank_you_layout)
        # Remove any leftover placeholders so they don't show as empty boxes
        for shape in list(slide.shapes):
            if shape.is_placeholder:
                try:
                    shape.element.getparent().remove(shape.element)
                except Exception:
                    pass
        print(f"  [ppt_gen] ✓ Added thank-you slide using layout: {thank_you_layout.name}")
        return

    # Fallback: plain Thank You slide
    try:
        layout = prs.slide_layouts[6]
    except IndexError:
        layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(layout)
    apply_slide_background(slide)
    for shape in list(slide.shapes):
        if shape.is_placeholder:
            try:
                shape.element.getparent().remove(shape.element)
            except Exception:
                pass
    thank_you_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(12.333), Inches(2))
    tf = thank_you_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Thank You"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(54)
    p.font.bold = True
    p.font.color.rgb = TITLE_BG


def create_ppt(slides, diagram_files=None, output_file="project_presentation.pptx", template_file=None, project_title="Project Presentation"):
    """
    Create a PowerPoint presentation from slides data.
    
    Args:
        slides: List of slide dictionaries with 'title' and 'points'
        diagram_files: Optional list of diagram image paths to embed
        output_file: Output filename for the presentation
        template_file: Optional path to .pptx template file (e.g., 'template.pptx')
        project_title: Title shown on the dedicated title slide
    """
    if not slides:
        print("No slides to create")
        return False

    # Load template if provided, otherwise create blank presentation
    use_template = False
    if template_file and os.path.exists(template_file):
        print(f"  [ppt_gen] Loading template: {template_file}")
        prs = Presentation(template_file)
        use_template = True
        # Remove any pre-existing slides baked into the template file
        # so they don't appear as extra blank slides before our content
        slide_ids = list(prs.slides._sldIdLst)
        for sldId in slide_ids:
            prs.part.drop_rel(sldId.rId)
            prs.slides._sldIdLst.remove(sldId)
        # Template already has dimensions, don't override
    else:
        if template_file:
            print(f"  [ppt_gen] ⚠ Template not found: {template_file}, using default")
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

    # Add dedicated title slide at the very beginning
    add_title_slide(prs, project_title, use_template)

    # Create text slides
    for idx, slide in enumerate(slides):
        # For templates, try to use content layout; otherwise use blank
        if use_template:
            # All content slides use Title and Content layout (1)
            if len(prs.slide_layouts) > 1:
                layout = prs.slide_layouts[1]  # Title and Content
                print(f"  [ppt_gen] Slide {idx+1}: Using template layout 1 (Title and Content)")
            else:
                # Fallback to first available layout
                layout = prs.slide_layouts[0]
                print(f"  [ppt_gen] Slide {idx+1}: Using template layout 0 (fallback)")
            
            slide_obj = prs.slides.add_slide(layout)
            
            # Try to use template placeholders
            if _add_content_to_template_slide(slide_obj, slide):
                print(f"  [ppt_gen] ✓ Content added via template placeholders")
                continue
            else:
                # Placeholders not matched; using custom styling
                for shape in list(slide_obj.shapes):
                    if shape.is_placeholder:
                        try:
                            sp = shape.element
                            sp.getparent().remove(sp)
                        except Exception:
                            pass
                # Fall through to custom styling below
        else:
            # No template: use blank layout with custom styling
            try:
                layout = prs.slide_layouts[6]  # Blank layout
            except IndexError:
                layout = prs.slide_layouts[0]
                print(f"  [ppt_gen] Layout 6 not found, using layout 0")
            
            slide_obj = prs.slides.add_slide(layout)
            
            # Remove all placeholders to avoid "Click to edit" boxes
            for shape in list(slide_obj.shapes):
                if shape.is_placeholder:
                    sp = shape.element
                    sp.getparent().remove(sp)
        
        # Custom styling (for non-template or when placeholders unavailable)
        apply_slide_background(slide_obj)
        add_styled_title(slide_obj, slide.get("title", "Untitled"))

        points = slide.get("points", [])
        if not points:
            continue

        tf = add_body_points(slide_obj, points)
        style_body_text_frame(tf)

    # Add diagram slides if available
    if diagram_files:
        for diagram_file in diagram_files:
            if os.path.exists(diagram_file):
                add_diagram_slide(prs, diagram_file)

    # Add thank-you slide at the end using the template's built-in layout
    add_thank_you_slide(prs)

    try:
        prs.save(output_file)
        print(f"Presentation saved as {output_file}")
        return True
    except PermissionError:
        alt_output = output_file.replace('.pptx', '_new.pptx')
        prs.save(alt_output)
        print(f"Target file was open. Presentation saved as {alt_output}")
        return True


def add_diagram_slide(prs, diagram_file):
    """
    Add a slide with an embedded diagram image
    """
    # Only process image files
    if not (diagram_file.endswith('.png') or diagram_file.endswith('.jpg') or diagram_file.endswith('.jpeg')):
        print(f"  Skipping non-image file: {diagram_file}")
        return
    
    # Use blank layout for diagram
    blank_layout = prs.slide_layouts[6]  # Blank slide
    slide = prs.slides.add_slide(blank_layout)

    # Remove any leftover "Click to add title" placeholders from the layout
    for shape in list(slide.shapes):
        if shape.is_placeholder:
            try:
                shape.element.getparent().remove(shape.element)
            except Exception:
                pass

    apply_slide_background(slide)
    
    # Determine title from filename
    if 'system' in diagram_file.lower():
        title = "System Architecture Diagram"
    elif 'dataflow' in diagram_file.lower() or 'data_flow' in diagram_file.lower():
        title = "Data Flow Diagram"
    else:
        title = "Architecture Diagram"

    add_styled_title(slide, title)
    
    # Add diagram image
    try:
        # Calculate position to center the image
        left = Inches(0.8)
        top = Inches(1.35)
        height = Inches(5.7)
        
        slide.shapes.add_picture(diagram_file, left, top, height=height)
        print(f"  ✓ Embedded diagram: {diagram_file}")
    except Exception as e:
        print(f"  Warning: Could not add diagram {diagram_file}: {e}")