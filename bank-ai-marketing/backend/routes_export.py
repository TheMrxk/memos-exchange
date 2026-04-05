"""
聊天记录导出 API 路由
提供 Markdown 格式聊天记录导出和客户信息整理功能
"""

from flask import Blueprint, jsonify, request, Response
from models import db, CallRecord, Customer
from datetime import datetime
import json
import os

logger = __import__('logging').getLogger(__name__)

export_bp = Blueprint('export', __name__, url_prefix='/api/export')


def generate_markdown_transcript(call_record: CallRecord, customer: Customer = None) -> str:
    """生成 Markdown 格式的通话记录"""
    lines = []

    # 标题
    lines.append("# AI 通话记录")
    lines.append("")

    # 基本信息
    lines.append("## 基本信息")
    lines.append("")
    lines.append(f"- **通话记录 ID**: `{call_record.id}`")
    lines.append(f"- **客户姓名**: {customer.name if customer else 'N/A'}")
    lines.append(f"- **客户手机号**: {call_record.customer_phone}")
    lines.append(f"- **通话状态**: {call_record.call_status}")
    lines.append(f"- **通话结果**: {call_record.call_result}")
    lines.append(f"- **通话时长**: {call_record.duration_seconds} 秒")
    lines.append(f"- **开始时间**: {call_record.start_time.strftime('%Y-%m-%d %H:%M:%S') if call_record.start_time else 'N/A'}")
    lines.append("")

    # 从 call_records 的 transcript 字段解析客户信息
    if call_record.transcript:
        try:
            call_data = json.loads(call_record.transcript)
            customer_info = call_data.get('customer_info', {})
            if customer_info:
                lines.append("## 客户信息摘要")
                lines.append("")
                for key, value in customer_info.items():
                    lines.append(f"- **{key}**: {value}")
                lines.append("")
        except:
            pass

    # 对话内容
    lines.append("## 对话内容")
    lines.append("")

    if call_record.transcript:
        try:
            call_data = json.loads(call_record.transcript)
            transcript = call_data.get('transcript', [])
            if isinstance(transcript, list):
                for item in transcript:
                    role = item.get('role', 'unknown')
                    text = item.get('text', '')
                    timestamp = item.get('timestamp', '')
                    role_icon = "👤" if role == "user" else "🤖"
                    role_name = "客户" if role == "user" else "AI 客服"
                    lines.append(f"### {timestamp} - {role_icon} {role_name}")
                    lines.append("")
                    lines.append(f"{text}")
                    lines.append("")
            else:
                lines.append(str(transcript))
                lines.append("")
        except:
            lines.append(call_record.transcript)
            lines.append("")
    else:
        lines.append("*无对话记录*")
        lines.append("")

    # 摘要和备注
    if call_record.summary:
        lines.append("## 通话摘要")
        lines.append("")
        lines.append(call_record.summary)
        lines.append("")

    # 原始数据 (JSON)
    lines.append("## 原始数据 (JSON)")
    lines.append("")
    lines.append("```json")

    export_data = {
        "call_id": call_record.id,
        "customer": {
            "name": customer.name if customer else None,
            "phone": call_record.customer_phone
        },
        "call_info": {
            "status": call_record.call_status,
            "result": call_record.call_result,
            "duration": call_record.duration_seconds,
            "start_time": call_record.start_time.isoformat() if call_record.start_time else None
        },
    }
    lines.append(json.dumps(export_data, ensure_ascii=False, indent=2))
    lines.append("```")

    return "\n".join(lines)


@export_bp.route('/call/<int:call_id>/markdown', methods=['GET'])
def export_call_markdown(call_id):
    """导出通话记录的 Markdown 格式"""
    call_record = CallRecord.query.get(call_id)
    if not call_record:
        return jsonify({"success": False, "error": "通话记录不存在"}), 404

    # 获取客户信息
    customer = None
    if call_record.customer_id:
        customer = Customer.query.get(call_record.customer_id)

    # 生成 Markdown
    markdown_content = generate_markdown_transcript(call_record, customer)

    filename = f"call_{call_id}_{call_record.customer_phone}.md"
    return Response(
        markdown_content,
        mimetype='text/markdown',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@export_bp.route('/call/<int:call_id>/summary', methods=['GET'])
def get_call_summary(call_id):
    """获取通话摘要数据（用于大模型整理）"""
    call_record = CallRecord.query.get(call_id)
    if not call_record:
        return jsonify({"success": False, "error": "通话记录不存在"}), 404

    customer = None
    if call_record.customer_id:
        customer = Customer.query.get(call_record.customer_id)

    # 从 call_records 的 transcript 字段解析数据
    transcript = []
    customer_info = {}
    summary = call_record.summary

    if call_record.transcript:
        try:
            call_data = json.loads(call_record.transcript)
            transcript = call_data.get('transcript', [])
            customer_info = call_data.get('customer_info', {})
            summary = call_data.get('summary', call_record.summary)
        except:
            pass

    # 构建结构化数据
    summary_data = {
        "call_id": call_id,
        "customer": {
            "name": customer.name if customer else None,
            "phone": call_record.customer_phone,
            "intent_level": customer.intent_level if customer else None,
            "tags": customer.tags if customer else None
        } if call_record else None,
        "call_info": {
            "status": call_record.call_status,
            "result": call_record.call_result,
            "duration": call_record.duration_seconds,
            "start_time": call_record.start_time.isoformat() if call_record.start_time else None
        },
        "transcript": transcript,
        "summary": summary,
        "customer_info": customer_info,
        "full_transcript": ""
    }

    # 构建完整对话文本
    if transcript:
        try:
            if isinstance(transcript, list):
                summary_data["full_transcript"] = "\n".join([f"{t.get('role', 'unknown')}: {t.get('text', '')}" for t in transcript])
        except:
            summary_data["full_transcript"] = str(transcript)

    return jsonify({
        "success": True,
        "data": summary_data
    })


@export_bp.route('/call/<int:call_id>/customer-info', methods=['POST'])
def update_call_customer_info(call_id):
    """更新客户信息（大模型整理后调用）"""
    call_record = CallRecord.query.get(call_id)
    if not call_record:
        return jsonify({"success": False, "error": "通话记录不存在"}), 404

    data = request.get_json() or {}
    customer_info = data.get('info', {})
    summary = data.get('summary', '')

    # 从 call_records 的 transcript 字段读取现有数据
    call_data = {}
    if call_record.transcript:
        try:
            call_data = json.loads(call_record.transcript)
        except:
            pass

    # 更新客户信息和摘要
    if customer_info:
        existing_info = call_data.get('customer_info', {})
        existing_info.update(customer_info)
        call_data['customer_info'] = existing_info

    if summary:
        call_data['summary'] = summary

    # 保存回 call_records 的 transcript 字段
    call_record.transcript = json.dumps(call_data, ensure_ascii=False)
    db.session.commit()

    # 同时更新客户的意向等级
    if customer_info.get('intent_level') and call_record.customer_id:
        customer = Customer.query.get(call_record.customer_id)
        if customer:
            customer.intent_level = customer_info.get('intent_level')
            db.session.commit()

    return jsonify({
        "success": True,
        "customer_info": call_data.get('customer_info', customer_info),
        "summary": call_data.get('summary', summary)
    })


@export_bp.route('/call/<int:call_id>/analyze', methods=['POST'])
def analyze_call_with_llm(call_id):
    """使用大模型分析通话记录并提取客户信息"""
    from services.llm_client import get_llm_client

    call_record = CallRecord.query.get(call_id)
    if not call_record:
        return jsonify({"success": False, "error": "通话记录不存在"}), 404

    customer = None
    if call_record.customer_id:
        customer = Customer.query.get(call_record.customer_id)

    # 从 call_records 的 transcript 字段读取数据
    if not call_record.transcript:
        return jsonify({"success": False, "error": "没有对话记录可供分析"}), 400

    try:
        call_data = json.loads(call_record.transcript)
        transcript = call_data.get('transcript', [])
    except:
        return jsonify({"success": False, "error": "无效的对话数据格式"}), 400

    # 获取对话文本
    try:
        if isinstance(transcript, list):
            full_transcript = "\n".join([f"{t.get('role', 'unknown')}: {t.get('text', '')}" for t in transcript])
        else:
            full_transcript = str(transcript)
    except:
        full_transcript = str(transcript)

    # 构建分析 Prompt
    prompt = f"""请分析以下银行客服与客户的通话记录，提取客户的关键信息：

通话内容:
{full_transcript}

请以 JSON 格式返回以下信息:
{{
    "intent_level": "客户意向程度 (hot/warm/cold/converted)",
    "interest": "客户感兴趣的产品或服务",
    "budget": "客户提到的金额或预算（如果有）",
    "concerns": ["客户的主要顾虑列表"],
    "next_step": "建议的下一步行动",
    "notes": "其他重要信息"
}}

只返回 JSON 数据，不要其他内容。"""

    try:
        # 调用 LLM 分析
        llm_client = get_llm_client()
        if not llm_client:
            return jsonify({"success": False, "error": "LLM 客户端未初始化"}), 500

        messages = [
            {"role": "system", "content": "你是一个专业的银行客服数据分析助手，擅长从对话中提取客户意向和关键信息。"},
            {"role": "user", "content": prompt}
        ]

        result = llm_client.chat(messages)

        # 解析 LLM 返回的 JSON
        import re
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            customer_info = json.loads(json_match.group())
        else:
            customer_info = json.loads(result)

        # 保存客户信息 - 存入 call_records 的 transcript 字段
        existing_info = call_data.get('customer_info', {})
        existing_info.update(customer_info)
        call_data['customer_info'] = existing_info
        call_data['summary'] = result
        call_record.transcript = json.dumps(call_data, ensure_ascii=False)
        db.session.commit()

        # 更新客户意向等级
        if customer_info.get('intent_level') and customer:
            customer.intent_level = customer_info.get('intent_level')
            db.session.commit()

        return jsonify({
            "success": True,
            "customer_info": customer_info,
            "summary": result
        })

    except Exception as e:
        logger.error(f"LLM 分析失败：{e}")
        return jsonify({"success": False, "error": str(e)}), 500
