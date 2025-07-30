"""
AI Evaluator Service for Scan2Score
Uses Claude 3.7 Sonnet with Chain-of-Thought reasoning for subjective answer evaluation
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import re

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)

class AIEvaluator:
    """AI-powered subjective answer evaluator using Claude 3.7 Sonnet and Chain-of-Thought reasoning"""
    
    def __init__(self, 
                 anthropic_api_key: str = None,
                 openai_api_key: str = None,
                 claude_model: str = "claude-3-7-sonnet-20250219",
                 gpt_model: str = "gpt-4-turbo-preview",
                 max_tokens: int = 4000,
                 temperature: float = 0.3):
        """
        Initialize AI Evaluator
        
        Args:
            anthropic_api_key: Anthropic API key for Claude
            openai_api_key: OpenAI API key for GPT models
            claude_model: Claude model to use (updated to latest Claude 3.7 Sonnet)
            gpt_model: GPT model to use as fallback
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation
        """
        self.anthropic_api_key = anthropic_api_key
        self.openai_api_key = openai_api_key
        self.claude_model = claude_model
        self.gpt_model = gpt_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Initialize clients
        self.anthropic_client = None
        self.openai_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize AI service clients"""
        try:
            if self.anthropic_api_key and anthropic:
                self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
                logger.info("Anthropic client initialized successfully")
            
            if self.openai_api_key and openai:
                self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing AI clients: {str(e)}")
    
    def create_evaluation_prompt(self, 
                                question: str,
                                student_answer: str,
                                rubric: Dict,
                                context: str = "") -> str:
        """
        Create a comprehensive evaluation prompt with Chain-of-Thought reasoning
        
        Args:
            question: The original question
            student_answer: Student's answer to evaluate
            rubric: Grading rubric with criteria and scoring
            context: Additional context or reference materials
            
        Returns:
            Formatted evaluation prompt
        """
        
        rubric_text = self._format_rubric(rubric)
        
        # Build prompt parts separately to avoid f-string backslash issues
        context_section = ""
        if context:
            context_section = "\n## Additional Context/Reference Material:\n" + context + "\n"
        
        prompt = f"""You are an expert academic evaluator tasked with grading a student's subjective answer. Use Chain-of-Thought reasoning to provide a comprehensive evaluation.

## Question:
{question}

## Student's Answer:
{student_answer}

## Grading Rubric:
{rubric_text}{context_section}

## Evaluation Instructions:
Please evaluate this answer using Chain-of-Thought reasoning. Follow these steps:

### Step 1: Content Analysis
- Identify the key concepts, facts, and arguments presented
- Note any missing critical elements
- Assess the accuracy of information provided

### Step 2: Structure and Organization
- Evaluate the logical flow and coherence of the answer
- Check if the response directly addresses the question
- Assess clarity and readability

### Step 3: Critical Thinking and Depth
- Analyze the depth of understanding demonstrated
- Evaluate reasoning quality and supporting evidence
- Check for original insights or creative thinking

### Step 4: Rubric Application
- Apply each rubric criterion systematically
- Provide specific evidence for each score
- Consider partial credit where appropriate

### Step 5: Final Scoring and Feedback
- Calculate the total score based on rubric weights
- Provide constructive feedback for improvement
- Highlight strengths and areas for development

## Required Output Format:
Please provide your evaluation in the following JSON format:

```json
{{
    "chain_of_thought": {{
        "content_analysis": "Your detailed analysis of content quality, accuracy, and completeness",
        "structure_organization": "Your assessment of answer structure, clarity, and organization",
        "critical_thinking": "Your evaluation of reasoning depth, evidence use, and insights",
        "rubric_application": "Step-by-step application of each rubric criterion with justification"
    }},
    "detailed_scores": {{
        "criterion_1": {{"score": X, "max_score": Y, "justification": "specific reasoning"}},
        "criterion_2": {{"score": X, "max_score": Y, "justification": "specific reasoning"}}
    }},
    "total_score": X,
    "max_possible_score": Y,
    "percentage": Z,
    "feedback": {{
        "strengths": ["strength 1", "strength 2"],
        "areas_for_improvement": ["improvement 1", "improvement 2"],
        "specific_suggestions": ["suggestion 1", "suggestion 2"]
    }},
    "confidence_level": "High/Medium/Low",
    "additional_comments": "Any additional observations or recommendations"
}}
```

Begin your evaluation:
"""
        return prompt
    
    def _format_rubric(self, rubric: Dict) -> str:
        """Format rubric for inclusion in prompt"""
        if not rubric:
            return "No specific rubric provided. Use general academic standards."
        
        formatted = []
        total_points = rubric.get('total_points', 100)
        formatted.append(f"**Total Points: {total_points}**\n")
        
        criteria = rubric.get('criteria', [])
        for i, criterion in enumerate(criteria, 1):
            name = criterion.get('name', f'Criterion {i}')
            description = criterion.get('description', '')
            max_points = criterion.get('max_points', 0)
            weight = criterion.get('weight', 1.0)
            
            formatted.append(f"**{name}** (Max: {max_points} points, Weight: {weight})")
            formatted.append(f"Description: {description}")
            
            # Add performance levels if available
            levels = criterion.get('performance_levels', [])
            if levels:
                formatted.append("Performance Levels:")
                for level in levels:
                    level_name = level.get('name', '')
                    level_description = level.get('description', '')
                    level_points = level.get('points', 0)
                    formatted.append(f"  - {level_name} ({level_points} pts): {level_description}")
            
            formatted.append("")  # Empty line between criteria
        
        return "\n".join(formatted)
    
    async def evaluate_answer_with_claude(self,
                                        question: str,
                                        student_answer: str,
                                        rubric: Dict,
                                        context: str = "") -> Dict:
        """
        Evaluate answer using Claude 3.7 Sonnet with Chain-of-Thought reasoning
        
        Args:
            question: The question being answered
            student_answer: Student's response
            rubric: Grading rubric
            context: Additional context
            
        Returns:
            Detailed evaluation results
        """
        if not self.anthropic_client:
            raise ValueError("Anthropic client not initialized. Check API key.")
        
        try:
            prompt = self.create_evaluation_prompt(question, student_answer, rubric, context)
            
            message = self.anthropic_client.messages.create(
                model=self.claude_model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            response_text = message.content[0].text
            
            # Parse JSON response
            evaluation_result = self._parse_evaluation_response(response_text)
            evaluation_result['model_used'] = self.claude_model
            evaluation_result['timestamp'] = datetime.now().isoformat()
            
            return evaluation_result
            
        except Exception as e:
            logger.error(f"Error evaluating with Claude: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'model_used': self.claude_model,
                'timestamp': datetime.now().isoformat()
            }
    
    async def evaluate_answer_with_gpt(self,
                                     question: str,
                                     student_answer: str,
                                     rubric: Dict,
                                     context: str = "") -> Dict:
        """
        Evaluate answer using GPT as fallback
        
        Args:
            question: The question being answered
            student_answer: Student's response
            rubric: Grading rubric
            context: Additional context
            
        Returns:
            Detailed evaluation results
        """
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized. Check API key.")
        
        try:
            prompt = self.create_evaluation_prompt(question, student_answer, rubric, context)
            
            response = self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            evaluation_result = self._parse_evaluation_response(response_text)
            evaluation_result['model_used'] = self.gpt_model
            evaluation_result['timestamp'] = datetime.now().isoformat()
            
            return evaluation_result
            
        except Exception as e:
            logger.error(f"Error evaluating with GPT: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'model_used': self.gpt_model,
                'timestamp': datetime.now().isoformat()
            }
    
    def _parse_evaluation_response(self, response_text: str) -> Dict:
        """Parse the AI evaluation response and extract JSON"""
        try:
            # Look for JSON content in the response
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without markdown formatting
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in response")
            
            evaluation = json.loads(json_str)
            evaluation['success'] = True
            evaluation['raw_response'] = response_text
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error parsing evaluation response: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to parse response: {str(e)}",
                'raw_response': response_text,
                'chain_of_thought': {'parsing_error': str(e)},
                'total_score': 0,
                'max_possible_score': 100,
                'percentage': 0,
                'feedback': {
                    'strengths': [],
                    'areas_for_improvement': ['Response parsing failed - manual review required'],
                    'specific_suggestions': []
                }
            }
    
    async def evaluate_answer(self,
                            question: str,
                            student_answer: str,
                            rubric: Dict,
                            context: str = "",
                            preferred_model: str = "claude") -> Dict:
        """
        Evaluate answer using preferred model with fallback
        
        Args:
            question: The question being answered
            student_answer: Student's response
            rubric: Grading rubric
            context: Additional context
            preferred_model: "claude" or "gpt"
            
        Returns:
            Detailed evaluation results
        """
        if preferred_model.lower() == "claude" and self.anthropic_client:
            try:
                return await self.evaluate_answer_with_claude(question, student_answer, rubric, context)
            except Exception as e:
                logger.warning(f"Claude evaluation failed, trying GPT: {str(e)}")
                if self.openai_client:
                    return await self.evaluate_answer_with_gpt(question, student_answer, rubric, context)
                else:
                    raise
        
        elif self.openai_client:
            return await self.evaluate_answer_with_gpt(question, student_answer, rubric, context)
        
        else:
            raise ValueError("No AI client available for evaluation")
    
    def batch_evaluate_answers(self,
                             evaluation_requests: List[Dict]) -> List[Dict]:
        """
        Evaluate multiple answers in batch
        
        Args:
            evaluation_requests: List of evaluation request dictionaries
            
        Returns:
            List of evaluation results
        """
        async def evaluate_batch():
            tasks = []
            for request in evaluation_requests:
                task = self.evaluate_answer(
                    question=request.get('question', ''),
                    student_answer=request.get('student_answer', ''),
                    rubric=request.get('rubric', {}),
                    context=request.get('context', ''),
                    preferred_model=request.get('preferred_model', 'claude')
                )
                tasks.append(task)
            
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(evaluate_batch())
        
        # Convert exceptions to error dictionaries
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'error': str(result),
                    'request_index': i,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                result['request_index'] = i
                processed_results.append(result)
        
        return processed_results
    
    def create_custom_rubric(self,
                           subject: str,
                           question_type: str,
                           max_points: int = 100,
                           criteria_count: int = 4) -> Dict:
        """
        Generate a custom rubric based on subject and question type
        
        Args:
            subject: Academic subject (e.g., "History", "Science", "Literature")
            question_type: Type of question (e.g., "essay", "short_answer", "analysis")
            max_points: Maximum possible points
            criteria_count: Number of evaluation criteria
            
        Returns:
            Generated rubric dictionary
        """
        
        # Default criteria templates based on question type
        criteria_templates = {
            'essay': [
                {'name': 'Content Knowledge', 'weight': 0.35, 'description': 'Accuracy and depth of subject matter understanding'},
                {'name': 'Organization & Structure', 'weight': 0.25, 'description': 'Logical flow, clear introduction, body, and conclusion'},
                {'name': 'Critical Analysis', 'weight': 0.25, 'description': 'Quality of reasoning, evidence use, and original insights'},
                {'name': 'Language & Mechanics', 'weight': 0.15, 'description': 'Grammar, vocabulary, clarity of expression'}
            ],
            'short_answer': [
                {'name': 'Accuracy', 'weight': 0.4, 'description': 'Correctness of factual information'},
                {'name': 'Completeness', 'weight': 0.3, 'description': 'Coverage of all required elements'},
                {'name': 'Clarity', 'weight': 0.2, 'description': 'Clear and concise communication'},
                {'name': 'Examples/Evidence', 'weight': 0.1, 'description': 'Use of relevant examples or supporting evidence'}
            ],
            'analysis': [
                {'name': 'Understanding', 'weight': 0.3, 'description': 'Demonstrates clear understanding of the topic'},
                {'name': 'Analysis Quality', 'weight': 0.35, 'description': 'Depth and sophistication of analytical thinking'},
                {'name': 'Evidence & Support', 'weight': 0.25, 'description': 'Use of relevant evidence to support arguments'},
                {'name': 'Synthesis', 'weight': 0.1, 'description': 'Ability to connect ideas and draw conclusions'}
            ]
        }
        
        # Select appropriate template
        template = criteria_templates.get(question_type.lower(), criteria_templates['short_answer'])
        
        # Generate rubric
        criteria = []
        for i, criterion_template in enumerate(template[:criteria_count]):
            criterion_points = int(max_points * criterion_template['weight'])
            
            criteria.append({
                'name': criterion_template['name'],
                'description': criterion_template['description'],
                'max_points': criterion_points,
                'weight': criterion_template['weight'],
                'performance_levels': [
                    {'name': 'Excellent', 'points': criterion_points, 'description': 'Exceeds expectations'},
                    {'name': 'Good', 'points': int(criterion_points * 0.8), 'description': 'Meets expectations'},
                    {'name': 'Satisfactory', 'points': int(criterion_points * 0.6), 'description': 'Partially meets expectations'},
                    {'name': 'Needs Improvement', 'points': int(criterion_points * 0.4), 'description': 'Below expectations'},
                    {'name': 'Unsatisfactory', 'points': 0, 'description': 'Does not meet expectations'}
                ]
            })
        
        return {
            'subject': subject,
            'question_type': question_type,
            'total_points': max_points,
            'criteria': criteria,
            'created_at': datetime.now().isoformat(),
            'version': '1.0'
        }