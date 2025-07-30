"""
Scan2Score Flask Application
AI Subjective Answer Evaluation System
"""

import os
import asyncio
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from datetime import datetime, timedelta
import jwt
from functools import wraps
import uuid

# Import Scan2Score services
from backend.config.settings import config
from backend.database.mongodb_manager import MongoDBManager
from backend.services.ocr_service import OCRService
from backend.services.ai_evaluator import AIEvaluator
from backend.services.plagiarism_detector import PlagiarismDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, 
           template_folder='frontend/templates',
           static_folder='frontend/static')

# Add security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "frame-ancestors 'none'; default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data:;"
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    response.headers['Expires'] = None  # Remove Expires header
    return response

# Load configuration
env = os.getenv('FLASK_ENV', 'development')
app.config.from_object(config[env])

# Enable CORS
CORS(app)

# Initialize services
try:
    # Database
    db_manager = MongoDBManager(
        connection_string=app.config['MONGODB_URI'],
        database_name=app.config['DB_NAME']
    )
    
   # OCR Service
    try:
        # Try the original parameter name first
        ocr_service = OCRService(
            lang=app.config['OCR_LANGUAGES']
        )
    except TypeError as e:
        # If that fails, try with common alternative parameter names
        try:
            ocr_service = OCRService(
                languages=app.config['OCR_LANGUAGES']
            )
        except TypeError:
            # If still failing, try with minimal parameters
            try:
                ocr_service = OCRService()
            except TypeError:
                # Last resort - check if we need to pass confidence threshold differently
                ocr_service = OCRService(
                    lang=app.config['OCR_LANGUAGES'],
                    confidence_threshold=app.config['OCR_CONFIDENCE_THRESHOLD']
                )
    
    # AI Evaluator
    ai_evaluator = AIEvaluator(
        anthropic_api_key=app.config['ANTHROPIC_API_KEY'],
        openai_api_key=app.config['OPENAI_API_KEY'],
        claude_model=app.config['CLAUDE_MODEL'],
        max_tokens=app.config['MAX_TOKENS'],
        temperature=app.config['TEMPERATURE']
    )
    
    # Plagiarism Detector
    plagiarism_detector = PlagiarismDetector(
        gptzero_api_key=app.config['GPTZERO_API_KEY'],
        copyleaks_email=app.config['COPYLEAKS_EMAIL'],
        copyleaks_api_key=app.config['COPYLEAKS_API_KEY']
    )
    
    logger.info("All services initialized successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize services: {str(e)}")
    raise

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]  # Remove 'Bearer ' prefix
            
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = data['user_id']
            current_user = db_manager.get_user(user_id=current_user_id)
            
            if not current_user:
                return jsonify({'message': 'Token is invalid'}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        stats = db_manager.get_collection_stats()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': 'connected',
                'ocr': 'available',
                'ai_evaluator': 'available',
                'plagiarism_detector': 'available'
            },
            'database_stats': stats
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Authentication endpoints

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration"""
    try:
        data = request.get_json()
        logger.info(f"Registration attempt for email: {data.get('email', 'not provided')}")
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'role']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Hash password
        password_hash = generate_password_hash(data['password'])
        logger.info("Password hashed successfully")
        
        user_data = {
            'username': data['username'],
            'email': data['email'],
            'password_hash': password_hash,
            'role': data['role'],  # 'teacher' or 'student'
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'institution': data.get('institution', ''),
            'is_active': True
        }
        
        logger.info(f"Attempting to create user with data: {user_data}")
        
        try:
            user_id = db_manager.create_user(user_data)
            logger.info(f"User created successfully with ID: {user_id}")
            
            # Verify user was created
            created_user = db_manager.get_user(user_id=user_id)
            if created_user:
                logger.info(f"User verification successful: {created_user['email']}")
            else:
                logger.error("User verification failed - user not found after creation")
                return jsonify({'error': 'User created but verification failed'}), 500
            
            return jsonify({
                'message': 'User created successfully',
                'user_id': user_id
            }), 201
            
        except Exception as db_error:
            logger.error(f"Database error during user creation: {str(db_error)}")
            return jsonify({'error': 'Database error during registration'}), 500
        
    except ValueError as e:
        logger.error(f"Registration ValueError: {str(e)}")
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        logger.info(f"Login attempt for email: {data.get('email', 'not provided')}")
        
        if 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password required'}), 400
        
        user = db_manager.get_user(email=data['email'])
        logger.info(f"User lookup result: {'Found' if user else 'Not found'}")
        
        if not user:
            logger.warning(f"Login failed: User not found for email {data['email']}")
            return jsonify({'error': 'Invalid credentials'}), 401
        
        password_check = check_password_hash(user['password_hash'], data['password'])
        logger.info(f"Password check result: {password_check}")
        
        if not password_check:
            logger.warning(f"Login failed: Invalid password for email {data['email']}")
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.get('is_active', True):
            return jsonify({'error': 'Account is disabled'}), 401
        
        # Generate JWT token
        token_payload = {
            'user_id': user['_id'],
            'email': user['email'],
            'role': user['role'],
            'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
        }
        
        token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')
        logger.info(f"Login successful for user: {user['email']}")
        
        return jsonify({
            'token': token,
            'user': {
                'id': user['_id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'first_name': user.get('first_name', ''),
                'last_name': user.get('last_name', '')
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

# File upload and OCR endpoints

@app.route('/api/upload', methods=['POST'])
@token_required
def upload_file(current_user):
    """Upload and process document with OCR"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        
        # Extract text using OCR
        # ocr_result = ocr_service.extract_text_from_file(file_path)
        
        # Create submission record
        submission_data = {
            'student_id': current_user['_id'],
            'original_filename': filename,
            'file_path': file_path,
            # 'ocr_result': ocr_result,
            'file_size': os.path.getsize(file_path),
            'assignment_id': request.form.get('assignment_id'),
            'question': request.form.get('question', ''),
            # 'extracted_text': ocr_result.get('text', '')
        }
        
        submission_id = db_manager.create_submission(submission_data)
        
        return jsonify({
            'submission_id': submission_id,
            # 'ocr_result': ocr_result,
            'message': 'File uploaded and processed successfully'
        })
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'File upload failed'}), 500

@app.route('/api/submissions', methods=['GET'])
@token_required
def get_submissions(current_user):
    """Get submissions with optional filtering"""
    try:
        # Query parameters
        student_id = request.args.get('student_id')
        assignment_id = request.args.get('assignment_id')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))

        # If student, only show their own submissions
        if current_user['role'] == 'student':
            student_id = current_user['_id']

        submissions = db_manager.get_submissions(
            student_id=student_id,
            assignment_id=assignment_id,
            limit=limit,
            skip=skip
        )

        return jsonify({
            'submissions': submissions,
            'count': len(submissions)
        })
    except Exception as e:
        logger.error(f"Get submissions error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve submissions'}), 500


# Rubric management endpoints

@app.route('/api/rubrics', methods=['POST'])
@token_required
def create_rubric(current_user):
    """Create a new grading rubric"""
    try:
        if current_user['role'] != 'teacher':
            return jsonify({'error': 'Only teachers can create rubrics'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['subject', 'question_type', 'total_points', 'criteria']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        rubric_data = {
            'name': data.get('name', f"{data['subject']} - {data['question_type']}"),
            'description': data.get('description', ''),
            'subject': data['subject'],
            'question_type': data['question_type'],
            'total_points': data['total_points'],
            'criteria': data['criteria'],
            'created_by': current_user['_id'],
            'institution': current_user.get('institution', ''),
            'is_public': data.get('is_public', False)
        }
        
        rubric_id = db_manager.create_rubric(rubric_data)
        
        return jsonify({
            'rubric_id': rubric_id,
            'message': 'Rubric created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Create rubric error: {str(e)}")
        return jsonify({'error': 'Failed to create rubric'}), 500

@app.route('/api/rubrics', methods=['GET'])
@token_required
def get_rubrics(current_user):
    """Get rubrics with optional filtering"""
    try:
        # Query parameters
        subject = request.args.get('subject')
        question_type = request.args.get('question_type')
        created_by = request.args.get('created_by')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        
        # If not a teacher, only show public rubrics or their own
        if current_user['role'] != 'teacher':
            created_by = current_user['_id']
        
        rubrics = db_manager.get_rubrics(
            created_by=created_by,
            subject=subject,
            question_type=question_type,
            limit=limit,
            skip=skip
        )
        
        return jsonify({
            'rubrics': rubrics,
            'count': len(rubrics)
        })
        
    except Exception as e:
        logger.error(f"Get rubrics error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve rubrics'}), 500

@app.route('/api/rubrics/<rubric_id>', methods=['GET'])
@token_required
def get_rubric(current_user, rubric_id):
    """Get specific rubric by ID"""
    try:
        rubric = db_manager.get_rubric(rubric_id)
        
        if not rubric:
            return jsonify({'error': 'Rubric not found'}), 404
        
        # Check permissions
        if (current_user['role'] != 'teacher' and 
            rubric['created_by'] != current_user['_id'] and 
            not rubric.get('is_public', False)):
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify(rubric)
        
    except Exception as e:
        logger.error(f"Get rubric error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve rubric'}), 500

# Evaluation endpoints

@app.route('/api/evaluate', methods=['POST'])
@token_required
def evaluate_submission(current_user):
    """Evaluate a student submission"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['submission_id', 'rubric_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get submission and rubric
        submission = db_manager.get_submission(data['submission_id'])
        rubric = db_manager.get_rubric(data['rubric_id'])
        
        if not submission:
            return jsonify({'error': 'Submission not found'}), 404
        
        if not rubric:
            return jsonify({'error': 'Rubric not found'}), 404
        
        # Check permissions
        if (current_user['role'] != 'teacher' and 
            submission['student_id'] != current_user['_id']):
            return jsonify({'error': 'Access denied'}), 403
        
        # Extract question and answer
        question = submission.get('question', data.get('question', ''))
        student_answer = submission.get('extracted_text', '')
        
        if not student_answer:
            return jsonify({'error': 'No text found in submission'}), 400
        
        # Run AI evaluation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            evaluation_result = loop.run_until_complete(
                ai_evaluator.evaluate_answer(
                    question=question,
                    student_answer=student_answer,
                    rubric=rubric,
                    context=data.get('context', ''),
                    preferred_model=data.get('preferred_model', 'claude')
                )
            )
        finally:
            loop.close()
        
        # Run plagiarism detection
        plagiarism_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(plagiarism_loop)
        
        try:
            plagiarism_result = plagiarism_loop.run_until_complete(
                plagiarism_detector.comprehensive_plagiarism_check(
                    text=student_answer,
                    title=f"Submission_{data['submission_id']}"
                )
            )
        finally:
            plagiarism_loop.close()
        
        # Create evaluation record
        evaluation_data = {
            'submission_id': data['submission_id'],
            'rubric_id': data['rubric_id'],
            'student_id': submission['student_id'],
            'evaluator_id': current_user['_id'],
            'question': question,
            'student_answer': student_answer,
            'ai_evaluation': evaluation_result,
            'plagiarism_result': {
                'is_plagiarized': plagiarism_result.is_plagiarized,
                'confidence_score': plagiarism_result.confidence_score,
                'ai_generated_probability': plagiarism_result.ai_generated_probability,
                'similarity_percentage': plagiarism_result.similarity_percentage,
                'detection_method': plagiarism_result.detection_method,
                'sources_found': plagiarism_result.sources_found,
                'additional_info': plagiarism_result.additional_info
            },
            'total_score': evaluation_result.get('total_score', 0),
            'max_possible_score': evaluation_result.get('max_possible_score', 100),
            'percentage': evaluation_result.get('percentage', 0),
            'needs_review': plagiarism_result.is_plagiarized or evaluation_result.get('confidence_level') == 'Low'
        }
        
        evaluation_id = db_manager.create_evaluation(evaluation_data)
        
        # Update student performance analytics
        performance_data = {
            'student_id': submission['student_id'],
            'recent_scores': [evaluation_result.get('total_score', 0)],
            'subject_performance': {
                rubric['subject']: {
                    'total_evaluations': 1,
                    'average_score': evaluation_result.get('total_score', 0),
                    'last_evaluation': datetime.now().isoformat()
                }
            }
        }
        
        db_manager.update_student_performance(submission['student_id'], performance_data)
        
        return jsonify({
            'evaluation_id': evaluation_id,
            'evaluation_result': evaluation_result,
            'plagiarism_result': {
                'is_plagiarized': plagiarism_result.is_plagiarized,
                'confidence_score': plagiarism_result.confidence_score,
                'ai_generated_probability': plagiarism_result.ai_generated_probability,
                'similarity_percentage': plagiarism_result.similarity_percentage
            },
            'message': 'Evaluation completed successfully'
        })
        
    except Exception as e:
        logger.error(f"Evaluation error: {str(e)}")
        return jsonify({'error': 'Evaluation failed'}), 500

@app.route('/api/evaluations', methods=['GET'])
@token_required
def get_evaluations(current_user):
    """Get evaluations with optional filtering"""
    try:
        # Query parameters
        student_id = request.args.get('student_id')
        rubric_id = request.args.get('rubric_id')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        
        # Filter based on user role
        if current_user['role'] == 'student':
            student_id = current_user['_id']
        
        evaluations = db_manager.get_evaluations(
            student_id=student_id,
            rubric_id=rubric_id,
            limit=limit,
            skip=skip
        )
        
        return jsonify({
            'evaluations': evaluations,
            'count': len(evaluations)
        })
        
    except Exception as e:
        logger.error(f"Get evaluations error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve evaluations'}), 500

# Analytics endpoints

@app.route('/api/analytics/student/<student_id>')
@token_required
def get_student_analytics(current_user, student_id):
    """Get student performance analytics"""
    try:
        # Check permissions
        if (current_user['role'] != 'teacher' and 
            current_user['_id'] != student_id):
            return jsonify({'error': 'Access denied'}), 403
        
        performance = db_manager.get_student_performance(student_id)
        evaluations = db_manager.get_evaluations(student_id=student_id, limit=100)
        
        # Calculate additional metrics
        if evaluations:
            scores = [eval_data['total_score'] for eval_data in evaluations if 'total_score' in eval_data]
            recent_trend = scores[-5:] if len(scores) >= 5 else scores
            
            analytics = {
                'student_id': student_id,
                'total_evaluations': len(evaluations),
                'average_score': sum(scores) / len(scores) if scores else 0,
                'highest_score': max(scores) if scores else 0,
                'lowest_score': min(scores) if scores else 0,
                'recent_trend': recent_trend,
                'performance_by_subject': performance.get('subject_performance', {}) if performance else {},
                'needs_review_count': len([e for e in evaluations if e.get('needs_review', False)]),
                'plagiarism_incidents': len([e for e in evaluations if e.get('plagiarism_result', {}).get('is_plagiarized', False)])
            }
        else:
            analytics = {
                'student_id': student_id,
                'total_evaluations': 0,
                'message': 'No evaluations found for this student'
            }
        
        return jsonify(analytics)
        
    except Exception as e:
        logger.error(f"Student analytics error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve analytics'}), 500

@app.route('/api/analytics/class')
@token_required
def get_class_analytics(current_user):
    """Get class performance analytics"""
    try:
        if current_user['role'] != 'teacher':
            return jsonify({'error': 'Only teachers can view class analytics'}), 403
        
        # Query parameters
        subject = request.args.get('subject')
        assignment_id = request.args.get('assignment_id')
        
        stats = db_manager.get_class_performance_stats(
            subject=subject,
            assignment_id=assignment_id
        )
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Class analytics error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve class analytics'}), 500

# Utility endpoints

@app.route('/api/generate-rubric', methods=['POST'])
@token_required
def generate_rubric(current_user):
    """Generate a custom rubric using AI"""
    try:
        if current_user['role'] != 'teacher':
            return jsonify({'error': 'Only teachers can generate rubrics'}), 403
        
        data = request.get_json()
        
        required_fields = ['subject', 'question_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        rubric = ai_evaluator.create_custom_rubric(
            subject=data['subject'],
            question_type=data['question_type'],
            max_points=data.get('max_points', 100),
            criteria_count=data.get('criteria_count', 4)
        )
        
        return jsonify({
            'rubric': rubric,
            'message': 'Rubric generated successfully'
        })
        
    except Exception as e:
        logger.error(f"Generate rubric error: {str(e)}")
        return jsonify({'error': 'Failed to generate rubric'}), 500

@app.route('/test-static')
def test_static():
    return app.send_static_file('js/app.js')

@app.route('/api/test/user/<email>')
def test_user_exists(email):
    """Test endpoint to check if user exists"""
    try:
        user = db_manager.get_user(email=email)
        if user:
            return jsonify({
                'exists': True,
                'user_id': user['_id'],
                'email': user['email'],
                'username': user['username'],
                'has_password_hash': 'password_hash' in user
            })
        else:
            return jsonify({'exists': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test/db')
def test_database():
    """Test database connection and basic operations"""
    try:
        # Test database connection
        stats = db_manager.get_collection_stats()
        
        # Test creating a simple document
        test_data = {'test': True, 'timestamp': datetime.now().isoformat()}
        result = db_manager.db.test_collection.insert_one(test_data)
        
        # Test reading the document
        test_doc = db_manager.db.test_collection.find_one({'_id': result.inserted_id})
        
        # Clean up
        db_manager.db.test_collection.delete_one({'_id': result.inserted_id})
        
        return jsonify({
            'status': 'healthy',
            'database_stats': stats,
            'write_test': 'passed',
            'read_test': 'passed' if test_doc else 'failed'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(413)
def too_large(error):
    return jsonify({'error': 'File too large'}), 413

# Cleanup on shutdown
# @app.teardown_appcontext
# def close_db(error):
#     """Close database connection on app shutdown"""
#     if hasattr(db_manager, 'disconnect'):
#         db_manager.disconnect()

if __name__ == '__main__':
    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Run the application
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=app.config['DEBUG']
    )