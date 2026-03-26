#!/usr/bin/env python3
"""
MemOS Exchange API - 项目交换区协作 API
允许 Claude 和其他 AI 助手通过 API 操作 GitHub 仓库
"""

from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()

# 认证
auth = HTTPTokenAuth(scheme='Bearer')

# 配置
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
REPO_OWNER = 'TheMrxk'
REPO_NAME = 'memos-exchange'
GITHUB_API = 'https://api.github.com'

# 允许的 AI 助手
ALLOWED_ASSISTANTS = {
    'claude': 'claude-api-key-here',
    'he-laoshi': 'he-laoshi-api-key-here'
}

@auth.verify_token
def verify_token(token):
    """验证 API Token"""
    return token in ALLOWED_ASSISTANTS.values()

# ============ 工具函数 ============

def github_request(method, endpoint, data=None):
    """发送 GitHub API 请求"""
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    url = f'{GITHUB_API}/{endpoint}'
    
    response = requests.request(method, url, headers=headers, json=data)
    return response.json()

def get_repo_contents(path=''):
    """获取仓库文件内容"""
    endpoint = f'repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}'
    return github_request('GET', endpoint)

def create_file(path, content, message, branch='main'):
    """创建文件"""
    endpoint = f'repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}'
    data = {
        'message': message,
        'content': content,
        'branch': branch
    }
    return github_request('PUT', endpoint, data)

def update_file(path, content, message, sha, branch='main'):
    """更新文件"""
    endpoint = f'repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}'
    data = {
        'message': message,
        'content': content,
        'sha': sha,
        'branch': branch
    }
    return github_request('PUT', endpoint, data)

def delete_file(path, message, sha, branch='main'):
    """删除文件"""
    endpoint = f'repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}'
    data = {
        'message': message,
        'sha': sha,
        'branch': branch
    }
    return github_request('DELETE', endpoint, data)

def create_issue(title, body, labels=None):
    """创建 Issue"""
    endpoint = f'repos/{REPO_OWNER}/{REPO_NAME}/issues'
    data = {
        'title': title,
        'body': body,
        'labels': labels or []
    }
    return github_request('POST', endpoint, data)

def create_pull_request(title, body, head, base='main'):
    """创建 Pull Request"""
    endpoint = f'repos/{REPO_OWNER}/{REPO_NAME}/pulls'
    data = {
        'title': title,
        'body': body,
        'head': head,
        'base': base
    }
    return github_request('POST', endpoint, data)

# ============ API 路由 ============

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'MemOS Exchange API'
    })

@app.route('/api/repo/info', methods=['GET'])
@auth.login_required
def get_repo_info():
    """获取仓库信息"""
    endpoint = f'repos/{REPO_OWNER}/{REPO_NAME}'
    info = github_request('GET', endpoint)
    return jsonify({
        'name': info.get('name'),
        'description': info.get('description'),
        'url': info.get('html_url'),
        'stars': info.get('stargazers_count'),
        'forks': info.get('forks_count'),
        'open_issues': info.get('open_issues_count')
    })

@app.route('/api/files/<path:file_path>', methods=['GET'])
@auth.login_required
def get_file(file_path):
    """获取文件内容"""
    try:
        content = get_repo_contents(file_path)
        if 'content' in content:
            import base64
            decoded = base64.b64decode(content['content']).decode('utf-8')
            return jsonify({
                'path': file_path,
                'content': decoded,
                'sha': content.get('sha'),
                'size': content.get('size'),
                'type': content.get('type')
            })
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['POST'])
@auth.login_required
def create_or_update_file():
    """创建或更新文件"""
    data = request.json
    
    required = ['path', 'content', 'message']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    path = data['path']
    content = data['content']
    message = data['message']
    branch = data.get('branch', 'main')
    
    import base64
    encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    try:
        # 检查文件是否存在
        existing = get_repo_contents(path)
        
        if 'sha' in existing:
            # 更新文件
            result = update_file(path, encoded, message, existing['sha'], branch)
            action = 'updated'
        else:
            # 创建文件
            result = create_file(path, encoded, message, branch)
            action = 'created'
        
        return jsonify({
            'success': True,
            'action': action,
            'path': path,
            'commit': result.get('commit', {}).get('sha'),
            'url': result.get('content', {}).get('html_url')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['DELETE'])
@auth.login_required
def delete_file_api():
    """删除文件"""
    data = request.json
    
    required = ['path', 'message']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    path = data['path']
    message = data['message']
    branch = data.get('branch', 'main')
    sha = data.get('sha')
    
    try:
        # 如果没有提供 SHA，获取它
        if not sha:
            existing = get_repo_contents(path)
            sha = existing['sha']
        
        result = delete_file(path, message, sha, branch)
        
        return jsonify({
            'success': True,
            'path': path,
            'commit': result.get('commit', {}).get('sha')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/issues', methods=['POST'])
@auth.login_required
def create_issue_api():
    """创建 Issue"""
    data = request.json
    
    required = ['title', 'body']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    title = data['title']
    body = data['body']
    labels = data.get('labels', [])
    
    try:
        result = create_issue(title, body, labels)
        
        return jsonify({
            'success': True,
            'number': result.get('number'),
            'url': result.get('html_url'),
            'title': result.get('title')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pulls', methods=['POST'])
@auth.login_required
def create_pull_request_api():
    """创建 Pull Request"""
    data = request.json
    
    required = ['title', 'body', 'head', 'base']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    title = data['title']
    body = data['body']
    head = data['head']
    base = data['base']
    
    try:
        result = create_pull_request(title, body, head, base)
        
        return jsonify({
            'success': True,
            'number': result.get('number'),
            'url': result.get('html_url'),
            'title': result.get('title')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/commits', methods=['GET'])
@auth.login_required
def get_recent_commits():
    """获取最近提交"""
    endpoint = f'repos/{REPO_OWNER}/{REPO_NAME}/commits'
    params = {'per_page': request.args.get('limit', 10)}
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    response = requests.get(f'{GITHUB_API}/{endpoint}', headers=headers, params=params)
    commits = response.json()
    
    result = []
    for commit in commits:
        result.append({
            'sha': commit.get('sha'),
            'message': commit.get('commit', {}).get('message'),
            'author': commit.get('commit', {}).get('author', {}).get('name'),
            'date': commit.get('commit', {}).get('author', {}).get('date'),
            'url': commit.get('html_url')
        })
    
    return jsonify(result)

@app.route('/api/search', methods=['GET'])
@auth.login_required
def search_code():
    """搜索代码"""
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({'error': 'Missing query parameter'}), 400
    
    endpoint = 'search/code'
    params = {
        'q': f'{query} repo:{REPO_OWNER}/{REPO_NAME}'
    }
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    response = requests.get(f'{GITHUB_API}/{endpoint}', headers=headers, params=params)
    result = response.json()
    
    return jsonify({
        'total_count': result.get('total_count'),
        'items': [
            {
                'path': item.get('path'),
                'repository': item.get('repository', {}).get('full_name'),
                'url': item.get('html_url')
            }
            for item in result.get('items', [])
        ]
    })

# ============ 错误处理 ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============ 启动 ============

if __name__ == '__main__':
    print("=" * 60)
    print("MemOS Exchange API Server")
    print("=" * 60)
    print(f"Repository: {REPO_OWNER}/{REPO_NAME}")
    print(f"GitHub: https://github.com/{REPO_OWNER}/{REPO_NAME}")
    print("=" * 60)
    print("\nAvailable endpoints:")
    print("  GET  /api/health          - Health check")
    print("  GET  /api/repo/info       - Repository info")
    print("  GET  /api/files/<path>    - Get file content")
    print("  POST /api/files           - Create/Update file")
    print("  DELETE /api/files         - Delete file")
    print("  POST /api/issues          - Create issue")
    print("  POST /api/pulls           - Create pull request")
    print("  GET  /api/commits         - Recent commits")
    print("  GET  /api/search          - Search code")
    print("=" * 60)
    print("\nAuthentication: Bearer Token")
    print("Available tokens:")
    for name, token in ALLOWED_ASSISTANTS.items():
        print(f"  - {name}: {token}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
