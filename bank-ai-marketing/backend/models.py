"""
Bank AI Marketing - Database Models
数据库模型定义
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


# ========================================
# 1. 坐席表 (Agents)
# ========================================
class Agent(db.Model):
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('admin', 'supervisor', 'operator'), default='operator')
    status = db.Column(db.Enum('active', 'inactive', 'busy'), default='active')
    phone_extension = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'role': self.role,
            'status': self.status,
            'phone_extension': self.phone_extension
        }


# ========================================
# 2. 客户表 (Customers)
# ========================================
class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.BigInteger, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(50))
    id_card = db.Column(db.String(18))  # 需要加密存储
    gender = db.Column(db.Enum('male', 'female', 'unknown'), default='unknown')
    age_range = db.Column(db.Enum('18-25', '26-35', '36-45', '46-60', '60+', 'unknown'), default='unknown')
    city = db.Column(db.String(50))
    tags = db.Column(db.JSON)
    risk_level = db.Column(db.Enum('low', 'medium', 'high'), default='low')
    intent_level = db.Column(db.Enum('cold', 'warm', 'hot', 'converted'), default='cold')
    source = db.Column(db.String(50), default='manual')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'name': self.name,
            'gender': self.gender,
            'age_range': self.age_range,
            'city': self.city,
            'tags': self.tags or [],
            'risk_level': self.risk_level,
            'intent_level': self.intent_level,
            'source': self.source
        }


# ========================================
# 3. 营销活动策划表 (Campaigns)
# ========================================
class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    service_type = db.Column(db.Enum('credit_card', 'loan', 'wealth', 'insurance', 'other'), nullable=False)
    status = db.Column(db.Enum('draft', 'active', 'paused', 'completed'), default='draft')
    script_template_id = db.Column(db.Integer, db.ForeignKey('script_templates.id'))
    target_count = db.Column(db.Integer, default=0)
    completed_count = db.Column(db.Integer, default=0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    created_by = db.Column(db.Integer, db.ForeignKey('agents.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'service_type': self.service_type,
            'status': self.status,
            'script_template_id': self.script_template_id,
            'target_count': self.target_count,
            'completed_count': self.completed_count,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None
        }


# ========================================
# 4. 脚本模板表 (ScriptTemplates)
# ========================================
class ScriptTemplate(db.Model):
    __tablename__ = 'script_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    service_type = db.Column(db.Enum('credit_card', 'loan', 'wealth', 'insurance', 'other'), nullable=False)
    version = db.Column(db.String(20), default='1.0.0')
    status = db.Column(db.Enum('draft', 'active', 'archived'), default='draft')

    # 脚本内容
    opening_script = db.Column(db.Text)
    pitch_script = db.Column(db.Text)
    objection_handling = db.Column(db.JSON)
    closing_script = db.Column(db.Text)

    # LLM 配置
    system_prompt = db.Column(db.Text)
    max_turns = db.Column(db.Integer, default=10)
    tone = db.Column(db.String(50), default='friendly')

    created_by = db.Column(db.Integer, db.ForeignKey('agents.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'service_type': self.service_type,
            'version': self.version,
            'status': self.status,
            'opening_script': self.opening_script,
            'pitch_script': self.pitch_script,
            'objection_handling': self.objection_handling or [],
            'closing_script': self.closing_script,
            'system_prompt': self.system_prompt,
            'max_turns': self.max_turns,
            'tone': self.tone
        }


# ========================================
# 5. 通话记录表 (CallRecords)
# ========================================
class CallRecord(db.Model):
    __tablename__ = 'call_records'

    id = db.Column(db.BigInteger, primary_key=True)
    call_sid = db.Column(db.String(100), unique=True, nullable=False)
    customer_id = db.Column(db.BigInteger, db.ForeignKey('customers.id'), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'))
    script_template_id = db.Column(db.Integer, db.ForeignKey('script_templates.id'))
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))

    # 通话详情
    direction = db.Column(db.Enum('inbound', 'outbound'), default='outbound')
    call_status = db.Column(db.Enum('no_answer', 'busy', 'failed', 'answered', 'completed'), default='no_answer')
    call_result = db.Column(db.Enum('not_interested', 'callback', 'interested', 'converted', 'complaint'))

    # 时间信息
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer, default=0)

    # 录音信息
    recording_url = db.Column(db.String(500))
    recording_duration = db.Column(db.Integer, default=0)

    # ASR/LLM 信息
    transcript = db.Column(db.Text)
    summary = db.Column(db.Text)
    intent_detected = db.Column(db.String(50))
    sentiment = db.Column(db.Enum('positive', 'neutral', 'negative'), default='neutral')

    # 元数据
    hangup_cause = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    customer = db.relationship('Customer', backref='call_records')
    campaign = db.relationship('Campaign', backref='call_records')
    script_template = db.relationship('ScriptTemplate', backref='call_records')
    agent = db.relationship('Agent', backref='call_records')
    details = db.relationship('CallDetail', backref='call_record', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'call_sid': self.call_sid,
            'customer_id': self.customer_id,
            'customer_phone': self.customer_phone,
            'campaign_id': self.campaign_id,
            'direction': self.direction,
            'call_status': self.call_status,
            'call_result': self.call_result,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'recording_url': self.recording_url,
            'summary': self.summary,
            'intent_detected': self.intent_detected,
            'sentiment': self.sentiment
        }


# ========================================
# 6. 通话详情表 (CallDetails)
# ========================================
class CallDetail(db.Model):
    __tablename__ = 'call_details'

    id = db.Column(db.BigInteger, primary_key=True)
    call_id = db.Column(db.BigInteger, db.ForeignKey('call_records.id'), nullable=False)
    turn_number = db.Column(db.Integer, nullable=False)
    speaker = db.Column(db.Enum('customer', 'assistant'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)
    confidence = db.Column(db.Float)
    is_interrupted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'call_id': self.call_id,
            'turn_number': self.turn_number,
            'speaker': self.speaker,
            'content': self.content,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'confidence': self.confidence,
            'is_interrupted': self.is_interrupted
        }


# ========================================
# 7. 跟进记录表 (FollowUps)
# ========================================
class FollowUp(db.Model):
    __tablename__ = 'follow_ups'

    id = db.Column(db.BigInteger, primary_key=True)
    customer_id = db.Column(db.BigInteger, db.ForeignKey('customers.id'), nullable=False)
    call_id = db.Column(db.BigInteger, db.ForeignKey('call_records.id'))
    follow_up_type = db.Column(db.Enum('callback', 'sms', 'wechat', 'visit'), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    actual_time = db.Column(db.DateTime)
    status = db.Column(db.Enum('pending', 'completed', 'cancelled'), default='pending')
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('agents.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    customer = db.relationship('Customer', backref='follow_ups')
    call = db.relationship('CallRecord', backref='follow_ups')
    creator = db.relationship('Agent', backref='follow_ups')

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'call_id': self.call_id,
            'follow_up_type': self.follow_up_type,
            'scheduled_time': self.scheduled_time.isoformat(),
            'actual_time': self.actual_time.isoformat() if self.actual_time else None,
            'status': self.status,
            'notes': self.notes
        }


# ========================================
# 8. 系统配置表 (SystemConfigs)
# ========================================
class SystemConfig(db.Model):
    __tablename__ = 'system_configs'

    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(100), unique=True, nullable=False)
    config_value = db.Column(db.Text, nullable=False)
    config_type = db.Column(db.String(20), default='string')
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'config_type': self.config_type,
            'description': self.description
        }


# ========================================
# 9. API 密钥表 (ApiKeys)
# ========================================
class ApiKey(db.Model):
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    key_name = db.Column(db.String(100), nullable=False)
    api_key = db.Column(db.String(255), unique=True, nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='active')
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'key_name': self.key_name,
            'api_key': self.api_key[:8] + '***' if self.api_key else '',  # 隐藏密钥
            'provider': self.provider,
            'status': self.status
        }


def init_db_models():
    """初始化数据库表"""
    db.create_all()
    print("Database tables created successfully")
