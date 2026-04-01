import os
from PIL import Image, ImageDraw, ImageFont

def render_mermaid_sync(mermaid_code, output_file):
    """
    Create visual flowchart diagrams from Mermaid code using PIL.
    Generates proper architectural diagrams as PNG images.
    """
    try:
        # Parse and render Mermaid diagram
        if 'graph TD' in mermaid_code or 'flowchart TD' in mermaid_code:
            return create_flowchart_image(mermaid_code, output_file)
        else:
            return create_diagram_image(mermaid_code, output_file)
    except Exception as e:
        print(f"  Error rendering diagram: {e}")
        return False


def create_flowchart_image(mermaid_code, output_file):
    """
    Create a visual flowchart from Mermaid diagram code.
    Parses the diagram structure and renders it as an image.
    """
    try:
        # Parse mermaid code
        lines = mermaid_code.strip().split('\n')
        nodes = {}
        connections = []
        
        # Extract nodes and connections
        for line in lines:
            line = line.strip()
            if not line or line.startswith('graph') or line.startswith('flowchart'):
                continue
            
            # Parse node definitions: A[Text] or A{Decision}
            if '[' in line or '{' in line:
                parts = line.split('[')  if '[' in line else line.split('{')
                if len(parts) >= 2:
                    node_id = parts[0].strip()
                    node_text = parts[1].split(']')[0] if ']' in parts[1] else parts[1].split('}')[0]
                    nodes[node_id] = {'text': node_text, 'shape': 'rect' if '[' in line else 'diamond'}
            
            # Parse connections: A --> B or A -->|label| B
            if '-->' in line:
                parts = line.split('-->')
                if len(parts) >= 2:
                    from_node = parts[0].strip()
                    to_part = parts[1].strip()
                    # Extract label if present
                    label = ''
                    if '|' in to_part:
                        label = to_part.split('|')[1].split('|')[0]
                        to_node = to_part.split('|')[2].strip()
                    else:
                        to_node = to_part
                    connections.append((from_node, to_node, label))
        
        # Create image
        img_width = 1200
        img_height = 800
        img = Image.new('RGB', (img_width, img_height), color='white')
        draw = ImageDraw.Draw(img)
        
        # Load font
        try:
            title_font = ImageFont.truetype("arial.ttf", 16)
            text_font = ImageFont.truetype("arial.ttf", 12)
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
        
        # Draw title
        diagram_type = "System Architecture" if 'system' in output_file.lower() else "Data Flow Diagram"
        draw.text((20, 20), diagram_type, fill='black', font=title_font)
        
        # Calculate node positions
        node_positions = {}
        num_nodes = len(nodes)
        if num_nodes > 0:
            nodes_per_row = 3
            row_height = 150
            col_width = img_width // (nodes_per_row + 1)
            
            for i, (node_id, node_info) in enumerate(nodes.items()):
                row = i // nodes_per_row
                col = i % nodes_per_row
                x = col_width * (col + 1)
                y = 100 + row * row_height
                node_positions[node_id] = (x, y)
        
        # Draw connections
        for from_id, to_id, label in connections:
            if from_id in node_positions and to_id in node_positions:
                x1, y1 = node_positions[from_id]
                x2, y2 = node_positions[to_id]
                
                # Draw arrow line
                draw.line([(x1 + 60, y1 + 30), (x2 - 60, y2 - 30)], fill='#444', width=2)
                
                # Draw arrowhead
                arrow_size = 10
                angle = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                if angle > 0:
                    angle_rad = ((y2 - y1) / angle, (x2 - x1) / angle)
                    arrow_x = x2 - 60
                    arrow_y = y2 - 30
                    draw.polygon([
                        (arrow_x, arrow_y),
                        (arrow_x - arrow_size, arrow_y - arrow_size),
                        (arrow_x - arrow_size, arrow_y + arrow_size)
                    ], fill='#444')
                
                # Draw label if present
                if label:
                    mid_x = (x1 + x2) // 2
                    mid_y = (y1 + y2) // 2
                    draw.text((mid_x, mid_y), label, fill='#666', font=text_font)
        
        # Draw nodes
        node_width = 120
        node_height = 60
        
        for node_id, (x, y) in node_positions.items():
            node_info = nodes[node_id]
            text = node_info['text'][:30]  # Limit text
            
            # Draw node box
            if node_info['shape'] == 'diamond':
                # Diamond shape for decisions
                points = [
                    (x, y - 25),           # top
                    (x + 60, y),           # right
                    (x, y + 25),           # bottom
                    (x - 60, y)            # left
                ]
                draw.polygon(points, fill='#FFE6E6', outline='#CC0000', width=2)
            else:
                # Rectangle for normal nodes
                draw.rectangle(
                    [x - 60, y - 30, x + 60, y + 30],
                    fill='#E6F2FF',
                    outline='#0066CC',
                    width=2
                )
            
            # Draw text
            text_bbox = draw.textbbox((0, 0), text, font=text_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            draw.text(
                (x - text_width // 2, y - text_height // 2),
                text,
                fill='black',
                font=text_font
            )
        
        img.save(output_file)
        return os.path.exists(output_file) and os.path.getsize(output_file) > 1000
    
    except Exception as e:
        print(f"  Error creating flowchart: {e}")
        return False


def create_diagram_image(mermaid_code, output_file):
    """
    Create a diagram image with the Mermaid code rendered as visual text.
    Fallback when full parsing is not possible.
    """
    try:
        img = Image.new('RGB', (1000, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 11)
            title_font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()
            title_font = ImageFont.load_default()
        
        # Draw title
        diagram_type = "Architecture Diagram"
        draw.text((20, 20), diagram_type, fill='black', font=title_font)
        
        # Draw diagram code with formatting
        y = 80
        for line in mermaid_code.split('\n'):
            if line.strip():
                # Indent code
                indent = len(line) - len(line.lstrip())
                draw.text((20 + indent * 10, y), line.strip(), fill='#333', font=font)
                y += 25
                if y > 550:
                    break
        
        img.save(output_file)
        return os.path.exists(output_file) and os.path.getsize(output_file) > 100
    
    except Exception as e:
        print(f"  Could not create diagram: {e}")
        return False

