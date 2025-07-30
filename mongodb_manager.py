"""
MongoDB Database Manager for Scan2Score
Handles database operations for rubrics, evaluations, and student data
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import pymongo
from pymongo import MongoClient
from bson import ObjectId
import json

logger = logging.getLogger(__name__)

class MongoDBManager:
    """MongoDB database manager for Scan2Score application"""
    
    def __init__(self, connection_string: str, database_name: str):
        """
        Initialize MongoDB connection
        
        Args:
            connection_string: MongoDB connection string
            database_name: Name of the database to use
        """
        self.connection_string = connection_string
        self.database_name = database_name
        self.client = None
        self.db = None
        self._connect()
    
    def _connect(self):
        """Establish connection to MongoDB"""
        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.database_name]
            
            # Test connection
            self.client.admin.command('ping')
            logger.info(f"Successfully connected to MongoDB database: {self.database_name}")
            
            # Create indexes for better performance
            self._create_indexes()
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    def _create_indexes(self):
        """Create database indexes for better query performance"""
        try:
            # Users collection indexes
            self.db.users.create_index("email", unique=True)
            self.db.users.create_index("username", unique=True)
            
            # Rubrics collection indexes
            self.db.rubrics.create_index([("subject", 1), ("question_type", 1)])
            self.db.rubrics.create_index("created_by")
            self.db.rubrics.create_index("created_at")
            
            # Evaluations collection indexes
            self.db.evaluations.create_index("student_id")
            self.db.evaluations.create_index("rubric_id")
            self.db.evaluations.create_index("created_at")
            self.db.evaluations.create_index([("student_id", 1), ("created_at", -1)])
            
            # Submissions collection indexes
            self.db.submissions.create_index("student_id")
            self.db.submissions.create_index("assignment_id")
            self.db.submissions.create_index("created_at")
            
            # Performance analytics indexes
            self.db.student_performance.create_index("student_id")
            self.db.student_performance.create_index([("student_id", 1), ("subject", 1)])
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Error creating indexes: {str(e)}")
    
    def disconnect(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    # User Management
    def create_user(self, user_data: Dict) -> str:
        """
        Create a new user
        
        Args:
            user_data: User information dictionary
            
        Returns:
            User ID as string
        """
        try:
            user_data['created_at'] = datetime.now(timezone.utc)
            user_data['updated_at'] = datetime.now(timezone.utc)
            
            result = self.db.users.insert_one(user_data)
            logger.info(f"Created user with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except pymongo.errors.DuplicateKeyError as e:
            logger.error(f"User already exists: {str(e)}")
            raise ValueError("User with this email or username already exists")
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    def get_user(self, user_id: str = None, email: str = None, username: str = None) -> Optional[Dict]:
        """
        Get user by ID, email, or username
        
        Args:
            user_id: User's ObjectId as string
            email: User's email address
            username: User's username
            
        Returns:
            User dictionary or None if not found
        """
        try:
            query = {}
            if user_id:
                query['_id'] = ObjectId(user_id)
            elif email:
                query['email'] = email
            elif username:
                query['username'] = username
            else:
                raise ValueError("Must provide user_id, email, or username")
            
            user = self.db.users.find_one(query)
            if user:
                user['_id'] = str(user['_id'])
            
            return user
            
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            return None
    
    def update_user(self, user_id: str, update_data: Dict) -> bool:
        """
        Update user information
        
        Args:
            user_id: User's ObjectId as string
            update_data: Data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            update_data['updated_at'] = datetime.now(timezone.utc)
            
            result = self.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            return False
    
    # Rubric Management
    def create_rubric(self, rubric_data: Dict) -> str:
        """
        Create a new grading rubric
        
        Args:
            rubric_data: Rubric information dictionary
            
        Returns:
            Rubric ID as string
        """
        try:
            rubric_data['created_at'] = datetime.now(timezone.utc)
            rubric_data['updated_at'] = datetime.now(timezone.utc)
            
            result = self.db.rubrics.insert_one(rubric_data)
            logger.info(f"Created rubric with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating rubric: {str(e)}")
            raise
    
    def get_rubric(self, rubric_id: str) -> Optional[Dict]:
        """
        Get rubric by ID
        
        Args:
            rubric_id: Rubric's ObjectId as string
            
        Returns:
            Rubric dictionary or None if not found
        """
        try:
            rubric = self.db.rubrics.find_one({'_id': ObjectId(rubric_id)})
            if rubric:
                rubric['_id'] = str(rubric['_id'])
            
            return rubric
            
        except Exception as e:
            logger.error(f"Error getting rubric: {str(e)}")
            return None
    
    def get_rubrics(self, 
                   created_by: str = None,
                   subject: str = None,
                   question_type: str = None,
                   limit: int = 50,
                   skip: int = 0) -> List[Dict]:
        """
        Get rubrics with optional filtering
        
        Args:
            created_by: Filter by creator user ID
            subject: Filter by subject
            question_type: Filter by question type
            limit: Maximum number of results
            skip: Number of results to skip
            
        Returns:
            List of rubric dictionaries
        """
        try:
            query = {}
            if created_by:
                query['created_by'] = created_by
            if subject:
                query['subject'] = subject
            if question_type:
                query['question_type'] = question_type
            
            cursor = self.db.rubrics.find(query).sort('created_at', -1).skip(skip).limit(limit)
            
            rubrics = []
            for rubric in cursor:
                rubric['_id'] = str(rubric['_id'])
                rubrics.append(rubric)
            
            return rubrics
            
        except Exception as e:
            logger.error(f"Error getting rubrics: {str(e)}")
            return []
    
    def update_rubric(self, rubric_id: str, update_data: Dict) -> bool:
        """
        Update rubric information
        
        Args:
            rubric_id: Rubric's ObjectId as string
            update_data: Data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            update_data['updated_at'] = datetime.now(timezone.utc)
            
            result = self.db.rubrics.update_one(
                {'_id': ObjectId(rubric_id)},
                {'$set': update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating rubric: {str(e)}")
            return False
    
    # Submission Management
    def create_submission(self, submission_data: Dict) -> str:
        """
        Create a new student submission
        
        Args:
            submission_data: Submission information dictionary
            
        Returns:
            Submission ID as string
        """
        try:
            submission_data['created_at'] = datetime.now(timezone.utc)
            submission_data['updated_at'] = datetime.now(timezone.utc)
            submission_data['status'] = 'submitted'
            
            result = self.db.submissions.insert_one(submission_data)
            logger.info(f"Created submission with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating submission: {str(e)}")
            raise
    
    def get_submission(self, submission_id: str) -> Optional[Dict]:
        """
        Get submission by ID
        
        Args:
            submission_id: Submission's ObjectId as string
            
        Returns:
            Submission dictionary or None if not found
        """
        try:
            submission = self.db.submissions.find_one({'_id': ObjectId(submission_id)})
            if submission:
                submission['_id'] = str(submission['_id'])
            
            return submission
            
        except Exception as e:
            logger.error(f"Error getting submission: {str(e)}")
            return None
    
    def get_submissions(self,
                       student_id: str = None,
                       assignment_id: str = None,
                       status: str = None,
                       limit: int = 50,
                       skip: int = 0) -> List[Dict]:
        """
        Get submissions with optional filtering
        
        Args:
            student_id: Filter by student ID
            assignment_id: Filter by assignment ID
            status: Filter by status
            limit: Maximum number of results
            skip: Number of results to skip
            
        Returns:
            List of submission dictionaries
        """
        try:
            query = {}
            if student_id:
                query['student_id'] = student_id
            if assignment_id:
                query['assignment_id'] = assignment_id
            if status:
                query['status'] = status
            
            cursor = self.db.submissions.find(query).sort('created_at', -1).skip(skip).limit(limit)
            
            submissions = []
            for submission in cursor:
                submission['_id'] = str(submission['_id'])
                submissions.append(submission)
            
            return submissions
            
        except Exception as e:
            logger.error(f"Error getting submissions: {str(e)}")
            return []
    
    # Evaluation Management
    def create_evaluation(self, evaluation_data: Dict) -> str:
        """
        Create a new evaluation result
        
        Args:
            evaluation_data: Evaluation information dictionary
            
        Returns:
            Evaluation ID as string
        """
        try:
            evaluation_data['created_at'] = datetime.now(timezone.utc)
            evaluation_data['updated_at'] = datetime.now(timezone.utc)
            
            result = self.db.evaluations.insert_one(evaluation_data)
            logger.info(f"Created evaluation with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating evaluation: {str(e)}")
            raise
    
    def get_evaluation(self, evaluation_id: str) -> Optional[Dict]:
        """
        Get evaluation by ID
        
        Args:
            evaluation_id: Evaluation's ObjectId as string
            
        Returns:
            Evaluation dictionary or None if not found
        """
        try:
            evaluation = self.db.evaluations.find_one({'_id': ObjectId(evaluation_id)})
            if evaluation:
                evaluation['_id'] = str(evaluation['_id'])
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error getting evaluation: {str(e)}")
            return None
    
    def get_evaluations(self,
                       student_id: str = None,
                       rubric_id: str = None,
                       submission_id: str = None,
                       limit: int = 50,
                       skip: int = 0) -> List[Dict]:
        """
        Get evaluations with optional filtering
        
        Args:
            student_id: Filter by student ID
            rubric_id: Filter by rubric ID
            submission_id: Filter by submission ID
            limit: Maximum number of results
            skip: Number of results to skip
            
        Returns:
            List of evaluation dictionaries
        """
        try:
            query = {}
            if student_id:
                query['student_id'] = student_id
            if rubric_id:
                query['rubric_id'] = rubric_id
            if submission_id:
                query['submission_id'] = submission_id
            
            cursor = self.db.evaluations.find(query).sort('created_at', -1).skip(skip).limit(limit)
            
            evaluations = []
            for evaluation in cursor:
                evaluation['_id'] = str(evaluation['_id'])
                evaluations.append(evaluation)
            
            return evaluations
            
        except Exception as e:
            logger.error(f"Error getting evaluations: {str(e)}")
            return []
    
    # Student Performance Analytics
    def update_student_performance(self, student_id: str, performance_data: Dict) -> bool:
        """
        Update student performance analytics
        
        Args:
            student_id: Student's ID
            performance_data: Performance metrics to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            performance_data['updated_at'] = datetime.now(timezone.utc)
            
            result = self.db.student_performance.update_one(
                {'student_id': student_id},
                {
                    '$set': performance_data,
                    '$setOnInsert': {'created_at': datetime.now(timezone.utc)}
                },
                upsert=True
            )
            
            return result.upserted_id is not None or result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating student performance: {str(e)}")
            return False
    
    def get_student_performance(self, student_id: str) -> Optional[Dict]:
        """
        Get student performance analytics
        
        Args:
            student_id: Student's ID
            
        Returns:
            Performance dictionary or None if not found
        """
        try:
            performance = self.db.student_performance.find_one({'student_id': student_id})
            if performance:
                performance['_id'] = str(performance['_id'])
            
            return performance
            
        except Exception as e:
            logger.error(f"Error getting student performance: {str(e)}")
            return None
    
    def get_class_performance_stats(self, 
                                  subject: str = None,
                                  assignment_id: str = None,
                                  date_from: datetime = None,
                                  date_to: datetime = None) -> Dict:
        """
        Get aggregated class performance statistics
        
        Args:
            subject: Filter by subject
            assignment_id: Filter by assignment
            date_from: Start date for filtering
            date_to: End date for filtering
            
        Returns:
            Aggregated statistics dictionary
        """
        try:
            pipeline = []
            
            # Build match stage
            match_stage = {}
            if subject:
                match_stage['subject'] = subject
            if assignment_id:
                match_stage['assignment_id'] = assignment_id
            if date_from or date_to:
                date_filter = {}
                if date_from:
                    date_filter['$gte'] = date_from
                if date_to:
                    date_filter['$lte'] = date_to
                match_stage['created_at'] = date_filter
            
            if match_stage:
                pipeline.append({'$match': match_stage})
            
            # Add aggregation stages
            pipeline.extend([
                {
                    '$group': {
                        '_id': None,
                        'total_evaluations': {'$sum': 1},
                        'average_score': {'$avg': '$total_score'},
                        'max_score': {'$max': '$total_score'},
                        'min_score': {'$min': '$total_score'},
                        'total_possible_score': {'$first': '$max_possible_score'}
                    }
                },
                {
                    '$project': {
                        '_id': 0,
                        'total_evaluations': 1,
                        'average_score': {'$round': ['$average_score', 2]},
                        'max_score': 1,
                        'min_score': 1,
                        'total_possible_score': 1,
                        'average_percentage': {
                            '$round': [
                                {'$multiply': [
                                    {'$divide': ['$average_score', '$total_possible_score']},
                                    100
                                ]}, 2
                            ]
                        }
                    }
                }
            ])
            
            result = list(self.db.evaluations.aggregate(pipeline))
            
            if result:
                return result[0]
            else:
                return {
                    'total_evaluations': 0,
                    'average_score': 0,
                    'max_score': 0,
                    'min_score': 0,
                    'average_percentage': 0
                }
                
        except Exception as e:
            logger.error(f"Error getting class performance stats: {str(e)}")
            return {}
    
    # Utility Methods
    def get_collection_stats(self) -> Dict:
        """
        Get database collection statistics
        
        Returns:
            Dictionary with collection counts and sizes
        """
        try:
            stats = {}
            collections = ['users', 'rubrics', 'submissions', 'evaluations', 'student_performance']
            
            for collection_name in collections:
                collection = self.db[collection_name]
                stats[collection_name] = {
                    'count': collection.count_documents({}),
                    'size_bytes': self.db.command('collStats', collection_name).get('size', 0)
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {}
    
    def backup_collection(self, collection_name: str, output_file: str) -> bool:
        """
        Backup a collection to JSON file
        
        Args:
            collection_name: Name of collection to backup
            output_file: Output file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            collection = self.db[collection_name]
            documents = list(collection.find())
            
            # Convert ObjectId to string for JSON serialization
            for doc in documents:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
            
            with open(output_file, 'w') as f:
                json.dump(documents, f, default=str, indent=2)
            
            logger.info(f"Backed up {len(documents)} documents from {collection_name} to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error backing up collection {collection_name}: {str(e)}")
            return False