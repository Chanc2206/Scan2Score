/**
 * Scan2Score Frontend Application
 * JavaScript for AI Subjective Answer Evaluation System
 */

// Global variables
let authToken = localStorage.getItem('authToken');
let currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
let currentSection = 'dashboard';

// API base URL
const API_BASE_URL = window.location.origin + '/api';

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    // Debug: Log when DOM is loaded
    console.log('DOM fully loaded and parsed');
    if (authToken) {
        showUserInterface();
        loadDashboard();
    }
});

/**
 * Initialize application
 */
function initializeApp() {
    // Setup navigation
    setupNavigation();
    
    // Setup drag and drop for file upload
    setupFileUpload();
    
    // Load initial data
    checkSystemHealth();
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-link[data-section]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const section = this.dataset.section;
            switchSection(section);
        });
    });
    
    // Forms
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    document.getElementById('registerForm').addEventListener('submit', handleRegister);
    document.getElementById('uploadForm').addEventListener('submit', function(e) {
        console.log('Upload form submitted');
        handleFileUpload(e);
    });
    
    // File upload
    document.getElementById('fileUpload').addEventListener('change', function() {
        handleFileSelect(this);
    });
    document.getElementById('fileUpload').addEventListener('click', function() {
        console.log('File input clicked');
    });
    
    // Filters
    document.getElementById('subjectFilter')?.addEventListener('change', filterRubrics);
    document.getElementById('typeFilter')?.addEventListener('change', filterRubrics);
}

/**
 * Setup navigation
 */
function setupNavigation() {
    // Update active nav link
    function updateActiveNav(activeSection) {
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        
        const activeLink = document.querySelector(`.nav-link[data-section="${activeSection}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
    }
    
    // Switch sections
    window.switchSection = function(section) {
        // Hide all sections
        document.querySelectorAll('.content-section').forEach(sec => {
            sec.style.display = 'none';
        });
        
        // Show selected section
        const targetSection = document.getElementById(`${section}-section`);
        if (targetSection) {
            targetSection.style.display = 'block';
            currentSection = section;
            updateActiveNav(section);
            
            // Load section-specific data
            loadSectionData(section);
        }
    };
}

/**
 * Load section-specific data
 */
function loadSectionData(section) {
    switch (section) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'rubrics':
            loadRubrics();
            break;
        case 'evaluations':
            loadEvaluations();
            break;
        case 'analytics':
            loadAnalytics();
            break;
    }
}

/**
 * Authentication functions
 */
async function handleLogin(e) {
    e.preventDefault();
    
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    
    console.log('Login attempt with email:', email);
    
    try {
        console.log('Sending login request...');
        const response = await apiCall('/auth/login', 'POST', {
            email,
            password
        });
        
        console.log('Login response:', response);
        
        if (response.token) {
            authToken = response.token;
            currentUser = response.user;
            
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            
            // Close modal
            const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
            loginModal.hide();
            
            // Show user interface
            showUserInterface();
            loadDashboard();
            
            showNotification('Login successful!', 'success');
        }
    } catch (error) {
        console.error('Login error:', error);
        showNotification('Login failed: ' + error.message, 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    
    const formData = {
        first_name: document.getElementById('registerFirstName').value,
        last_name: document.getElementById('registerLastName').value,
        username: document.getElementById('registerUsername').value,
        email: document.getElementById('registerEmail').value,
        password: document.getElementById('registerPassword').value,
        role: document.getElementById('registerRole').value,
        institution: document.getElementById('registerInstitution').value
    };
    
    console.log('Registration form data:', formData);
    
    try {
        console.log('Sending registration request...');
        const response = await apiCall('/auth/register', 'POST', formData);
        console.log('Registration response:', response);
        
        // Close modal
        const registerModal = bootstrap.Modal.getInstance(document.getElementById('registerModal'));
        registerModal.hide();
        
        // Show login modal
        const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
        loginModal.show();
        
        showNotification('Registration successful! Please login.', 'success');
    } catch (error) {
        console.error('Registration error:', error);
        showNotification('Registration failed: ' + error.message, 'error');
    }
}

function logout() {
    authToken = null;
    currentUser = {};
    
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    
    hideUserInterface();
    showNotification('Logged out successfully', 'info');
}

function showUserInterface() {
    document.getElementById('userDropdown').style.display = 'block';
    document.getElementById('loginButton').style.display = 'none';
    document.getElementById('username').textContent = currentUser.username || 'User';
}

function hideUserInterface() {
    document.getElementById('userDropdown').style.display = 'none';
    document.getElementById('loginButton').style.display = 'block';
    
    // Redirect to dashboard
    switchSection('dashboard');
}

/**
 * File upload functions
 */
function setupFileUpload() {
    const uploadArea = document.querySelector('.upload-area');
    
    // Drag and drop events
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            document.getElementById('fileUpload').files = files;
            handleFileSelect(document.getElementById('fileUpload'));
        }
    });
}

function handleFileSelect(input) {
    const file = input.files[0];
    if (!file) return;
    
    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf', 
                         'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    
    if (!allowedTypes.includes(file.type)) {
        showNotification('Invalid file type. Please upload PNG, JPG, PDF, or DOCX files.', 'error');
        return;
    }
    
    // Validate file size (16MB)
    if (file.size > 16 * 1024 * 1024) {
        showNotification('File too large. Maximum size is 16MB.', 'error');
        return;
    }
    
    // Update UI
    document.getElementById('uploadPlaceholder').style.display = 'none';
    document.getElementById('fileInfo').style.display = 'block';
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
}

async function handleFileUpload(e) {
    e.preventDefault();
    
    if (!authToken) {
        showNotification('Please login to upload files', 'error');
        return;
    }
    
    const fileInput = document.getElementById('fileUpload');
    const file = fileInput.files[0];
    
    if (!file) {
        showNotification('Please select a file to upload', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('question', document.getElementById('questionText').value);
    formData.append('assignment_id', document.getElementById('assignmentId').value);
    
    // Show progress
    showUploadProgress();
    
    try {
        const response = await apiCall('/upload', 'POST', formData, true);
        
        hideUploadProgress();
        showNotification('File uploaded and processed successfully!', 'success');
        
        // Reset form
        document.getElementById('uploadForm').reset();
        document.getElementById('uploadPlaceholder').style.display = 'block';
        document.getElementById('fileInfo').style.display = 'none';
        
        // Refresh data
        loadDashboard();
        
    } catch (error) {
        hideUploadProgress();
        showNotification('Upload failed: ' + error.message, 'error');
    }
}

function showUploadProgress() {
    document.getElementById('uploadProgress').style.display = 'block';
    
    // Simulate progress
    let progress = 0;
    const progressBar = document.querySelector('#uploadProgress .progress-bar');
    const progressStatus = document.getElementById('progressStatus');
    
    const interval = setInterval(() => {
        progress += Math.random() * 20;
        if (progress > 90) progress = 90;
        
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
        
        if (progress < 30) {
            progressStatus.textContent = 'Uploading file...';
        } else if (progress < 60) {
            progressStatus.textContent = 'Processing with OCR...';
        } else {
            progressStatus.textContent = 'Extracting text...';
        }
    }, 500);
    
    // Store interval for cleanup
    window.uploadProgressInterval = interval;
}

function hideUploadProgress() {
    document.getElementById('uploadProgress').style.display = 'none';
    
    if (window.uploadProgressInterval) {
        clearInterval(window.uploadProgressInterval);
    }
}

/**
 * Dashboard functions
 */
async function loadDashboard() {
    if (!authToken) return;
    
    try {
        // Load stats
        await Promise.all([
            loadDashboardStats(),
            loadRecentActivity(),
            checkSystemHealth()
        ]);
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

async function loadDashboardStats() {
    try {
        const [submissions, evaluations, rubrics] = await Promise.all([
            apiCall('/submissions'),
            apiCall('/evaluations'),
            apiCall('/rubrics')
        ]);
        
        // Update stats cards
        document.getElementById('totalSubmissions').textContent = submissions.count || 0;
        document.getElementById('totalEvaluations').textContent = evaluations.count || 0;
        document.getElementById('totalRubrics').textContent = rubrics.count || 0;
        
        // Calculate average score
        if (evaluations.evaluations && evaluations.evaluations.length > 0) {
            const scores = evaluations.evaluations.map(eval => eval.percentage || 0);
            const average = scores.reduce((a, b) => a + b, 0) / scores.length;
            document.getElementById('averageScore').textContent = Math.round(average) + '%';
        } else {
            document.getElementById('averageScore').textContent = 'N/A';
        }
        
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadRecentActivity() {
    try {
        const evaluations = await apiCall('/evaluations?limit=10');
        const activityHtml = generateRecentActivityHtml(evaluations.evaluations || []);
        document.getElementById('recentActivity').innerHTML = activityHtml;
    } catch (error) {
        document.getElementById('recentActivity').innerHTML = 
            '<p class="text-muted">Unable to load recent activity</p>';
    }
}

function generateRecentActivityHtml(evaluations) {
    if (evaluations.length === 0) {
        return '<p class="text-muted">No recent activity</p>';
    }
    
    return evaluations.map(evaluation => {
        const date = new Date(evaluation.created_at).toLocaleDateString();
        const score = evaluation.percentage || 0;
        const statusColor = score >= 70 ? 'success' : score >= 50 ? 'warning' : 'danger';
        
        return `
            <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                <div>
                    <strong>Evaluation</strong>
                    <small class="text-muted d-block">${date}</small>
                </div>
                <span class="badge bg-${statusColor}">${score}%</span>
            </div>
        `;
    }).join('');
}

/**
 * System health check
 */
async function checkSystemHealth() {
    try {
        const health = await apiCall('/health');
        const statusHtml = generateSystemStatusHtml(health);
        document.getElementById('systemStatus').innerHTML = statusHtml;
    } catch (error) {
        document.getElementById('systemStatus').innerHTML = `
            <div class="text-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                System check failed
            </div>
        `;
    }
}

function generateSystemStatusHtml(health) {
    const services = health.services || {};
    const status = health.status === 'healthy' ? 'success' : 'danger';
    
    return `
        <div class="mb-3">
            <span class="badge bg-${status}">
                <i class="fas fa-${health.status === 'healthy' ? 'check' : 'times'} me-1"></i>
                ${health.status.toUpperCase()}
            </span>
        </div>
        <div class="small">
            ${Object.entries(services).map(([service, status]) => 
                `<div class="d-flex justify-content-between">
                    <span>${service}:</span>
                    <span class="text-${status === 'connected' || status === 'available' ? 'success' : 'danger'}">
                        ${status}
                    </span>
                </div>`
            ).join('')}
        </div>
    `;
}

/**
 * Rubrics functions
 */
async function loadRubrics() {
    if (!authToken) return;
    
    try {
        const response = await apiCall('/rubrics');
        const rubricsHtml = generateRubricsTableHtml(response.rubrics || []);
        document.getElementById('rubricsTable').innerHTML = rubricsHtml;
        
        // Populate subject filter
        populateSubjectFilter(response.rubrics || []);
        
    } catch (error) {
        document.getElementById('rubricsTable').innerHTML = 
            '<p class="text-muted">Unable to load rubrics</p>';
    }
}

function generateRubricsTableHtml(rubrics) {
    if (rubrics.length === 0) {
        return '<p class="text-muted">No rubrics found</p>';
    }
    
    return `
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Subject</th>
                        <th>Type</th>
                        <th>Points</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${rubrics.map(rubric => `
                        <tr>
                            <td><strong>${rubric.name || 'Untitled'}</strong></td>
                            <td><span class="badge bg-primary">${rubric.subject}</span></td>
                            <td>${rubric.question_type}</td>
                            <td>${rubric.total_points}</td>
                            <td>${new Date(rubric.created_at).toLocaleDateString()}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary" onclick="viewRubric('${rubric._id}')">
                                    <i class="fas fa-eye"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-success" onclick="useRubric('${rubric._id}')">
                                    <i class="fas fa-play"></i>
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function populateSubjectFilter(rubrics) {
    const subjects = [...new Set(rubrics.map(r => r.subject))];
    const subjectFilter = document.getElementById('subjectFilter');
    
    // Clear existing options except first
    while (subjectFilter.children.length > 1) {
        subjectFilter.removeChild(subjectFilter.lastChild);
    }
    
    subjects.forEach(subject => {
        const option = document.createElement('option');
        option.value = subject;
        option.textContent = subject;
        subjectFilter.appendChild(option);
    });
}

function filterRubrics() {
    // Implementation for filtering rubrics
    loadRubrics(); // For now, just reload
}

/**
 * Evaluations functions
 */
async function loadEvaluations() {
    if (!authToken) return;
    
    try {
        const response = await apiCall('/evaluations');
        const evaluationsHtml = generateEvaluationsTableHtml(response.evaluations || []);
        document.getElementById('evaluationsTable').innerHTML = evaluationsHtml;
    } catch (error) {
        document.getElementById('evaluationsTable').innerHTML = 
            '<p class="text-muted">Unable to load evaluations</p>';
    }
}

function generateEvaluationsTableHtml(evaluations) {
    if (evaluations.length === 0) {
        return '<p class="text-muted">No evaluations found</p>';
    }
    
    return `
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Score</th>
                        <th>Percentage</th>
                        <th>Plagiarism</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${evaluations.map(evaluation => {
                        const score = evaluation.total_score || 0;
                        const maxScore = evaluation.max_possible_score || 100;
                        const percentage = evaluation.percentage || 0;
                        const plagiarized = evaluation.plagiarism_result?.is_plagiarized || false;
                        const needsReview = evaluation.needs_review || false;
                        
                        return `
                            <tr>
                                <td>${new Date(evaluation.created_at).toLocaleDateString()}</td>
                                <td>${score}/${maxScore}</td>
                                <td>
                                    <span class="badge bg-${percentage >= 70 ? 'success' : percentage >= 50 ? 'warning' : 'danger'}">
                                        ${percentage}%
                                    </span>
                                </td>
                                <td>
                                    <span class="badge bg-${plagiarized ? 'danger' : 'success'}">
                                        ${plagiarized ? 'Detected' : 'Clean'}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge bg-${needsReview ? 'warning' : 'success'}">
                                        ${needsReview ? 'Review' : 'Complete'}
                                    </span>
                                </td>
                                <td>
                                    <button class="btn btn-sm btn-outline-primary" onclick="viewEvaluation('${evaluation._id}')">
                                        <i class="fas fa-eye"></i>
                                    </button>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

/**
 * Analytics functions
 */
async function loadAnalytics() {
    if (!authToken) return;
    
    try {
        const studentId = currentUser.role === 'student' ? currentUser.id : null;
        
        if (studentId) {
            const analytics = await apiCall(`/analytics/student/${studentId}`);
            displayStudentAnalytics(analytics);
        } else {
            const classAnalytics = await apiCall('/analytics/class');
            displayClassAnalytics(classAnalytics);
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

function displayStudentAnalytics(analytics) {
    // Display charts and metrics
    createScoreTrendsChart(analytics.recent_trend || []);
    createSubjectPerformanceChart(analytics.performance_by_subject || {});
    
    // Update performance metrics
    const metricsHtml = `
        <div class="row g-4">
            <div class="col-md-3">
                <div class="performance-metric">
                    <div class="metric-value">${analytics.total_evaluations || 0}</div>
                    <div class="metric-label">Total Evaluations</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="performance-metric">
                    <div class="metric-value">${Math.round(analytics.average_score || 0)}%</div>
                    <div class="metric-label">Average Score</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="performance-metric">
                    <div class="metric-value">${analytics.highest_score || 0}</div>
                    <div class="metric-label">Highest Score</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="performance-metric">
                    <div class="metric-value">${analytics.plagiarism_incidents || 0}</div>
                    <div class="metric-label">Plagiarism Incidents</div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('performanceMetrics').innerHTML = metricsHtml;
}

function createScoreTrendsChart(trendData) {
    const ctx = document.getElementById('scoreTrendsChart').getContext('2d');
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: trendData.map((_, index) => `Eval ${index + 1}`),
            datasets: [{
                label: 'Score Trend',
                data: trendData,
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
}

function createSubjectPerformanceChart(subjectData) {
    const ctx = document.getElementById('subjectPerformanceChart').getContext('2d');
    
    const subjects = Object.keys(subjectData);
    const scores = subjects.map(subject => 
        Math.round(subjectData[subject].average_score || 0)
    );
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: subjects,
            datasets: [{
                data: scores,
                backgroundColor: [
                    '#007bff',
                    '#28a745',
                    '#ffc107',
                    '#dc3545',
                    '#17a2b8'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

/**
 * Utility functions
 */
async function apiCall(endpoint, method = 'GET', data = null, isFormData = false) {
    const config = {
        method,
        headers: {}
    };
    
    if (authToken) {
        config.headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    if (data) {
        if (isFormData) {
            config.body = data;
        } else {
            config.headers['Content-Type'] = 'application/json';
            config.body = JSON.stringify(data);
        }
    }
    
    console.log('API Call:', method, API_BASE_URL + endpoint);
    console.log('Request config:', config);
    
    const response = await fetch(API_BASE_URL + endpoint, config);
    
    console.log('Response status:', response.status);
    console.log('Response headers:', response.headers);
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('Error response:', errorData);
        throw new Error(errorData.error || `HTTP ${response.status}`);
    }
    
    const result = await response.json();
    console.log('Response data:', result);
    return result;
}

function showNotification(message, type = 'info') {
    const toast = document.getElementById('notificationToast');
    const toastTitle = document.getElementById('toastTitle');
    const toastBody = document.getElementById('toastBody');
    
    // Set colors based on type
    const colors = {
        success: 'text-bg-success',
        error: 'text-bg-danger',
        warning: 'text-bg-warning',
        info: 'text-bg-info'
    };
    
    toast.className = `toast ${colors[type] || colors.info}`;
    toastTitle.textContent = type.charAt(0).toUpperCase() + type.slice(1);
    toastBody.textContent = message;
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Global functions for event handlers
window.refreshDashboard = loadDashboard;
window.refreshEvaluations = loadEvaluations;
window.logout = logout;
window.handleFileSelect = handleFileSelect;

// Placeholder functions for missing functionality
window.generateRubric = function() {
    showNotification('AI Rubric Generation coming soon!', 'info');
};

window.viewRubric = function(rubricId) {
    showNotification('Viewing rubric: ' + rubricId, 'info');
};

window.useRubric = function(rubricId) {
    showNotification('Using rubric for evaluation: ' + rubricId, 'info');
};

window.viewEvaluation = function(evaluationId) {
    showNotification('Viewing evaluation: ' + evaluationId, 'info');
};