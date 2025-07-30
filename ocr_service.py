"""
OCR Service for Scan2Score
Uses PaddleOCR for text detection and recognition from images
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
import cv2
from PIL import Image
import io
import base64

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

logger = logging.getLogger(__name__)

class OCRService:
    """OCR service using PaddleOCR for text detection and recognition"""
    
    def __init__(self, 
                 lang: str = 'en',
                 use_angle_cls: bool = True,
                 use_gpu: bool = False,
                 use_doc_orientation_classify: bool = False,
                 use_doc_unwarping: bool = False,
                 use_textline_orientation: bool = True,
                 det_limit_side_len: int = 960,
                 rec_batch_num: int = 6,
                 cls_batch_num: int = 6,
                 drop_score: float = 0.5):
        """
        Initialize OCR Service
        
        Args:
            lang: Language for OCR (e.g., 'en', 'ch', 'fr', 'german', 'korean', 'japan')
            use_angle_cls: Use angle classification model
            use_gpu: Use GPU for inference
            use_doc_orientation_classify: Use document orientation classification
            use_doc_unwarping: Use document unwarping
            use_textline_orientation: Use text line orientation classification
            det_limit_side_len: Detection limit side length
            rec_batch_num: Recognition batch number
            cls_batch_num: Classification batch number
            drop_score: Drop score threshold for text recognition
        """
        if PaddleOCR is None:
            raise ImportError("PaddleOCR is not installed. Please install it using: pip install paddleocr")
        
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.use_gpu = use_gpu
        self.use_doc_orientation_classify = use_doc_orientation_classify
        self.use_doc_unwarping = use_doc_unwarping
        self.use_textline_orientation = use_textline_orientation
        self.det_limit_side_len = det_limit_side_len
        self.rec_batch_num = rec_batch_num
        self.cls_batch_num = cls_batch_num
        self.drop_score = drop_score
        
        self.ocr = None
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        """Initialize PaddleOCR with proper parameters"""
        try:
            # Device configuration
            device = 'gpu' if self.use_gpu else 'cpu'
            
            # Initialize PaddleOCR with correct parameters
            self.ocr = PaddleOCR(
                lang='en',  # Force English only
                use_doc_orientation_classify=self.use_doc_orientation_classify,
                use_doc_unwarping=self.use_doc_unwarping,
                use_textline_orientation=self.use_textline_orientation,
                text_det_limit_side_len=self.det_limit_side_len,
                text_recognition_batch_size=self.rec_batch_num,
                text_rec_score_thresh=self.drop_score,
                device=device,
                enable_mkldnn=True if not self.use_gpu else False,
                cpu_threads=8
            )
            
            logger.info(f"PaddleOCR initialized successfully with language: {self.lang}")
            
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
            raise
    
    def extract_text_from_image(self, image_input) -> List[Dict]:
        """
        Extract text from image using PaddleOCR
        
        Args:
            image_input: Image input (file path, PIL Image, numpy array, or base64 string)
            
        Returns:
            List of dictionaries containing detected text and bounding boxes
        """
        if self.ocr is None:
            raise RuntimeError("OCR not initialized")
        
        try:
            # Convert input to format acceptable by PaddleOCR
            image = self._prepare_image(image_input)
            
            # Perform OCR
            result = self.ocr.predict(image)
            
            # Process results
            extracted_texts = []
            for res in result:
                if hasattr(res, 'json'):
                    # Get the structured result
                    json_result = res.json
                    
                    # Extract text and bounding boxes
                    rec_texts = json_result.get('rec_texts', [])
                    rec_scores = json_result.get('rec_scores', [])
                    rec_boxes = json_result.get('rec_boxes', [])
                    
                    for i, text in enumerate(rec_texts):
                        if text.strip():  # Only include non-empty text
                            confidence = rec_scores[i] if i < len(rec_scores) else 0.0
                            bbox = rec_boxes[i] if i < len(rec_boxes) else []
                            
                            extracted_texts.append({
                                'text': text,
                                'confidence': float(confidence),
                                'bbox': bbox.tolist() if hasattr(bbox, 'tolist') else bbox,
                                'position': self._get_text_position(bbox)
                            })
                else:
                    # Fallback for older format
                    if isinstance(res, list):
                        for line in res:
                            if len(line) >= 2:
                                bbox, (text, confidence) = line[0], line[1]
                                if text.strip():
                                    extracted_texts.append({
                                        'text': text,
                                        'confidence': float(confidence),
                                        'bbox': bbox,
                                        'position': self._get_text_position(bbox)
                                    })
            
            logger.info(f"Extracted {len(extracted_texts)} text elements from image")
            return extracted_texts
            
        except Exception as e:
            logger.error(f"Error during OCR processing: {str(e)}")
            return []
    
    def _prepare_image(self, image_input):
        """
        Prepare image for OCR processing
        
        Args:
            image_input: Various image input formats
            
        Returns:
            Image in format suitable for PaddleOCR
        """
        try:
            # Handle different input types
            if isinstance(image_input, str):
                if image_input.startswith('data:image') or len(image_input) > 500:
                    # Base64 encoded image
                    if 'base64,' in image_input:
                        image_input = image_input.split('base64,')[1]
                    
                    image_data = base64.b64decode(image_input)
                    image = Image.open(io.BytesIO(image_data))
                    return np.array(image)
                else:
                    # File path
                    return image_input
            
            elif isinstance(image_input, Image.Image):
                # PIL Image
                return np.array(image_input)
            
            elif isinstance(image_input, np.ndarray):
                # NumPy array
                return image_input
            
            elif hasattr(image_input, 'read'):
                # File-like object
                image_data = image_input.read()
                image = Image.open(io.BytesIO(image_data))
                return np.array(image)
            
            else:
                raise ValueError(f"Unsupported image input type: {type(image_input)}")
                
        except Exception as e:
            logger.error(f"Error preparing image: {str(e)}")
            raise
    
    def _get_text_position(self, bbox) -> Dict:
        """
        Calculate text position information from bounding box
        
        Args:
            bbox: Bounding box coordinates
            
        Returns:
            Dictionary with position information
        """
        try:
            if not bbox or len(bbox) < 4:
                return {'x': 0, 'y': 0, 'width': 0, 'height': 0}
            
            # Handle different bbox formats
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                # Format: [x_min, y_min, x_max, y_max]
                if all(isinstance(coord, (int, float)) for coord in bbox):
                    x_min, y_min, x_max, y_max = bbox
                    return {
                        'x': int(x_min),
                        'y': int(y_min),
                        'width': int(x_max - x_min),
                        'height': int(y_max - y_min)
                    }
            
            # Handle polygon format (4 points)
            if hasattr(bbox, '__iter__'):
                bbox_array = np.array(bbox)
                if bbox_array.shape == (4, 2):
                    x_coords = bbox_array[:, 0]
                    y_coords = bbox_array[:, 1]
                    
                    x_min, x_max = int(np.min(x_coords)), int(np.max(x_coords))
                    y_min, y_max = int(np.min(y_coords)), int(np.max(y_coords))
                    
                    return {
                        'x': x_min,
                        'y': y_min,
                        'width': x_max - x_min,
                        'height': y_max - y_min
                    }
            
            return {'x': 0, 'y': 0, 'width': 0, 'height': 0}
            
        except Exception as e:
            logger.warning(f"Error calculating text position: {str(e)}")
            return {'x': 0, 'y': 0, 'width': 0, 'height': 0}
    
    def batch_extract_text(self, image_inputs: List) -> List[List[Dict]]:
        """
        Extract text from multiple images
        
        Args:
            image_inputs: List of image inputs
            
        Returns:
            List of text extraction results for each image
        """
        results = []
        for i, image_input in enumerate(image_inputs):
            try:
                logger.info(f"Processing image {i+1}/{len(image_inputs)}")
                text_results = self.extract_text_from_image(image_input)
                results.append(text_results)
            except Exception as e:
                logger.error(f"Error processing image {i+1}: {str(e)}")
                results.append([])
        
        return results
    
    def get_text_only(self, image_input) -> List[str]:
        """
        Extract only text content (without bounding boxes or confidence)
        
        Args:
            image_input: Image input
            
        Returns:
            List of extracted text strings
        """
        text_results = self.extract_text_from_image(image_input)
        return [result['text'] for result in text_results if result['text'].strip()]
    
    def get_text_with_confidence(self, image_input, min_confidence: float = 0.5) -> List[Dict]:
        """
        Extract text with confidence filtering
        
        Args:
            image_input: Image input
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of text results above confidence threshold
        """
        text_results = self.extract_text_from_image(image_input)
        return [
            result for result in text_results 
            if result['confidence'] >= min_confidence
        ]
    
    def detect_language(self, image_input) -> str:
        """
        Basic language detection based on character patterns
        
        Args:
            image_input: Image input
            
        Returns:
            Detected language code
        """
        try:
            texts = self.get_text_only(image_input)
            combined_text = ' '.join(texts)
            
            # Simple language detection logic
            if any('\u4e00' <= char <= '\u9fff' for char in combined_text):
                return 'ch'  # Chinese
            elif any('\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff' for char in combined_text):
                return 'japan'  # Japanese
            elif any('\uac00' <= char <= '\ud7af' for char in combined_text):
                return 'korean'  # Korean
            else:
                return 'en'  # Default to English
                
        except Exception as e:
            logger.warning(f"Language detection failed: {str(e)}")
            return 'en'
    
    def set_language(self, lang: str):
        """
        Change OCR language and reinitialize
        
        Args:
            lang: New language code
        """
        if lang != self.lang:
            self.lang = lang
            logger.info(f"Changing OCR language to: {lang}")
            self._initialize_ocr()
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported languages
        
        Returns:
            List of supported language codes
        """
        return [
            'ch', 'en', 'fr', 'german', 'korean', 'japan',
            'it', 'xi', 'pu', 'ru', 'ar', 'ta', 'ug', 'fa', 'ur', 'rs',
            'oc', 'rsc', 'bg', 'uk', 'be', 'te', 'kn', 'ch_tra', 'hi',
            'mr', 'ne', 'latin', 'devanagari', 'cyrillic', 'arabic'
        ]
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.ocr:
                # PaddleOCR doesn't have explicit cleanup, but we can set to None
                self.ocr = None
                logger.info("OCR service cleaned up")
        except Exception as e:
            logger.warning(f"Error during cleanup: {str(e)}")
    
    def __del__(self):
        """Destructor"""
        self.cleanup()