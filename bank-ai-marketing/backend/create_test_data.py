#!/usr/bin/env python3
"""
创建测试数据 - 模拟通话记录和客户信息
用于测试前端 UI、导出 Markdown 和 AI 分析功能
"""

import mysql.connector
import json
from datetime import datetime, timedelta
import random

# 数据库配置
DB_CONFIG = {
    'host': 'mysql',
    'port': 3306,
    'user': 'bankai',
    'password': 'BankAi2026',
    'database': 'bank_ai_marketing'
}

# 模拟客户数据
CUSTOMERS_DATA = [
    {'phone': '13812345678', 'name': '张伟', 'city': '北京', 'intent': 'hot'},
    {'phone': '13987654321', 'name': '李娜', 'city': '上海', 'intent': 'warm'},
    {'phone': '13655556666', 'name': '王强', 'city': '广州', 'intent': 'cold'},
    {'phone': '13799998888', 'name': '刘芳', 'city': '深圳', 'intent': 'converted'},
]

# 模拟对话内容
CONVERSATIONS = [
    {
        'transcript': [
            {'role': 'assistant', 'text': '您好，请问是张伟先生吗？我是银行 AI 客服代表。', 'timestamp': '14:30:01'},
            {'role': 'user', 'text': '是的，我是。有什么事吗？', 'timestamp': '14:30:05'},
            {'role': 'assistant', 'text': '张先生您好，我行最近推出了一款优质的理财产品，年化收益率可达 4.5%，想向您介绍一下。', 'timestamp': '14:30:10'},
            {'role': 'user', 'text': '理财产品啊，具体是什么产品？', 'timestamp': '14:30:15'},
            {'role': 'assistant', 'text': '这款 product 是稳健型理财，投资期限 1 年，起投金额 5 万元，主要投资于债券和货币市场工具。', 'timestamp': '14:30:20'},
            {'role': 'user', 'text': '听起来不错，那风险怎么样？', 'timestamp': '14:30:28'},
            {'role': 'assistant', 'text': '这款产品风险等级为 R2，属于中低风险，适合稳健型投资者。历史业绩表现稳定，没有出现过亏损。', 'timestamp': '14:30:35'},
            {'role': 'user', 'text': '好的，我考虑一下。大概需要多少资金起投？', 'timestamp': '14:30:45'},
            {'role': 'assistant', 'text': '起投金额是 5 万元，追加投资是 1 万元的整数倍。张先生您有兴趣了解一下详细的产品说明书吗？', 'timestamp': '14:30:50'},
            {'role': 'user', 'text': '行，你发我看看吧。我手机号就是微信。', 'timestamp': '14:31:00'},
            {'role': 'assistant', 'text': '好的，我稍后添加您的微信发送产品资料。感谢您的接听，祝您生活愉快！', 'timestamp': '14:31:08'},
        ],
        'customer_info': {
            'interest': '理财产品',
            'budget': '50000 起',
            'risk_tolerance': '稳健型',
            'sentiment': 'positive',
            'follow_up_needed': True
        },
        'summary': '客户对理财产品表现出兴趣，询问了收益率、风险等级和起投金额。同意接收产品资料，意向程度较高，建议后续跟进。',
        'intent_level': 'hot'
    },
    {
        'transcript': [
            {'role': 'assistant', 'text': '您好，请问是李娜女士吗？我是银行 AI 客服。', 'timestamp': '10:15:01'},
            {'role': 'user', 'text': '对，是我。', 'timestamp': '10:15:04'},
            {'role': 'assistant', 'text': '李女士您好，感谢您一直以来的支持。我行现推出信用卡优惠活动，消费返现最高可达 10%，想邀请参加。', 'timestamp': '10:15:10'},
            {'role': 'user', 'text': '信用卡我已经有了。', 'timestamp': '10:15:18'},
            {'role': 'assistant', 'text': '理解，我们这款信用卡有很多特色权益，比如机场贵宾厅、加油优惠、电影票买一送一等。', 'timestamp': '10:15:25'},
            {'role': 'user', 'text': '年费多少？', 'timestamp': '10:15:32'},
            {'role': 'assistant', 'text': '首年免年费，消费满 5 次或累计 1 万元可免次年年费。', 'timestamp': '10:15:38'},
            {'role': 'user', 'text': '那还行，但我平时消费不多。', 'timestamp': '10:15:45'},
            {'role': 'assistant', 'text': '没关系的，您可以先办理，有机会再用。请问您平时在哪些场景消费比较多呢？比如超市、餐饮、加油。', 'timestamp': '10:15:52'},
            {'role': 'user', 'text': '主要是超市和加油吧。', 'timestamp': '10:16:00'},
            {'role': 'assistant', 'text': '好的，那这张卡很适合您，超市和加油都有额外返现。我可以帮您登记一下，稍后让专员联系您办理。', 'timestamp': '10:16:10'},
            {'role': 'user', 'text': '行吧，那你联系吧。', 'timestamp': '10:16:18'},
        ],
        'customer_info': {
            'interest': '信用卡',
            'usage_scenario': ['超市', '加油'],
            'concerns': ['年费', '消费频次'],
            'sentiment': 'neutral'
        },
        'summary': '客户已有信用卡，但对年费优惠政策表示认可。主要消费场景为超市和加油，对产品有一定兴趣但积极性一般。',
        'intent_level': 'warm'
    },
    {
        'transcript': [
            {'role': 'assistant', 'text': '您好，请问是王强先生吗？我是银行 AI 客服。', 'timestamp': '16:20:01'},
            {'role': 'user', 'text': '又是什么推销吧？', 'timestamp': '16:20:05'},
            {'role': 'assistant', 'text': '王先生您好，我行推出了一款优惠贷款产品，利率优惠，放款快，想向您介绍一下。', 'timestamp': '16:20:12'},
            {'role': 'user', 'text': '不需要，我现在不缺钱。', 'timestamp': '16:20:18'},
            {'role': 'assistant', 'text': '理解的，您可以先了解一下，以备不时之需。这款产品年化利率低至 3.85%，随借随还。', 'timestamp': '16:20:25'},
            {'role': 'user', 'text': '真不需要，别再打了。', 'timestamp': '16:20:32'},
            {'role': 'assistant', 'text': '抱歉打扰您了，那我不多打扰了。祝您生活愉快，再见。', 'timestamp': '16:20:38'},
        ],
        'customer_info': {
            'interest': '无',
            'sentiment': 'negative',
            'do_not_call': True
        },
        'summary': '客户明确拒绝贷款产品，态度较为强硬，表示不需要且不希望再接到推销电话。',
        'intent_level': 'cold'
    },
    {
        'transcript': [
            {'role': 'assistant', 'text': '您好，请问是刘芳女士吗？我是银行 AI 客服代表。', 'timestamp': '09:00:01'},
            {'role': 'user', 'text': '是的，你好。', 'timestamp': '09:00:05'},
            {'role': 'assistant', 'text': '刘女士您好，感谢您之前的咨询。关于您关注的住房贷款产品，我来给您回访一下。', 'timestamp': '09:00:12'},
            {'role': 'user', 'text': '对，我之前咨询过，你们那个利率是多少？', 'timestamp': '09:00:20'},
            {'role': 'assistant', 'text': '目前首套房贷款利率是 LPR 下浮 20 个基点，也就是 4.0% 左右，具体要看您的资质。', 'timestamp': '09:00:28'},
            {'role': 'user', 'text': '我想贷 200 万，20 年，月供多少？', 'timestamp': '09:00:35'},
            {'role': 'assistant', 'text': '等额本息的话，200 万 20 年，月供大约是 12130 元左右。', 'timestamp': '09:00:42'},
            {'role': 'user', 'text': '还行。我需要准备什么材料？', 'timestamp': '09:00:50'},
            {'role': 'assistant', 'text': '需要身份证、户口本、收入证明、银行流水、购房合同等。您是什么时候购房呢？', 'timestamp': '09:00:58'},
            {'role': 'user', 'text': '已经定了，下个月网签。', 'timestamp': '09:01:05'},
            {'role': 'assistant', 'text': '好的，那我安排客户经理和您对接，协助您准备材料。您看明天方便来网点详谈吗？', 'timestamp': '09:01:12'},
            {'role': 'user', 'text': '明天上午可以，大概 10 点左右。', 'timestamp': '09:01:20'},
            {'role': 'assistant', 'text': '好的，我帮您预约明天上午 10 点，XX 支行的客户经理接待您。稍后会发短信确认。', 'timestamp': '09:01:28'},
            {'role': 'user', 'text': '好的，谢谢。', 'timestamp': '09:01:35'},
        ],
        'customer_info': {
            'interest': '住房贷款',
            'loan_amount': '2000000',
            'loan_term': '20 年',
            'purchase_status': '已定房，下月网签',
            'appointment': '明天上午 10 点',
            'sentiment': 'positive'
        },
        'summary': '客户已确定购房，需要办理住房贷款 200 万 20 年期。已预约明天上午 10 点到网点详谈，意向明确，成交概率高。',
        'intent_level': 'converted'
    },
]


def create_test_data():
    """创建测试数据"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    print("📊 开始创建测试数据...")

    # 1. 创建坐席
    cursor.execute("""
        INSERT INTO agents (username, password_hash, display_name, role, status)
        VALUES ('agent001', 'pbkdf2:sha256:260000$xxx$xxx', '客服 001', 'operator', 'active')
        ON DUPLICATE KEY UPDATE username=username
    """)

    # 2. 创建营销活动
    cursor.execute("""
        INSERT INTO campaigns (name, service_type, status, target_count, start_date, end_date, created_at)
        VALUES
        ('理财产品推广', 'wealth', 'active', 100, '2026-04-01', '2026-04-30', NOW()),
        ('信用卡营销', 'credit_card', 'active', 200, '2026-04-01', '2026-04-30', NOW()),
        ('贷款产品推广', 'loan', 'active', 150, '2026-04-01', '2026-04-30', NOW())
    """)

    # 3. 创建客户和通话记录
    for i, (customer_data, conversation) in enumerate(zip(CUSTOMERS_DATA, CONVERSATIONS)):
        # 创建客户
        cursor.execute("""
            INSERT INTO customers (phone_number, name, city, intent_level, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE phone_number=phone_number
        """, (customer_data['phone'], customer_data['name'], customer_data['city'], customer_data['intent']))

        customer_id = cursor.lastrowid

        # 创建通话记录
        start_time = datetime.now() - timedelta(days=random.randint(0, 5), hours=random.randint(0, 23))
        duration = len(conversation['transcript']) * 5 + random.randint(10, 30)
        call_sid = f'call_{customer_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}'

        cursor.execute("""
            INSERT INTO call_records
            (call_sid, customer_id, customer_phone, call_status, call_result, duration_seconds, start_time, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (call_sid, customer_id, customer_data['phone'], 'completed',
              'interested' if customer_data['intent'] in ['hot', 'converted'] else 'not_interested',
              duration, start_time))

        call_id = cursor.lastrowid

        # 创建通话 TURN 级别详情
        for turn_num, turn in enumerate(conversation['transcript']):
            cursor.execute("""
                INSERT INTO call_details
                (call_id, turn_number, speaker, content, start_time, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (call_id, turn_num,
                  'assistant' if turn['role'] == 'assistant' else 'customer',
                  turn['text'], start_time))

        # 将完整的对话 transcript 和 customer_info 存入 call_records 的 transcript 字段 (JSON 格式)
        transcript_json = json.dumps(conversation['transcript'], ensure_ascii=False)
        customer_info_json = json.dumps(conversation['customer_info'], ensure_ascii=False)

        # 合并存储：transcript 字段存储完整对话 + 客户信息
        call_data = {
            'transcript': conversation['transcript'],
            'customer_info': conversation['customer_info'],
            'summary': conversation['summary'],
            'intent_level': conversation['intent_level']
        }
        full_data_json = json.dumps(call_data, ensure_ascii=False)

        cursor.execute("""
            UPDATE call_records
            SET transcript = %s, summary = %s
            WHERE id = %s
        """, (full_data_json, conversation['summary'], call_id))

        print(f"  ✅ 客户 {customer_data['name']} ({customer_data['phone']}) - 通话记录已创建")

    conn.commit()
    cursor.close()
    conn.close()

    print("\n✅ 测试数据创建完成！")
    print("\n📋 数据概览:")
    print("  - 客户数：4")
    print("  - 通话记录：4")
    print("  - 对话内容：包含完整的 ASR→LLM→TTS 对话")
    print("  - 客户信息：包含意向等级、兴趣点、情绪等")
    print("\n🔗 访问 http://localhost:8080 查看效果")


if __name__ == '__main__':
    create_test_data()
