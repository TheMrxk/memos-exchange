#!/usr/bin/env python3
"""
Memory Exchange - Web Backend API

Flask REST API for managing conversations and memories.
"""

import sys
from pathlib import Path

# 添加 memory-exchange-plugin 目录到路径（用于导入 db.schema）
sys.path.insert(0, str(Path(__file__).parent.parent / 'memory-exchange-plugin'))

from flask import Flask, jsonify, request
from flask_cors import CORS
from db.schema import get_database, DatabaseManager
import json
import time
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # 允许前端跨域访问

# 数据库实例
db = None


def init_db():
    global db
    # 使用环境变量中的数据库路径，或者使用默认路径
    db_path = os.environ.get('DATABASE_URL', '/app/data/memory-exchange.db')
    db = get_database(db_path)


# ==================== API 调用统计中间件 ====================

@app.before_request
def before_request():
    """记录请求开始时间"""
    request.start_time = time.time()


@app.after_request
def after_request(response):
    """记录 API 调用"""
    if hasattr(request, 'start_time'):
        response_time_ms = int((time.time() - request.start_time) * 1000)

        # 判断调用来源
        source = 'unknown'
        user_agent = request.headers.get('User-Agent', '').lower()
        referer = request.headers.get('Referer', '').lower()

        if 'vue' in user_agent or 'axios' in user_agent:
            source = 'web'
        elif 'python' in user_agent or 'requests' in user_agent:
            source = 'python'
        elif 'node' in user_agent or 'fetch' in user_agent:
            source = 'plugin'
        elif referer:
            if 'localhost:8080' in referer or '192.168' in referer:
                source = 'web'

        # 记录调用（非健康检查端点）
        if request.path != '/health':
            try:
                db.record_api_call(
                    endpoint=request.path,
                    method=request.method,
                    source=source,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms
                )
            except Exception as e:
                print(f"记录 API 调用失败：{e}")

    return response


# ==================== 健康检查 ====================

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'Memory Exchange API'
    })


# ==================== 统计信息 ====================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    stats = db.get_stats()

    # 添加 API 调用统计
    hours = request.args.get('hours', 24, type=int)
    api_stats = db.get_api_stats(hours)
    stats['api_stats'] = api_stats

    return jsonify(stats)


# ==================== API 统计 ====================

@app.route('/api/api-stats', methods=['GET'])
def get_api_stats():
    """获取 API 调用统计"""
    hours = request.args.get('hours', 24, type=int)
    api_stats = db.get_api_stats(hours)
    return jsonify(api_stats)


# ==================== 对话管理 ====================

@app.route('/api/conversations', methods=['GET'])
def list_conversations():
    """获取对话列表"""
    session_id = request.args.get('session_id')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    conversations = db.get_conversations(session_id, limit, offset)

    # 转换日期格式
    for conv in conversations:
        if 'timestamp' in conv and conv['timestamp']:
            conv['timestamp'] = str(conv['timestamp'])
        if 'created_at' in conv and conv['created_at']:
            conv['created_at'] = str(conv['created_at'])

    return jsonify({
        'conversations': conversations,
        'total': len(conversations)
    })


@app.route('/api/conversations/<int:conv_id>', methods=['GET'])
def get_conversation(conv_id):
    """获取单条对话详情"""
    # 这里需要扩展 DatabaseManager 添加按 ID 获取的方法
    # 暂时返回所有对话，前端过滤
    conversations = db.get_conversations(limit=1000)
    conv = next((c for c in conversations if c['id'] == conv_id), None)

    if conv is None:
        return jsonify({'error': 'Conversation not found'}), 404

    return jsonify(conv)


@app.route('/api/conversations/<int:conv_id>', methods=['DELETE'])
def delete_conversation(conv_id):
    """删除对话（软删除，标记 is_stored=0）"""
    db.conn.execute("""
        UPDATE conversations SET is_stored = 0
        WHERE id = ?
    """, (conv_id,))
    db.conn.commit()

    return jsonify({'success': True, 'message': 'Conversation deleted'})


# ==================== 记忆管理 ====================

@app.route('/api/memories', methods=['GET'])
def list_memories():
    """获取记忆列表"""
    memory_type = request.args.get('type')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    memories = db.get_memories(memory_type, 'default', limit, offset)

    # 转换日期和标签格式
    for mem in memories:
        if 'created_at' in mem and mem['created_at']:
            mem['created_at'] = str(mem['created_at'])
        if 'updated_at' in mem and mem['updated_at']:
            mem['updated_at'] = str(mem['updated_at'])
        if 'tags' in mem and mem['tags']:
            try:
                mem['tags'] = json.loads(mem['tags'])
            except:
                mem['tags'] = []

    return jsonify({
        'memories': memories,
        'total': len(memories)
    })


@app.route('/api/memories/search', methods=['GET'])
def search_memories():
    """搜索记忆"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400

    limit = request.args.get('limit', 10, type=int)
    min_score = request.args.get('min_score', 0.1, type=float)
    memory_type = request.args.get('type')

    results = db.search_memories(query, 'default', limit, min_score)

    # 应用类型过滤
    if memory_type:
        results = [r for r in results if r.get('memory_type') == memory_type]

    # 转换日期和标签格式
    for mem in results:
        if 'created_at' in mem and mem['created_at']:
            mem['created_at'] = str(mem['created_at'])
        if 'tags' in mem and mem['tags']:
            try:
                mem['tags'] = json.loads(mem['tags'])
            except:
                mem['tags'] = []

    return jsonify({
        'query': query,
        'results': results,
        'total': len(results)
    })


@app.route('/api/memories/<int:mem_id>', methods=['GET'])
def get_memory(mem_id):
    """获取单条记忆详情"""
    # 获取所有记忆并查找
    memories = db.get_memories(limit=1000)
    mem = next((m for m in memories if m['id'] == mem_id), None)

    if mem is None:
        return jsonify({'error': 'Memory not found'}), 404

    # 转换格式
    if 'created_at' in mem and mem['created_at']:
        mem['created_at'] = str(mem['created_at'])
    if 'tags' in mem and mem['tags']:
        try:
            mem['tags'] = json.loads(mem['tags'])
        except:
            mem['tags'] = []

    return jsonify(mem)


@app.route('/api/memories', methods=['POST'])
def create_memory():
    """创建新记忆"""
    data = request.get_json()

    if not data or 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400

    content = data['content']
    memory_type = data.get('memory_type', 'fact')
    tags = data.get('tags', [])

    mem_id = db.add_memory(
        content=content,
        memory_type=memory_type,
        tags=tags
    )

    return jsonify({
        'success': True,
        'id': mem_id,
        'message': 'Memory created'
    }), 201


@app.route('/api/memories/<int:mem_id>', methods=['PUT'])
def update_memory(mem_id):
    """更新记忆"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # 构建更新 SQL
    updates = []
    params = []

    if 'content' in data:
        updates.append('content = ?')
        params.append(data['content'])
    if 'memory_type' in data:
        updates.append('memory_type = ?')
        params.append(data['memory_type'])
    if 'tags' in data:
        updates.append('tags = ?')
        params.append(json.dumps(data['tags']))
    if 'confidence' in data:
        updates.append('confidence = ?')
        params.append(data['confidence'])

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    updates.append('updated_at = CURRENT_TIMESTAMP')
    params.append(mem_id)

    db.conn.execute(f"""
        UPDATE memories SET {', '.join(updates)}
        WHERE id = ?
    """, params)
    db.conn.commit()

    return jsonify({
        'success': True,
        'message': 'Memory updated'
    })


@app.route('/api/memories/<int:mem_id>', methods=['DELETE'])
def delete_memory(mem_id):
    """删除记忆"""
    db.conn.execute("""
        DELETE FROM memories WHERE id = ?
    """, (mem_id,))
    db.conn.commit()

    return jsonify({
        'success': True,
        'message': 'Memory deleted'
    })


# ==================== 会话管理 ====================

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """获取会话列表"""
    cursor = db.conn.execute("""
        SELECT * FROM sessions
        ORDER BY last_activity DESC
        LIMIT 50
    """)
    sessions = [dict(row) for row in cursor.fetchall()]

    # 转换日期格式
    for session in sessions:
        if 'started_at' in session and session['started_at']:
            session['started_at'] = str(session['started_at'])
        if 'last_activity' in session and session['last_activity']:
            session['last_activity'] = str(session['last_activity'])

    return jsonify({
        'sessions': sessions,
        'total': len(sessions)
    })


# ==================== 主函数 ====================

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
