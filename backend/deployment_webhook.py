#!/usr/bin/env python3
"""
Webhook-based deployment system for Social Media Manager
Handles automatic deployments when GitHub webhook is triggered
"""

import os
import sys
import json
import hmac
import hashlib
import subprocess
import logging
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'your_webhook_secret_here')
PROJECT_PATH = '/opt/social-media'
BACKEND_PATH = '/opt/social-media/backend'
LOG_FILE = '/var/log/deployment-webhook.log'

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def verify_signature(payload_body, signature_header):
    """Verify GitHub webhook signature"""
    if not signature_header:
        return False
    
    sha_name, signature = signature_header.split('=')
    if sha_name != 'sha256':
        return False
    
    mac = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload_body,
        hashlib.sha256
    )
    return hmac.compare_digest(mac.hexdigest(), signature)

def run_command(command, cwd=None):
    """Run shell command and return result"""
    try:
        logger.info(f"Running command: {command}")
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            executable='/bin/bash'  # Use bash instead of sh for source command
        )
        
        if result.returncode == 0:
            logger.info(f"Command succeeded: {result.stdout}")
            return True, result.stdout
        else:
            logger.error(f"Command failed: {result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {command}")
        return False, "Command timed out"
    except Exception as e:
        logger.error(f"Command error: {str(e)}")
        return False, str(e)

def deploy_application():
    """Execute deployment steps"""
    deployment_steps = [
        {
            'name': 'Git Stash Local Changes',
            'command': 'git stash',
            'cwd': PROJECT_PATH
        },
        {
            'name': 'Git Pull',
            'command': 'git pull origin master',
            'cwd': PROJECT_PATH
        },
        {
            'name': 'Install Dependencies',
            'command': 'source venv/bin/activate && pip install -r requirements.txt',
            'cwd': BACKEND_PATH
        },
        {
            'name': 'Run Migrations',
            'command': 'source venv/bin/activate && set -a && source .env && set +a && python manage.py migrate',
            'cwd': BACKEND_PATH
        },
        {
            'name': 'Collect Static Files',
            'command': 'source venv/bin/activate && set -a && source .env && set +a && python manage.py collectstatic --noinput',
            'cwd': BACKEND_PATH
        },
        {
            'name': 'Restart Gunicorn Service',
            'command': 'systemctl restart social-api-gunicorn',
            'cwd': None
        },
        {
            'name': 'Restart Celery Worker Service',
            'command': 'systemctl restart social-api-celery-worker',
            'cwd': None
        },
        {
            'name': 'Restart Celery Beat Service',
            'command': 'systemctl restart social-api-celery-beat',
            'cwd': None
        }
    ]
    
    deployment_log = []
    
    for step in deployment_steps:
        logger.info(f"Executing: {step['name']}")
        success, output = run_command(step['command'], step['cwd'])
        
        step_result = {
            'step': step['name'],
            'success': success,
            'output': output[:500] if output else '',  # Limit output length
            'timestamp': datetime.now().isoformat()
        }
        
        deployment_log.append(step_result)
        
        if not success and step['name'] not in ['Restart Gunicorn Service', 'Restart Celery Worker Service', 'Restart Celery Beat Service', 'Git Stash Local Changes']:
            logger.error(f"Deployment failed at step: {step['name']}")
            return False, deployment_log
    
    # Verify deployment
    logger.info("Verifying deployment...")
    success, output = run_command('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8002/api/social/platforms/')
    
    if success and '401' in output:  # 401 is expected for unauthenticated request
        logger.info("Deployment verification successful")
        deployment_log.append({
            'step': 'Verification',
            'success': True,
            'output': 'API responding correctly',
            'timestamp': datetime.now().isoformat()
        })
        return True, deployment_log
    else:
        logger.error(f"Deployment verification failed: {output}")
        deployment_log.append({
            'step': 'Verification',
            'success': False,
            'output': f'API not responding: {output}',
            'timestamp': datetime.now().isoformat()
        })
        return False, deployment_log

@app.route('/webhook/deploy', methods=['POST'])
def webhook_deploy():
    """Handle GitHub webhook for deployment"""
    try:
        # Verify signature
        signature = request.headers.get('X-Hub-Signature-256')
        if not verify_signature(request.data, signature):
            logger.warning("Invalid webhook signature")
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse payload
        payload = request.get_json()
        
        # Check if this is a push to master branch
        if payload.get('ref') != 'refs/heads/master':
            logger.info(f"Ignoring push to {payload.get('ref')}")
            return jsonify({'message': 'Not a master branch push, ignoring'}), 200
        
        # Log deployment start
        logger.info(f"Starting deployment for commit: {payload.get('head_commit', {}).get('id', 'unknown')}")
        logger.info(f"Commit message: {payload.get('head_commit', {}).get('message', 'unknown')}")
        
        # Execute deployment
        success, deployment_log = deploy_application()
        
        response = {
            'success': success,
            'message': 'Deployment completed successfully' if success else 'Deployment failed',
            'timestamp': datetime.now().isoformat(),
            'commit': payload.get('head_commit', {}).get('id', 'unknown'),
            'deployment_log': deployment_log
        }
        
        if success:
            logger.info("Deployment completed successfully")
            return jsonify(response), 200
        else:
            logger.error("Deployment failed")
            return jsonify(response), 500
            
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/status', methods=['GET'])
def webhook_status():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'project_path': PROJECT_PATH
    })

if __name__ == '__main__':
    # Run the webhook server
    app.run(host='127.0.0.1', port=5001, debug=False)