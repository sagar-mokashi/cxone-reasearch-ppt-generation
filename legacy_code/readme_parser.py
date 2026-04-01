import os
import re


SECTION_CHAR_LIMIT = 2000
FULL_CONTENT_EXCERPT_LIMIT = 6000

def find_readme(repo_path):
    """Find README file in repository (case-insensitive)"""
    for file in os.listdir(repo_path):
        if file.lower().startswith('readme') and file.lower().endswith(('.md', '.txt', '.rst')):
            return os.path.join(repo_path, file)
    return None


def parse_readme(readme_path):
    """
    Parse README.md and extract meaningful sections for business presentation
    Returns dict with business-relevant content
    """
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading README: {e}")
        return {}
    
    sections = extract_sections(content)
    return sections


def extract_sections(content):
    """
    Extract key sections from README using regex
    Looking for common markdown sections
    """
    sections = {
        'title': '',
        'overview': '',
        'problem': '',
        'solution': '',
        'features': '',
        'benefits': '',
        'architecture': '',
        'usage': '',
        'roadmap': '',
        'limitations': '',
        'installation': '',
        'technologies': '',
        'full_content': content
    }
    
    lines = content.split('\n')
    
    # Extract title (first H1)
    for line in lines:
        if line.strip().startswith('# ') and not line.strip().startswith('## '):
            sections['title'] = line.replace('#', '').strip()
            break
    
    # Extract key sections based on headers
    current_section = None
    current_content = []
    
    for line in lines:
        # Check for headers
        if line.strip().startswith('##'):
            # Save previous section
            if current_section and current_content:
                content_text = '\n'.join(current_content).strip()
                if content_text:
                    sections[current_section] = content_text[:SECTION_CHAR_LIMIT]
            
            header = line.replace('#', '').strip().lower()
            current_content = []
            
            # Map headers to sections
            if any(word in header for word in ['overview', 'about', 'introduction']):
                current_section = 'overview'
            elif any(word in header for word in ['problem', 'challenge', 'issue']):
                current_section = 'problem'
            elif any(word in header for word in ['solution', 'approach', 'design']):
                current_section = 'solution'
            elif any(word in header for word in ['feature', 'capability']):
                current_section = 'features'
            elif any(word in header for word in ['benefit', 'advantage', 'outcome', 'impact']):
                current_section = 'benefits'
            elif any(word in header for word in ['architecture', 'structure', 'design']):
                current_section = 'architecture'
            elif any(word in header for word in ['usage', 'how', 'example']):
                current_section = 'usage'
            elif any(word in header for word in ['roadmap', 'future', 'next', 'phase']):
                current_section = 'roadmap'
            elif any(word in header for word in ['limit', 'constraint', 'known']):
                current_section = 'limitations'
            elif any(word in header for word in ['install', 'setup', 'setup']):
                current_section = 'installation'
            elif any(word in header for word in ['tech', 'stack', 'tool']):
                current_section = 'technologies'
        elif current_section and line.strip() and not line.strip().startswith('#'):
            current_content.append(line)
    
    # Save last section
    if current_section and current_content:
        content_text = '\n'.join(current_content).strip()
        if content_text:
            sections[current_section] = content_text[:SECTION_CHAR_LIMIT]
    
    # If we didn't find specific sections, extract first paragraph as overview
    if not sections['overview']:
        first_content = '\n'.join([l for l in lines if l.strip() and not l.strip().startswith('#')])
        sections['overview'] = first_content[:1000]
    
    return sections


def create_business_summary(sections):
    """
    Create a comprehensive business summary from parsed README sections
    This will be sent to LLM to generate PPT slides
    """
    full_content_excerpt = sections.get('full_content', '')[:FULL_CONTENT_EXCERPT_LIMIT]

    summary = f"""
PROJECT: {sections.get('title', 'Unknown Project')}

OVERVIEW:
{sections.get('overview', 'No overview found')}

PROBLEM STATEMENT:
{sections.get('problem', sections.get('overview', 'See overview'))}

SOLUTION:
{sections.get('solution', 'Solution details not provided')}

KEY FEATURES:
{sections.get('features', 'Features not documented')}

BUSINESS BENEFITS:
{sections.get('benefits', 'Benefits not explicitly stated')}

ARCHITECTURE:
{sections.get('architecture', 'Architecture details not documented')}

CURRENT USAGE:
{sections.get('usage', 'Usage not documented')}

FUTURE ROADMAP:
{sections.get('roadmap', 'No roadmap provided')}

KNOWN LIMITATIONS:
{sections.get('limitations', 'No limitations documented')}

TECHNOLOGIES USED:
{sections.get('technologies', 'Tech stack not specified')}

README EXCERPT:
{full_content_excerpt if full_content_excerpt else 'No README excerpt available'}
"""
    return summary.strip()
