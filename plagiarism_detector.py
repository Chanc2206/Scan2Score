"""
Plagiarism Detection Service for Scan2Score
Integrates GPTZero and CopyLeaks APIs for comprehensive plagiarism detection
"""

import asyncio
import logging
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import re
import requests
import httpx
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PlagiarismResult:
    """Data class for plagiarism detection results"""
    is_plagiarized: bool
    confidence_score: float
    ai_generated_probability: float
    sources_found: List[Dict]
    similarity_percentage: float
    detection_method: str
    timestamp: str
    additional_info: Dict

class PlagiarismDetector:
    """Comprehensive plagiarism detection using multiple APIs and techniques"""
    
    def __init__(self,
                 gptzero_api_key: str = None,
                 copyleaks_email: str = None,
                 copyleaks_api_key: str = None):
        """
        Initialize plagiarism detector
        
        Args:
            gptzero_api_key: API key for GPTZero service
            copyleaks_email: Email for CopyLeaks account
            copyleaks_api_key: API key for CopyLeaks service
        """
        self.gptzero_api_key = gptzero_api_key
        self.copyleaks_email = copyleaks_email
        self.copyleaks_api_key = copyleaks_api_key
        
        # API endpoints
        self.gptzero_base_url = "https://api.gptzero.me/v2"
        self.copyleaks_base_url = "https://api.copyleaks.com/v3"
        
        # Initialize session for requests
        self.session = requests.Session()
        self.async_client = httpx.AsyncClient(timeout=30.0)
        
        # Cache for results (simple in-memory cache)
        self.results_cache = {}
        self.cache_ttl = timedelta(hours=24)
    
    def _generate_text_hash(self, text: str) -> str:
        """Generate hash for text caching"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid"""
        if not cache_entry:
            return False
        
        cache_time = datetime.fromisoformat(cache_entry.get('timestamp', ''))
        return datetime.now() - cache_time < self.cache_ttl
    
    async def detect_ai_generated_content(self, text: str) -> Dict:
        """
        Detect AI-generated content using GPTZero
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with AI detection results
        """
        if not self.gptzero_api_key:
            return {
                'success': False,
                'error': 'GPTZero API key not provided',
                'ai_probability': 0.0
            }
        
        # Check cache first
        text_hash = self._generate_text_hash(text)
        cache_key = f"gptzero_{text_hash}"
        
        if cache_key in self.results_cache and self._is_cache_valid(self.results_cache[cache_key]):
            logger.info("Returning cached GPTZero result")
            return self.results_cache[cache_key]['result']
        
        try:
            headers = {
                'Authorization': f'Bearer {self.gptzero_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'document': text,
                'version': '2024-01-09'  # Use latest version
            }
            
            async with self.async_client as client:
                response = await client.post(
                    f"{self.gptzero_base_url}/predict/text",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    processed_result = {
                        'success': True,
                        'ai_probability': result.get('documents', [{}])[0].get('average_generated_prob', 0.0),
                        'completely_generated_prob': result.get('documents', [{}])[0].get('completely_generated_prob', 0.0),
                        'overall_burstiness': result.get('documents', [{}])[0].get('overall_burstiness', 0.0),
                        'perplexity': result.get('documents', [{}])[0].get('perplexity', 0.0),
                        'sentences': result.get('documents', [{}])[0].get('sentences', []),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Cache result
                    self.results_cache[cache_key] = {
                        'result': processed_result,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    return processed_result
                else:
                    logger.error(f"GPTZero API error: {response.status_code} - {response.text}")
                    return {
                        'success': False,
                        'error': f"API error: {response.status_code}",
                        'ai_probability': 0.0
                    }
                    
        except Exception as e:
            logger.error(f"Error detecting AI content with GPTZero: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'ai_probability': 0.0
            }
    
    async def detect_traditional_plagiarism(self, text: str, title: str = "Document") -> Dict:
        """
        Detect traditional plagiarism using CopyLeaks
        
        Args:
            text: Text to analyze
            title: Document title for reference
            
        Returns:
            Dictionary with plagiarism detection results
        """
        if not self.copyleaks_email or not self.copyleaks_api_key:
            return {
                'success': False,
                'error': 'CopyLeaks credentials not provided',
                'similarity_percentage': 0.0,
                'sources': []
            }
        
        # Check cache first
        text_hash = self._generate_text_hash(text)
        cache_key = f"copyleaks_{text_hash}"
        
        if cache_key in self.results_cache and self._is_cache_valid(self.results_cache[cache_key]):
            logger.info("Returning cached CopyLeaks result")
            return self.results_cache[cache_key]['result']
        
        try:
            # First, get access token
            auth_response = await self._get_copyleaks_token()
            if not auth_response.get('success'):
                return auth_response
            
            access_token = auth_response['access_token']
            
            # Submit document for scanning
            scan_id = self._generate_text_hash(text)[:16]  # Unique scan ID
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            scan_payload = {
                'base64': self._encode_text_to_base64(text),
                'filename': f"{title}.txt",
                'properties': {
                    'webhooks': {
                        'status': 'https://your-webhook-url.com/status'  # Replace with actual webhook
                    },
                    'includeHtml': False,
                    'developerPayload': f'scan_{scan_id}'
                }
            }
            
            async with self.async_client as client:
                # Submit scan
                submit_response = await client.put(
                    f"{self.copyleaks_base_url}/education/{scan_id}",
                    headers=headers,
                    json=scan_payload
                )
                
                if submit_response.status_code in [200, 201]:
                    # Wait for scan completion (simplified approach)
                    await asyncio.sleep(10)  # Wait 10 seconds for processing
                    
                    # Get results
                    results_response = await client.get(
                        f"{self.copyleaks_base_url}/education/{scan_id}/result",
                        headers=headers
                    )
                    
                    if results_response.status_code == 200:
                        result = results_response.json()
                        
                        processed_result = {
                            'success': True,
                            'scan_id': scan_id,
                            'similarity_percentage': result.get('scannedDocument', {}).get('totalTextCredits', 0),
                            'identical_percentage': result.get('scannedDocument', {}).get('creditsPerResult', 0),
                            'minor_changes_percentage': result.get('scannedDocument', {}).get('totalCredits', 0),
                            'sources': self._process_copyleaks_sources(result.get('results', [])),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Cache result
                        self.results_cache[cache_key] = {
                            'result': processed_result,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        return processed_result
                    else:
                        # Results not ready yet, return partial result
                        return {
                            'success': True,
                            'scan_id': scan_id,
                            'similarity_percentage': 0.0,
                            'status': 'processing',
                            'message': 'Scan in progress, results will be available shortly',
                            'timestamp': datetime.now().isoformat()
                        }
                else:
                    logger.error(f"CopyLeaks submit error: {submit_response.status_code}")
                    return {
                        'success': False,
                        'error': f"Submit error: {submit_response.status_code}",
                        'similarity_percentage': 0.0
                    }
                    
        except Exception as e:
            logger.error(f"Error detecting plagiarism with CopyLeaks: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'similarity_percentage': 0.0
            }
    
    async def _get_copyleaks_token(self) -> Dict:
        """Get access token from CopyLeaks"""
        try:
            auth_payload = {
                'email': self.copyleaks_email,
                'key': self.copyleaks_api_key
            }
            
            async with self.async_client as client:
                response = await client.post(
                    f"{self.copyleaks_base_url}/account/login/api",
                    json=auth_payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        'success': True,
                        'access_token': result.get('access_token'),
                        'expires_in': result.get('expires_in')
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Authentication failed: {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': f"Authentication error: {str(e)}"
            }
    
    def _encode_text_to_base64(self, text: str) -> str:
        """Encode text to base64 for CopyLeaks"""
        import base64
        return base64.b64encode(text.encode('utf-8')).decode('utf-8')
    
    def _process_copyleaks_sources(self, sources: List[Dict]) -> List[Dict]:
        """Process CopyLeaks sources into simplified format"""
        processed_sources = []
        
        for source in sources[:10]:  # Limit to top 10 sources
            processed_sources.append({
                'url': source.get('url', ''),
                'title': source.get('title', 'Unknown Source'),
                'similarity_percentage': source.get('matchedWords', 0),
                'matched_words': source.get('introduction', {}).get('words', 0),
                'type': source.get('type', 'web')
            })
        
        return processed_sources
    
    def detect_pattern_based_plagiarism(self, text: str, reference_texts: List[str] = None) -> Dict:
        """
        Simple pattern-based plagiarism detection
        
        Args:
            text: Text to analyze
            reference_texts: List of reference texts to compare against
            
        Returns:
            Pattern-based plagiarism analysis
        """
        try:
            # Basic text preprocessing
            clean_text = self._preprocess_text(text)
            
            # Check for common plagiarism patterns
            patterns = {
                'excessive_quotes': self._check_excessive_quotes(text),
                'repetitive_phrases': self._check_repetitive_phrases(clean_text),
                'unusual_formatting': self._check_unusual_formatting(text),
                'citation_inconsistencies': self._check_citation_patterns(text)
            }
            
            # Calculate overall suspicion score
            suspicion_score = 0.0
            if patterns['excessive_quotes']['detected']:
                suspicion_score += 0.3
            if patterns['repetitive_phrases']['detected']:
                suspicion_score += 0.4
            if patterns['unusual_formatting']['detected']:
                suspicion_score += 0.2
            if patterns['citation_inconsistencies']['detected']:
                suspicion_score += 0.1
            
            # Compare with reference texts if provided
            similarity_scores = []
            if reference_texts:
                for ref_text in reference_texts:
                    similarity = self._calculate_text_similarity(clean_text, self._preprocess_text(ref_text))
                    similarity_scores.append(similarity)
            
            max_similarity = max(similarity_scores) if similarity_scores else 0.0
            
            return {
                'success': True,
                'suspicion_score': min(suspicion_score, 1.0),
                'max_similarity': max_similarity,
                'patterns_detected': patterns,
                'reference_similarities': similarity_scores,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in pattern-based detection: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'suspicion_score': 0.0
            }
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for analysis"""
        # Convert to lowercase and remove extra whitespace
        text = re.sub(r'\s+', ' ', text.lower().strip())
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,;:!?-]', '', text)
        return text
    
    def _check_excessive_quotes(self, text: str) -> Dict:
        """Check for excessive quoted content"""
        quote_pattern = r'"[^"]*"'
        quotes = re.findall(quote_pattern, text)
        
        total_quoted_chars = sum(len(quote) for quote in quotes)
        quote_percentage = total_quoted_chars / len(text) if text else 0
        
        return {
            'detected': quote_percentage > 0.4,  # More than 40% quoted
            'percentage': quote_percentage,
            'quote_count': len(quotes)
        }
    
    def _check_repetitive_phrases(self, text: str) -> Dict:
        """Check for repetitive phrases (potential copy-paste)"""
        words = text.split()
        phrase_length = 5  # Check for 5-word phrases
        phrases = {}
        
        for i in range(len(words) - phrase_length + 1):
            phrase = ' '.join(words[i:i + phrase_length])
            phrases[phrase] = phrases.get(phrase, 0) + 1
        
        repeated_phrases = {k: v for k, v in phrases.items() if v > 1}
        max_repetition = max(repeated_phrases.values()) if repeated_phrases else 0
        
        return {
            'detected': max_repetition > 2,
            'max_repetitions': max_repetition,
            'repeated_phrases_count': len(repeated_phrases)
        }
    
    def _check_unusual_formatting(self, text: str) -> Dict:
        """Check for unusual formatting that might indicate copy-paste"""
        indicators = {
            'inconsistent_spacing': len(re.findall(r'\s{3,}', text)) > 0,
            'mixed_case_patterns': len(re.findall(r'[a-z][A-Z]', text)) > len(text) * 0.05,
            'unusual_punctuation': len(re.findall(r'[.]{2,}|[!]{2,}|[?]{2,}', text)) > 0
        }
        
        detected_count = sum(indicators.values())
        
        return {
            'detected': detected_count > 1,
            'indicators': indicators,
            'indicator_count': detected_count
        }
    
    def _check_citation_patterns(self, text: str) -> Dict:
        """Check for citation inconsistencies"""
        citation_patterns = [
            r'\([^)]*\d{4}[^)]*\)',  # (Author, 2024)
            r'\[[^\]]*\d+[^\]]*\]',  # [1], [Author, 2024]
            r'(?:according to|as stated by|cited in)\s+[^.]+',  # According to...
        ]
        
        citations = []
        for pattern in citation_patterns:
            citations.extend(re.findall(pattern, text, re.IGNORECASE))
        
        # Simple check for citation density
        words = len(text.split())
        citation_density = len(citations) / (words / 100) if words > 0 else 0  # Citations per 100 words
        
        return {
            'detected': citation_density > 5 or citation_density < 0.5,  # Too many or too few citations
            'citation_count': len(citations),
            'citation_density': citation_density
        }
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using Jaccard similarity"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    async def comprehensive_plagiarism_check(self,
                                          text: str,
                                          title: str = "Document",
                                          reference_texts: List[str] = None) -> PlagiarismResult:
        """
        Perform comprehensive plagiarism detection using all available methods
        
        Args:
            text: Text to analyze
            title: Document title
            reference_texts: Optional reference texts to compare against
            
        Returns:
            Comprehensive plagiarism analysis result
        """
        logger.info(f"Starting comprehensive plagiarism check for document: {title}")
        
        # Run all detection methods concurrently
        tasks = [
            self.detect_ai_generated_content(text),
            self.detect_traditional_plagiarism(text, title)
        ]
        
        ai_result, traditional_result = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Run pattern-based detection (synchronous)
        pattern_result = self.detect_pattern_based_plagiarism(text, reference_texts)
        
        # Process results
        ai_probability = 0.0
        if isinstance(ai_result, dict) and ai_result.get('success'):
            ai_probability = ai_result.get('ai_probability', 0.0)
        
        similarity_percentage = 0.0
        sources_found = []
        if isinstance(traditional_result, dict) and traditional_result.get('success'):
            similarity_percentage = traditional_result.get('similarity_percentage', 0.0)
            sources_found = traditional_result.get('sources', [])
        
        pattern_suspicion = 0.0
        if pattern_result.get('success'):
            pattern_suspicion = pattern_result.get('suspicion_score', 0.0)
        
        # Calculate overall confidence and plagiarism determination
        confidence_factors = []
        
        # AI-generated content confidence
        if ai_probability > 0.7:
            confidence_factors.append(0.9)
        elif ai_probability > 0.5:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.3)
        
        # Traditional plagiarism confidence
        if similarity_percentage > 30:
            confidence_factors.append(0.9)
        elif similarity_percentage > 15:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.3)
        
        # Pattern-based confidence
        if pattern_suspicion > 0.6:
            confidence_factors.append(0.8)
        elif pattern_suspicion > 0.3:
            confidence_factors.append(0.6)
        else:
            confidence_factors.append(0.4)
        
        overall_confidence = sum(confidence_factors) / len(confidence_factors)
        
        # Determine if plagiarized
        is_plagiarized = (
            ai_probability > 0.7 or
            similarity_percentage > 25 or
            pattern_suspicion > 0.6
        )
        
        # Determine primary detection method
        detection_method = "pattern_based"
        if ai_probability > similarity_percentage and ai_probability > pattern_suspicion * 100:
            detection_method = "ai_detection"
        elif similarity_percentage > pattern_suspicion * 100:
            detection_method = "traditional_plagiarism"
        
        return PlagiarismResult(
            is_plagiarized=is_plagiarized,
            confidence_score=overall_confidence,
            ai_generated_probability=ai_probability,
            sources_found=sources_found,
            similarity_percentage=similarity_percentage,
            detection_method=detection_method,
            timestamp=datetime.now().isoformat(),
            additional_info={
                'ai_detection_result': ai_result if isinstance(ai_result, dict) else {'error': str(ai_result)},
                'traditional_detection_result': traditional_result if isinstance(traditional_result, dict) else {'error': str(traditional_result)},
                'pattern_detection_result': pattern_result,
                'text_length': len(text),
                'word_count': len(text.split())
            }
        )