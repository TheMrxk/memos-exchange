"""
Bank AI Marketing - API Routes
API 路由定义
"""

import json
from flask import Blueprint, jsonify, request
from models import db, Agent, Customer, Campaign, ScriptTemplate, CallRecord, CallDetail, FollowUp, SystemConfig, ApiKey
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def init_routes(app):
    """注册所有 API 路由"""

    # ========================================
    # 公共 API
    # ========================================

    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        """获取统计信息"""
        stats = {
            'total_customers': Customer.query.count(),
            'total_calls': CallRecord.query.count(),
            'total_campaigns': Campaign.query.count(),
            'total_agents': Agent.query.count(),
            'pending_followups': FollowUp.query.filter(FollowUp.status == 'pending').count(),
            'calls_today': CallRecord.query.filter(
                db.func.date(CallRecord.start_time) == datetime.now().date()
            ).count()
        }
        return jsonify(stats)

    # ========================================
    # 客户管理 API
    # ========================================

    customers_bp = Blueprint('customers', __name__, url_prefix='/api/customers')

    @customers_bp.route('', methods=['GET'])
    def list_customers():
        """获取客户列表"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        intent_level = request.args.get('intent_level')
        search = request.args.get('search')

        query = Customer.query

        if intent_level:
            query = query.filter(Customer.intent_level == intent_level)
        if search:
            query = query.filter(
                db.or_(
                    Customer.phone_number.like(f'%{search}%'),
                    Customer.name.like(f'%{search}%')
                )
            )

        pagination = query.order_by(Customer.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'items': [c.to_dict() for c in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        })

    @customers_bp.route('', methods=['POST'])
    def create_customer():
        """创建客户"""
        data = request.json

        # 检查手机号是否已存在
        existing = Customer.query.filter_by(phone_number=data['phone_number']).first()
        if existing:
            return jsonify({'error': '手机号已存在'}), 400

        customer = Customer(
            phone_number=data['phone_number'],
            name=data.get('name'),
            gender=data.get('gender', 'unknown'),
            age_range=data.get('age_range', 'unknown'),
            city=data.get('city'),
            tags=data.get('tags', []),
            source=data.get('source', 'manual')
        )

        db.session.add(customer)
        db.session.commit()

        return jsonify(customer.to_dict()), 201

    @customers_bp.route('/<int:customer_id>', methods=['GET'])
    def get_customer(customer_id):
        """获取客户详情"""
        customer = Customer.query.get_or_404(customer_id)
        return jsonify(customer.to_dict())

    @customers_bp.route('/<int:customer_id>', methods=['PUT'])
    def update_customer(customer_id):
        """更新客户"""
        customer = Customer.query.get_or_404(customer_id)
        data = request.json

        for key in ['name', 'gender', 'age_range', 'city', 'tags', 'risk_level', 'intent_level']:
            if key in data:
                setattr(customer, key, data[key])

        db.session.commit()
        return jsonify(customer.to_dict())

    @customers_bp.route('/<int:customer_id>', methods=['DELETE'])
    def delete_customer(customer_id):
        """删除客户"""
        customer = Customer.query.get_or_404(customer_id)
        db.session.delete(customer)
        db.session.commit()
        return jsonify({'message': '删除成功'})

    @customers_bp.route('/<int:customer_id>/calls', methods=['GET'])
    def get_customer_calls(customer_id):
        """获取客户通话记录"""
        calls = CallRecord.query.filter_by(customer_id=customer_id).order_by(
            CallRecord.start_time.desc()
        ).limit(50).all()
        return jsonify([c.to_dict() for c in calls])

    @customers_bp.route('/<int:customer_id>/followups', methods=['POST'])
    def create_followup(customer_id):
        """创建客户跟进计划"""
        data = request.json
        followup = FollowUp(
            customer_id=customer_id,
            follow_up_type=data['follow_up_type'],
            scheduled_time=datetime.fromisoformat(data['scheduled_time']),
            notes=data.get('notes'),
            created_by=data.get('created_by')
        )
        db.session.add(followup)
        db.session.commit()
        return jsonify(followup.to_dict()), 201

    app.register_blueprint(customers_bp)

    # ========================================
    # 通话记录 API
    # ========================================

    calls_bp = Blueprint('calls', __name__, url_prefix='/api/calls')

    @calls_bp.route('', methods=['GET'])
    def list_calls():
        """获取通话记录列表"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        result = request.args.get('result')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = CallRecord.query

        if status:
            query = query.filter(CallRecord.call_status == status)
        if result:
            query = query.filter(CallRecord.call_result == result)
        if start_date:
            query = query.filter(CallRecord.start_time >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(CallRecord.start_time <= datetime.fromisoformat(end_date))

        pagination = query.order_by(CallRecord.start_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'items': [c.to_dict() for c in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        })

    @calls_bp.route('/<int:call_id>', methods=['GET'])
    def get_call(call_id):
        """获取通话详情"""
        call = CallRecord.query.get_or_404(call_id)
        result = call.to_dict()

        # 从 call_records 的 transcript 字段 (JSON 格式) 获取数据
        if call.transcript:
            try:
                call_data = json.loads(call.transcript)
                result['transcript'] = call_data.get('transcript', [])
                result['customer_info'] = call_data.get('customer_info', {})
                result['summary'] = call_data.get('summary', call.summary)
                result['intent_level'] = call_data.get('intent_level', call.intent_detected)
            except json.JSONDecodeError:
                result['transcript'] = []
                result['customer_info'] = {}
        else:
            result['transcript'] = []
            result['customer_info'] = {}

        result['details'] = [d.to_dict() for d in call.details]
        return jsonify(result)

    @calls_bp.route('/<int:call_id>/summary', methods=['PUT'])
    def update_call_summary(call_id):
        """更新通话摘要"""
        call = CallRecord.query.get_or_404(call_id)
        data = request.json

        for key in ['summary', 'intent_detected', 'sentiment', 'call_result']:
            if key in data:
                setattr(call, key, data[key])

        db.session.commit()
        return jsonify(call.to_dict())

    app.register_blueprint(calls_bp)

    # ========================================
    # 营销活动 API
    # ========================================

    campaigns_bp = Blueprint('campaigns', __name__, url_prefix='/api/campaigns')

    @campaigns_bp.route('', methods=['GET'])
    def list_campaigns():
        """获取活动列表"""
        status = request.args.get('status')
        service_type = request.args.get('service_type')

        query = Campaign.query
        if status:
            query = query.filter(Campaign.status == status)
        if service_type:
            query = query.filter(Campaign.service_type == service_type)

        campaigns = query.order_by(Campaign.created_at.desc()).all()
        return jsonify([c.to_dict() for c in campaigns])

    @campaigns_bp.route('', methods=['POST'])
    def create_campaign():
        """创建活动"""
        data = request.json
        campaign = Campaign(
            name=data['name'],
            description=data.get('description'),
            service_type=data['service_type'],
            script_template_id=data.get('script_template_id'),
            target_count=data.get('target_count', 0),
            start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else None,
            end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
            created_by=data.get('created_by')
        )
        db.session.add(campaign)
        db.session.commit()
        return jsonify(campaign.to_dict()), 201

    @campaigns_bp.route('/<int:campaign_id>', methods=['PUT'])
    def update_campaign(campaign_id):
        """更新活动"""
        campaign = Campaign.query.get_or_404(campaign_id)
        data = request.json

        for key in ['name', 'description', 'status', 'target_count', 'start_date', 'end_date']:
            if key in data:
                if key in ['start_date', 'end_date'] and data[key]:
                    setattr(campaign, key, datetime.fromisoformat(data[key]))
                else:
                    setattr(campaign, key, data[key])

        db.session.commit()
        return jsonify(campaign.to_dict())

    @campaigns_bp.route('/<int:campaign_id>', methods=['GET'])
    def get_campaign(campaign_id):
        """获取活动详情"""
        campaign = Campaign.query.get_or_404(campaign_id)
        return jsonify(campaign.to_dict())

    app.register_blueprint(campaigns_bp)

    # ========================================
    # 脚本模板 API
    # ========================================

    scripts_bp = Blueprint('scripts', __name__, url_prefix='/api/scripts')

    @scripts_bp.route('', methods=['GET'])
    def list_scripts():
        """获取脚本模板列表"""
        service_type = request.args.get('service_type')
        status = request.args.get('status')

        query = ScriptTemplate.query
        if service_type:
            query = query.filter(ScriptTemplate.service_type == service_type)
        if status:
            query = query.filter(ScriptTemplate.status == status)

        templates = query.order_by(ScriptTemplate.created_at.desc()).all()
        return jsonify([t.to_dict() for t in templates])

    @scripts_bp.route('', methods=['POST'])
    def create_script():
        """创建脚本模板"""
        data = request.json
        template = ScriptTemplate(
            name=data['name'],
            service_type=data['service_type'],
            opening_script=data.get('opening_script'),
            pitch_script=data.get('pitch_script'),
            objection_handling=data.get('objection_handling', []),
            closing_script=data.get('closing_script'),
            system_prompt=data.get('system_prompt'),
            max_turns=data.get('max_turns', 10),
            tone=data.get('tone', 'friendly'),
            created_by=data.get('created_by')
        )
        db.session.add(template)
        db.session.commit()
        return jsonify(template.to_dict()), 201

    @scripts_bp.route('/<int:script_id>', methods=['PUT'])
    def update_script(script_id):
        """更新脚本模板"""
        template = ScriptTemplate.query.get_or_404(script_id)
        data = request.json

        for key in ['name', 'service_type', 'status', 'opening_script', 'pitch_script',
                    'objection_handling', 'closing_script', 'system_prompt', 'max_turns', 'tone']:
            if key in data:
                setattr(template, key, data[key])

        db.session.commit()
        return jsonify(template.to_dict())

    @scripts_bp.route('/<int:script_id>', methods=['GET'])
    def get_script(script_id):
        """获取脚本模板详情"""
        template = ScriptTemplate.query.get_or_404(script_id)
        return jsonify(template.to_dict())

    app.register_blueprint(scripts_bp)

    # ========================================
    # 跟进计划 API
    # ========================================

    followups_bp = Blueprint('followups', __name__, url_prefix='/api/followups')

    @followups_bp.route('', methods=['GET'])
    def list_followups():
        """获取跟进计划列表"""
        status = request.args.get('status')
        customer_id = request.args.get('customer_id')

        query = FollowUp.query
        if status:
            query = query.filter(FollowUp.status == status)
        if customer_id:
            query = query.filter(FollowUp.customer_id == customer_id)

        followups = query.order_by(FollowUp.scheduled_time.asc()).all()
        return jsonify([f.to_dict() for f in followups])

    @followups_bp.route('/<int:followup_id>/complete', methods=['POST'])
    def complete_followup(followup_id):
        """完成跟进"""
        followup = FollowUp.query.get_or_404(followup_id)
        followup.status = 'completed'
        followup.actual_time = datetime.now()
        data = request.json
        if data.get('notes'):
            followup.notes = data['notes']
        db.session.commit()
        return jsonify(followup.to_dict())

    app.register_blueprint(followups_bp)

    # ========================================
    # 系统配置 API
    # ========================================

    configs_bp = Blueprint('configs', __name__, url_prefix='/api/configs')

    @configs_bp.route('', methods=['GET'])
    def list_configs():
        """获取系统配置"""
        configs = SystemConfig.query.all()
        return jsonify({c.config_key: c.config_value for c in configs})

    @configs_bp.route('/<config_key>', methods=['PUT'])
    def update_config(config_key):
        """更新系统配置"""
        config = SystemConfig.query.filter_by(config_key=config_key).first_or_404()
        data = request.json
        config.config_value = data.get('config_value', config.config_value)
        db.session.commit()
        return jsonify(config.to_dict())

    app.register_blueprint(configs_bp)

    logger.info("API routes registered successfully")
