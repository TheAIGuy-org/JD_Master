# llm/prompts.py
"""
World-class prompt templates for JD rewriting.
Each prompt is engineered for precision and clarity.
"""
from typing import List, Dict


class PromptTemplates:
    """
    Centralized repository of all prompt templates.
    Each template is optimized for its specific task.
    """
    
    @staticmethod
    def segment_sections(text: str) -> str:
        """
        Prompt for segmenting JD text into logical sections.
        
        Goal: Break text into semantically meaningful blocks.
        Strategy: Ask LLM to identify section boundaries and classify.
        """
        return f"""You are a Job Description parser. Your task is to segment the following text into logical sections.

INSTRUCTIONS:
1. Identify distinct sections based on content and structure
2. For each section, extract the header (if present) and content
3. Classify each section using EXACTLY ONE of these semantic tags:
   - WORK_SCOPE: Job responsibilities, duties, what the person will do
   - PREREQUISITES: Required qualifications, experience requirements
   - SKILL_LIST: Technical skills, tools, technologies
   - BRAND_STATIC: Company description, mission, values, culture
   - COMPENSATION: Salary, benefits, perks
   - UNKNOWN: Cannot determine semantic meaning

OUTPUT FORMAT:
Return a JSON array of sections. Each section must have:
- "header": The section title/header (or "Untitled" if none)
- "content": The section text
- "semantic_tag": One of the tags listed above

CRITICAL RULES:
- Output ONLY valid JSON, no markdown, no preamble
- Every section must have all three fields
- Use semantic_tag values EXACTLY as listed above
- If unsure about a tag, use "UNKNOWN"

TEXT TO SEGMENT:
{text}

JSON OUTPUT:"""
    
    @staticmethod
    def extract_trinity(sections: List[Dict], target_profile: Dict) -> str:
        """
        Prompt for extracting skills and domain from JD.
        
        Goal: Build ground truth that anchors the rewrite.
        Strategy: Extract only what's explicitly stated, filter by profile.
        """
        sections_text = "\n\n".join([
            f"SECTION: {s['original_header']}\n{s['original_content']}"
            for s in sections
        ])
        
        excluded_categories = target_profile.get("skill_filters", {}).get("exclude_categories", [])
        
        return f"""You are a skill extraction specialist. Extract the Ground Truth from this Job Description.

YOUR MISSION:
Extract three critical pieces of information:
1. JOB_TITLE: The exact role title mentioned in the JD (e.g. "Senior Software Engineer")
2. SKILLS: Concrete technical skills, tools, technologies explicitly mentioned
3. DOMAIN: The industry/business domain (e.g., "Fintech", "Healthcare", "E-commerce")

FILTERING RULES:
The target role is: {target_profile['label']}
EXCLUDE any skills in these categories: {', '.join(excluded_categories)}

EXTRACTION RULES:
1. Extract ONLY skills explicitly mentioned in the text
2. Use the exact terminology from the JD (e.g., "Python", not "Python programming")
3. Do NOT infer or add skills not present
4. For domain, infer from context if not explicitly stated
5. Look for the Job Title at the beginning or in 'About the Role' sections.

JOB DESCRIPTION SECTIONS:
{sections_text}

OUTPUT FORMAT:
Return ONLY valid JSON with this structure:
{{
  "job_title": "extracted title string",
  "skills": ["skill1", "skill2", ...],
  "domain": "domain_name"
}}

CRITICAL RULES:
- Output ONLY JSON, no markdown
- Skills array must not be empty (extract at least generic skills if specific ones filtered)

JSON OUTPUT:"""
    
    @staticmethod
    def rewrite_section_actor(
        section: Dict,
        target_profile: Dict,
        approved_skills: List[str],
        domain_context: str
    ) -> str:
        """
        Actor prompt for rewriting a section.
        
        Goal: Transform content to match target seniority level.
        Strategy: Apply behavioral profile while preserving truth.
        """
        vocab_shifts = target_profile.get("vocabulary_shifts", {})
        vocab_examples = "\n".join([f"- Replace '{k}' with '{v}'" for k, v in vocab_shifts.items()])
        
        return f"""You are a Job Description rewriter. Transform this section to match the target seniority level.

TARGET PROFILE: {target_profile['label']}

BEHAVIORAL LENS:
{target_profile['reasoning_focus']}

AUTONOMY EXPECTATION:
{target_profile['autonomy_level']}

RISK AVOIDANCE:
{target_profile['risk_avoidance']}

VOCABULARY TRANSFORMATIONS:
{vocab_examples}

APPROVED SKILLS (Use ONLY these):
{', '.join(approved_skills)}

DOMAIN CONTEXT:
{domain_context}

SECTION TO REWRITE:
Header: {section['original_header']}
Content: {section['original_content']}

REWRITING RULES:
1. Preserve factual accuracy - do not invent requirements
2. Use ONLY skills from the approved skills list
3. Apply vocabulary transformations to shift tone
4. Match the autonomy level described above
5. Avoid language that violates the risk avoidance guidelines
6. Keep the rewritten content roughly the same length as original
7. Maintain professional, clear language
8. FORMATTING: If the original content uses bullet points, you MUST use Markdown bullet points ('- ') in the output.

OUTPUT FORMAT:
Return ONLY the rewritten content as plain text, no JSON, no markdown.

REWRITTEN CONTENT:"""
    
    @staticmethod
    def validate_section_critic(
        section: Dict,
        draft_content: str,
        target_profile: Dict,
        approved_skills: List[str]
    ) -> str:
        """
        Critic prompt for validating rewritten content.
        
        Goal: Catch hallucinations and profile violations.
        Strategy: Check against ground truth and profile rules.
        """
        return f"""You are a quality control critic. Validate this rewritten Job Description section.

TARGET PROFILE: {target_profile['label']}

RISK AVOIDANCE RULES:
{target_profile['risk_avoidance']}

APPROVED SKILLS LIST:
{', '.join(approved_skills)}

ORIGINAL CONTENT:
{section['original_content']}

REWRITTEN CONTENT:
{draft_content}

VALIDATION CHECKLIST:
1. HALLUCINATION CHECK: Does the draft mention skills NOT in the approved skills list?
2. PROFILE VIOLATION: Does the draft violate the risk avoidance rules?
3. FACTUAL DRIFT: Does the draft contradict the original meaning?
4. TONE MISMATCH: Does the draft fail to match the target seniority level?

OUTPUT FORMAT:
Return ONLY valid JSON with this structure:
{{
  "is_valid": true/false,
  "violations": ["violation1", "violation2", ...],
  "suggestions": "Brief suggestions for improvement if invalid"
}}

CRITICAL RULES:
- Output ONLY JSON, no markdown, no preamble
- is_valid should be false if ANY check fails
- violations array should list specific issues found
- If valid, violations should be empty array

JSON OUTPUT:"""
    
    @staticmethod
    def assemble_document(sections: List[Dict], domain_context: str) -> str:
        """
        Prompt for assembling final document with polish.
        
        Goal: Create cohesive, professional output.
        Strategy: Stitch sections with smooth transitions.
        """
        sections_text = "\n\n".join([
            f"## {s['original_header']}\n{s['final_content']}"
            for s in sections
        ])
        
        return f"""You are a document formatter. Create a polished Job Description from these sections.

DOMAIN: {domain_context}

SECTIONS:
{sections_text}

YOUR TASK:
1. Organize sections in a logical order (typically: Brand → Scope → Requirements → Skills → Compensation)
2. Ensure consistent formatting and tone
3. Add a brief, professional header introducing the role
4. Ensure smooth transitions between sections
5. Output in clean Markdown format

OUTPUT FORMAT:
Return the complete, polished Job Description in Markdown format.

POLISHED JOB DESCRIPTION:"""
    
    @staticmethod
    def refine_section_actor(
        original_draft: str,
        critique: str,
        target_profile: Dict,
        approved_skills: List[str]
    ) -> str:
        """
        FIXED: Added missing refinement prompt for Auto-Correction Loop.
        """
        return f"""You are a Job Description editor. Fix the draft based on the specific critique provided.

TARGET PROFILE: {target_profile['label']}
APPROVED SKILLS: {', '.join(approved_skills)}

CRITIQUE / ERRORS TO FIX:
{critique}

CURRENT DRAFT:
{original_draft}

TASK:
Rewrite the draft to address the critique. 
- If the critique says "Remove X", remove it.
- If the critique says "Change tone", change it.
- Ensure the result still reads professionally.

OUTPUT FORMAT:
Return ONLY the fixed content as plain text.

FIXED CONTENT:"""
    
    @staticmethod
    def assemble_document(sections: List[Dict], domain_context: str) -> str:
        """
        Prompt for assembling final document with polish.
        """
        sections_text = "\n\n".join([
            f"## {s['original_header']}\n{s['final_content']}"
            for s in sections
        ])
        
        return f"""You are a document formatter. Create a polished Job Description from these sections.

DOMAIN: {domain_context}

SECTIONS:
{sections_text}

YOUR TASK:
1. Organize sections in a logical order (typically: Brand → Scope → Requirements → Skills → Compensation)
2. Ensure consistent formatting and tone
3. Add a brief, professional header introducing the role
4. Ensure smooth transitions between sections
5. Output in clean Markdown format

OUTPUT FORMAT:
Return the complete, polished Job Description in Markdown format.

POLISHED JOB DESCRIPTION:"""