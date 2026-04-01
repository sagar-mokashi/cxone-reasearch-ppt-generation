import boto3
import json
import urllib3
from botocore.config import Config
from prompt import prompt2, system_prompt
from config import AWS_REGION, INFERENCE_PROFILE, LLM_MAX_TOKENS, LLM_TEMPERATURE

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def generate_slides(business_summary):
    """
    Generate PPT slides from business summary using LLM.
    Falls back to basic slides if LLM unavailable.
    """

    try:
        client = boto3.client("bedrock-runtime", region_name=AWS_REGION, verify=False)

        full_prompt = prompt2.replace("{{readme_text}}", business_summary)

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": LLM_MAX_TOKENS,
            "temperature": LLM_TEMPERATURE,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": full_prompt}]
                }
            ]
        })

        response = client.invoke_model(
            modelId=INFERENCE_PROFILE,
            body=body,
            contentType="application/json"
        )

        result = json.loads(response["body"].read())
        content = result.get("content", [{}])[0].get("text", "")
        
        if not content:
            print("Warning: Empty response from LLM, using fallback...")
            return generate_fallback_slides(business_summary)
        
        # Try to parse JSON response
        try:
            slides_data = json.loads(content)
        except json.JSONDecodeError:
            # Extract JSON if wrapped in text
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                slides_data = json.loads(json_match.group())
            else:
                print("Warning: Could not parse JSON from LLM response")
                return generate_fallback_slides(business_summary)
        
        # Return both project_title and slides
        return {
            "project_title": slides_data.get("project_title", "Project Presentation"),
            "slides": slides_data.get("slides", [])
        }
    
    except Exception as e:
        print(f"LLM Error: {e}")
        print("Using fallback slide generation...")
        return {
            "project_title": "Project Presentation",
            "slides": generate_fallback_slides(business_summary)
        }


def generate_fallback_slides(business_summary):
    """Generate basic business slides from summary when LLM is unavailable"""
    
    # Try to extract key info from summary
    lines = business_summary.split('\n')
    title = [l for l in lines if l.startswith('PROJECT:')]
    title = title[0].replace('PROJECT:', '').strip() if title else "Project Presentation"
    
    return [
        {
            "title": title,
            "points": [
                "Business-focused presentation",
                "Problem to solution overview",
                "Key benefits and outcomes",
                "Roadmap and next steps"
            ]
        },
        {
            "title": "Overview",
            "points": [
                "Project: " + title,
                "Focus: Business value and outcomes",
                "Audience: Stakeholders and decision makers",
                "Goal: Clear understanding of solution"
            ]
        },
        {
            "title": "Problem & Solution",
            "points": [
                "Identified business challenges",
                "Innovative solution approach",
                "Clear value proposition",
                "Expected business impact"
            ]
        },
        {
            "title": "Key Benefits",
            "points": [
                "Improved business outcomes",
                "Operational efficiency",
                "Cost optimization",
                "Strategic advantage"
            ]
        },
        {
            "title": "Current Capabilities",
            "points": [
                "Production-ready features",
                "Scalable architecture",
                "Proven performance",
                "Reliable operations"
            ]
        },
        {
            "title": "Roadmap & Vision",
            "points": [
                "Phase 1: Current implementation (Complete)",
                "Phase 2: Enhanced capabilities (Planned)",
                "Phase 3: Advanced features (Future)",
                "Continuous improvement cycle"
            ]
        },
        {
            "title": "Next Steps",
            "points": [
                "Stakeholder alignment",
                "Implementation planning",
                "Resource allocation",
                "Success measurement"
            ]
        }
    ]