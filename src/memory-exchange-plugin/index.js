#!/usr/bin/env node
/**
 * Memory Exchange - 本地记忆插件
 *
 * 功能:
 * - 对话前自动检索相关记忆并注入上下文
 * - 对话后自动保存对话到本地数据库
 *
 * 配置:
 * {
 *   "enabled": true,
 *   "memoryLimitNumber": 6,
 *   "minScore": 0.3,
 *   "includeAssistant": true,
 *   "maxMessageChars": 5000,
 *   "searchEngine": "~/.openclaw/workspace/memory-exchange/src/memory-exchange-plugin/search_engine.py",
 *   "databasePath": "~/.openclaw/workspace/memory-exchange.db",
 *   "userId": "default"
 * }
 */

const { execSync, spawn } = require('child_process');
const { homedir } = require('os');
const { join } = require('path');
const fs = require('fs');

// 文件日志输出
const LOG_FILE = join(homedir(), '.openclaw', 'workspace', 'memory-exchange-plugin.log');
function fileLog(message) {
    const timestamp = new Date().toISOString();
    const logLine = `[${timestamp}] ${message}\n`;
    fs.appendFileSync(LOG_FILE, logLine);
}

// 默认配置
const DEFAULT_CONFIG = {
    enabled: true,
    memoryLimitNumber: 6,
    preferenceLimitNumber: 6,
    minScore: 0.3,
    includeAssistant: true,
    maxMessageChars: 5000,
    searchEngine: join(homedir(), '.openclaw', 'extensions', 'memory-exchange-plugin', 'search_engine.py'),
    databasePath: join(homedir(), '.openclaw', 'workspace', 'memory-exchange.db', 'memory-exchange.db'),
    userId: 'default',
    pythonPath: 'python3'
};

/**
 * 构建插件配置
 */
function buildConfig(pluginConfig = {}) {
    const cfg = { ...DEFAULT_CONFIG, ...pluginConfig };

    // 展开路径
    if (cfg.searchEngine.startsWith('~')) {
        cfg.searchEngine = join(homedir(), cfg.searchEngine.slice(1));
    }
    if (cfg.databasePath.startsWith('~')) {
        cfg.databasePath = join(homedir(), cfg.databasePath.slice(1));
    }

    return cfg;
}

/**
 * 调用检索引擎（Python 脚本）
 */
function searchMemories(cfg, query, limit = 6) {
    try {
        // 截断查询，避免过长
        const maxQueryChars = 200;
        const truncatedQuery = query.length > maxQueryChars ? query.slice(0, maxQueryChars) : query;

        const cmd = `${cfg.pythonPath} "${cfg.searchEngine}" search "${truncatedQuery}" --limit ${limit} --min-score ${cfg.minScore} --json --user-id "${cfg.userId}"`;

        const result = execSync(cmd, {
            encoding: 'utf8',
            timeout: 5000,
            stdio: ['pipe', 'pipe', 'pipe']
        });

        return JSON.parse(result);
    } catch (err) {
        // 搜索失败时返回空数组，不中断对话
        console.warn('[memory-exchange] 检索失败:', err.message);
        return [];
    }
}

/**
 * 保存对话到数据库
 */
function saveConversation(cfg, sessionKey, userContent, assistantContent) {
    fileLog('saveConversation 被调用：sessionKey=' + sessionKey + ', userContent length=' + userContent.length);
    try {
        // 清理用户内容中的系统标记
        const cleanUserContent = cleanConversationContent(userContent);
        const cleanAssistantContent = cleanConversationContent(assistantContent || '');

        // 将内容写入临时文件，避免 shell 转义问题（三引号、特殊字符等）
        const tmpFile = join(require('os').tmpdir(), `memory-exchange-save-${Date.now()}.json`);
        const data = {
            session_key: sessionKey,
            user_content: cleanUserContent,
            assistant_content: cleanAssistantContent
        };
        fs.writeFileSync(tmpFile, JSON.stringify(data, null, 2));

        // 使用 Python 脚本从临时文件读取并保存
        const saveCmd = `${cfg.pythonPath} -c "
import sys
import json
sys.path.insert(0, '${cfg.searchEngine.replace('/search_engine.py', '')}')
from db.schema import get_database

with open('${tmpFile}', 'r', encoding='utf-8') as f:
    data = json.load(f)

db = get_database('${cfg.databasePath}')
conv_id = db.add_conversation(data['session_key'], 'user', data['user_content'])
if data.get('assistant_content'):
    db.add_conversation(data['session_key'], 'assistant', data['assistant_content'])
db.close()
print(conv_id)
" 2>&1`;
        fileLog('执行命令：' + saveCmd.substring(0, 200));
        const convId = execSync(saveCmd, {
            encoding: 'utf8',
            timeout: 5000,
            stdio: ['pipe', 'pipe', 'pipe']
        }).trim();

        // 清理临时文件
        try { fs.unlinkSync(tmpFile); } catch(e) {}

        fileLog('对话已保存，ID=' + convId);
        console.log('[memory-exchange] 对话已保存，ID:', convId);
        return convId;
    } catch (err) {
        fileLog('保存对话失败：' + err.message);
        console.warn('[memory-exchange] 保存对话失败:', err.message);
        return null;
    }
}

/**
 * 从对话生成记忆
 */
function generateMemory(cfg, userContent, assistantContent, conversationId) {
    fileLog('generateMemory 被调用：conversationId=' + conversationId);
    try {
        // 将内容写入临时文件，避免 shell 转义问题
        const tmpFile = join(require('os').tmpdir(), `memory-exchange-${Date.now()}.json`);
        const data = {
            user_content: userContent,
            assistant_content: assistantContent || '',
            conversation_id: parseInt(conversationId) || null,
            user_id: cfg.userId
        };
        fs.writeFileSync(tmpFile, JSON.stringify(data, null, 2));

        const pythonCode = `
import sys
import json
sys.path.insert(0, '${cfg.searchEngine.replace('/search_engine.py', '')}')
from search_engine import MemorySearchEngine
from db.schema import get_database

with open('${tmpFile}', 'r') as f:
    data = json.load(f)

engine = MemorySearchEngine(get_database('${cfg.databasePath}'))
memory_id = engine.add_memory_from_conversation(
    user_content=data['user_content'],
    assistant_content=data['assistant_content'],
    conversation_id=data['conversation_id'],
    user_id=data['user_id']
)
print(memory_id)
`;

        const result = execSync(`${cfg.pythonPath} -c "${pythonCode.replace(/"/g, '\\"')}"`, {
            encoding: 'utf8',
            timeout: 90000,  // 90 秒超时，LLM 调用可能需要较长时间
            stdio: ['pipe', 'pipe', 'pipe']
        }).trim();

        // 清理临时文件
        try { fs.unlinkSync(tmpFile); } catch(e) {}

        fileLog('记忆生成结果：' + result);
        console.log('[memory-exchange] 记忆已生成:', result);
        return result;
    } catch (err) {
        fileLog('记忆生成失败：' + err.message);
        console.warn('[memory-exchange] 记忆生成失败:', err.message);
        return null;
    }
}

/**
 * 格式化记忆为注入文本
 */
function formatMemoriesForInjection(memories) {
    if (!memories || memories.length === 0) {
        return '';
    }

    const lines = [
        '',
        '## 📔 本地记忆',
        '以下是从本地记忆中检索到的相关信息：',
        ''
    ];

    memories.forEach((mem, idx) => {
        const scorePct = Math.round((mem.score || 0) * 100);
        const typeLabels = {
            'preference': '偏好',
            'skill': '技能',
            'experience': '经验',
            'fact': '事实'
        };
        const typeLabel = typeLabels[mem.memory_type] || mem.memory_type;

        lines.push(`${idx + 1}. [相关性 ${scorePct}%] **${typeLabel}**`);
        lines.push(`   ${mem.content}`);

        if (mem.tags) {
            const tags = typeof mem.tags === 'string' ? JSON.parse(mem.tags) : mem.tags;
            if (tags && tags.length > 0) {
                lines.push(`   🏷️ ${tags.join(' ')}`);
            }
        }

        if (mem.created_at) {
            lines.push(`   📅 ${mem.created_at}`);
        }

        lines.push('');
    });

    lines.push('---');
    lines.push('');

    return lines.join('\n');
}

/**
 * 提取文本内容（处理可能的复杂格式）
 */
function extractText(content) {
    if (!content) return '';
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) {
        return content
            .filter(block => block && typeof block === 'object' && block.type === 'text')
            .map(block => block.text)
            .join(' ');
    }
    return '';
}

/**
 * 截断文本
 */
function truncate(text, maxLen) {
    if (!text) return '';
    if (!maxLen) return text;
    return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text;
}

/**
 * 清理用户消息，移除系统注入的上下文，提取用户实际消息
 */
function cleanUserPrompt(text) {
    if (!text) return '';

    // 移除零宽空格
    text = text.replace(/[\u200b\u200c\u200d\ufeff]/g, '');

    // 首先尝试从 "user 原始 query:" 标记后提取
    const marker = 'user 原始 query:';
    const markerIndex = text.lastIndexOf(marker);
    if (markerIndex !== -1) {
        const afterMarker = text.substring(markerIndex + marker.length).trim();
        // 如果标记后面有实际内容（不是空的或系统格式），就使用它
        if (afterMarker && afterMarker.length > 5 && !afterMarker.startsWith('```')) {
            return afterMarker;
        }
    }

    // 方法 2：从 "以下是用户输入】" 之后提取（OpenClaw 的注入格式）
    const inputMarker = '以下是用户输入】';
    const inputMarkerIndex = text.lastIndexOf(inputMarker);
    if (inputMarkerIndex !== -1) {
        const afterInputMarker = text.substring(inputMarkerIndex + inputMarker.length).trim();
        if (afterInputMarker && afterInputMarker.length > 3) {
            return afterInputMarker;
        }
    }

    // 无法从标记提取，尝试直接返回清理后的内容（去掉系统标记）
    // 移除 "Conversation info" 等系统标记行
    let cleaned = text.replace(/^Conversation info \(untrusted metadata\):.*$/gm, '');
    cleaned = cleaned.replace(/^Sender \(untrusted metadata\):.*$/gm, '');
    cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
    cleaned = cleaned.trim();

    // 如果清理后的内容有效，返回它
    if (cleaned && cleaned.length > 3 && !cleaned.startsWith('```')) {
        return cleaned;
    }

    // 无法提取有效内容，返回空
    return '';
}

/**
 * 清理对话内容中的系统标记（用于保存对话记录）
 * 移除 "user 原始 query:"、"Conversation info"、"Sender" 等标记
 */
function cleanConversationContent(text) {
    if (!text) return '';

    // 移除零宽空格
    text = text.replace(/[\u200b\u200c\u200d\ufeff]/g, '');

    // 移除 "user 原始 query:" 标记行
    text = text.replace(/^user\s*原始\s*query\s*[:：]\s*$/gm, '');

    // 移除 "Conversation info (untrusted metadata):" 及其后的 JSON 块
    text = text.replace(/Conversation info \(untrusted metadata\):\s*```json\s*\{[^}]*\}\s*```/g, '');
    text = text.replace(/Conversation info \(untrusted metadata\):/g, '');

    // 移除 "Sender (untrusted metadata):" 及其后的 JSON 块
    text = text.replace(/Sender \(untrusted metadata\):\s*```json\s*\{[^}]*\}\s*```/g, '');
    text = text.replace(/Sender \(untrusted metadata\):/g, '');

    // 移除空的代码块
    text = text.replace(/```\s*```/g, '');

    // 清理多余的空行（3 个或以上连续换行替换为 2 个）
    text = text.replace(/\n{3,}/g, '\n\n');

    // 清理每行开头的多余空格（保留缩进结构）
    text = text.replace(/^[ \t]+$/gm, '');

    // 清理开头和结尾的空白
    return text.trim();
}

/**
 * 从对话中提取最后一轮问答
 */
function pickLastTurn(messages, cfg) {
    // 找到最后一个 user 消息的位置
    let lastUserIndex = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i]?.role === 'user') {
            lastUserIndex = i;
            break;
        }
    }

    if (lastUserIndex === -1) return { user: '', assistant: '' };

    // 获取 user 消息
    const userMsg = messages[lastUserIndex];
    const userContent = truncate(extractText(userMsg.content), cfg.maxMessageChars);

    // 获取 assistant 回复（如果有）
    let assistantContent = '';
    if (cfg.includeAssistant && lastUserIndex < messages.length - 1) {
        const assistantMsg = messages[lastUserIndex + 1];
        if (assistantMsg?.role === 'assistant') {
            assistantContent = truncate(extractText(assistantMsg.content), cfg.maxMessageChars);
        }
    }

    return { user: userContent.trim(), assistant: assistantContent.trim() };
}

module.exports = {
    id: 'memory-exchange-plugin',
    name: 'Memory Exchange 本地记忆',
    description: '本地记忆存储和检索插件',
    kind: 'lifecycle',

    register(api) {
        const cfg = buildConfig(api.pluginConfig);
        const log = api.logger ?? console;

        // 存储用户原始消息的临时缓存（按 sessionId）
        const userPromptCache = new Map();

        fileLog('==================== 插件加载开始 ====================');
        fileLog('插件配置:' + JSON.stringify(cfg, null, 2));
        fileLog('API 对象:' + !!api);
        fileLog('api.on 方法:' + typeof api.on);
        console.log('[memory-exchange] 插件加载中...');

        if (!cfg.enabled) {
            log.info('[memory-exchange] 插件已禁用');
            fileLog('插件已禁用');
            return;
        }

        log.info('[memory-exchange] 插件已注册');
        fileLog('插件已注册');
        console.log('[memory-exchange] 插件已注册，数据库路径:', cfg.databasePath);

        // 对话前钩子 - 检索记忆并注入
        api.on('before_agent_start', async (event, ctx) => {
            fileLog('before_agent_start 事件触发');
            try {
                // 尝试从多个来源获取用户实际消息
                let userPrompt = '';
                const sessionKey = ctx?.sessionKey || ctx?.sessionId || 'default';

                // 1. 首先尝试从 event.prompt 获取
                if (event?.prompt && event.prompt.length >= 3) {
                    userPrompt = event.prompt;
                    fileLog('从 event.prompt 获取：' + userPrompt.substring(0, 100));
                } else {
                    fileLog('event.prompt 为空或过短：' + JSON.stringify({ hasPrompt: !!event?.prompt, promptLength: event?.prompt?.length }));
                }

                // 2. 如果 prompt 是系统上下文，尝试从 messages 中提取最后一条用户消息
                if (!userPrompt || userPrompt.includes('Conversation info') || userPrompt.includes('untrusted metadata')) {
                    const messages = event?.messages || [];
                    fileLog('messages 数组长度：' + messages.length);

                    // 输出最后 3 条消息的结构用于调试
                    const lastMessages = messages.slice(-3).map((m, i) => ({
                        index: messages.length - 3 + i,
                        role: m?.role,
                        contentPreview: extractText(m.content).substring(0, 50)
                    }));
                    fileLog('最后 3 条消息：' + JSON.stringify(lastMessages));

                    // 找到最后一条用户消息
                    for (let i = messages.length - 1; i >= 0; i--) {
                        const msg = messages[i];
                        if (msg?.role === 'user') {
                            const msgContent = extractText(msg.content);
                            fileLog('找到 user 消息 (index=' + i + ')，内容：' + msgContent.substring(0, 100));
                            if (msgContent && msgContent.length >= 3) {
                                userPrompt = msgContent;
                                fileLog('从 messages 中提取到用户消息：' + userPrompt.substring(0, 50));
                                break;
                            }
                        }
                    }
                }

                fileLog('userPrompt: ' + userPrompt.substring(0, 100));

                // 3. 清理用户消息，保存原始内容供后续使用
                const cleanPrompt = cleanUserPrompt(userPrompt);
                fileLog('清理后的用户消息：' + (cleanPrompt ? cleanPrompt.substring(0, 50) : '空'));

                // 保存到缓存，供 agent_end 使用
                if (cleanPrompt && cleanPrompt.length >= 3) {
                    userPromptCache.set(sessionKey, cleanPrompt);
                    fileLog('已缓存用户消息到 session: ' + sessionKey);
                }

                if (!userPrompt || userPrompt.length < 3) {
                    fileLog('prompt 过短，跳过检索');
                    return;
                }

                // 检索记忆
                fileLog('开始检索记忆...');
                const memories = searchMemories(cfg, userPrompt, cfg.memoryLimitNumber);
                fileLog('检索结果：' + (memories?.length || 0) + ' 条');

                if (!memories || memories.length === 0) {
                    fileLog('无相关记忆，跳过注入');
                    return;
                }

                // 格式化为注入文本
                const injectionText = formatMemoriesForInjection(memories);
                fileLog('注入文本长度：' + injectionText.length);

                if (injectionText) {
                    // 注入到系统上下文
                    fileLog('注入记忆到上下文');
                    return {
                        appendSystemContext: injectionText
                    };
                }
            } catch (err) {
                fileLog('before_agent_start 失败：' + err.message);
                log.warn('[memory-exchange] before_agent_start 失败:', err.message);
            }
        });

        // 对话后钩子 - 保存对话
        api.on('agent_end', async (event, ctx) => {
            fileLog('agent_end 事件触发！');
            fileLog('event: ' + JSON.stringify({
                success: event?.success,
                messagesCount: event?.messages?.length,
                hasPrompt: !!event?.prompt
            }));
            fileLog('ctx: ' + JSON.stringify({
                sessionKey: ctx?.sessionKey,
                sessionId: ctx?.sessionId
            }));
            console.log('[memory-exchange] agent_end 事件触发！！！');

            log.info('[memory-exchange] agent_end 事件触发', {
                success: event?.success,
                messagesCount: event?.messages?.length,
                sessionKey: ctx?.sessionKey,
                sessionId: ctx?.sessionId
            });

            try {
                if (!event?.success || !event?.messages?.length) {
                    fileLog('事件数据无效：success=' + event?.success + ', messages=' + event?.messages?.length);
                    log.warn('[memory-exchange] 事件数据无效', { success: event?.success, messages: event?.messages?.length });
                    return;
                }

                // 从缓存中获取用户原始消息（在 before_agent_start 时保存的）
                const sessionKey = ctx?.sessionKey || ctx?.sessionId || 'default-session';
                const cachedUserPrompt = userPromptCache.get(sessionKey);

                // 调试：输出 messages 数组结构
                const debugMessages = event.messages.slice(-5).map((m, i) => ({
                    index: event.messages.length - 5 + i,
                    role: m?.role,
                    contentPreview: extractText(m.content).substring(0, 80)
                }));
                fileLog('agent_end - 最后 5 条消息：' + JSON.stringify(debugMessages));

                // 提取最后一轮对话（用于保存对话记录）
                const { user, assistant } = pickLastTurn(event.messages, cfg);
                fileLog('提取对话：user=' + user.substring(0, 50) + ', assistant=' + (assistant ? assistant.substring(0, 50) : 'null'));
                fileLog('缓存的用户消息：' + (cachedUserPrompt ? cachedUserPrompt.substring(0, 50) : '无'));

                // 优先使用缓存的用户原始消息（已清理系统标记），如果没有则使用 pickLastTurn 提取的
                const userContentForSave = (cachedUserPrompt && cachedUserPrompt.length >= 3) ? cachedUserPrompt : user;

                // 确定用于生成记忆的内容
                // 使用用户消息（优先缓存，其次提取的）
                let userContentForMemory = userContentForSave;
                if (!userContentForMemory || userContentForMemory.length < 5) {
                    fileLog('用户消息过短，跳过记忆生成');
                    userContentForMemory = null;
                }

                if (!userContentForSave) {
                    fileLog('未找到用户消息');
                    log.warn('[memory-exchange] 未找到用户消息');
                    return;
                }

                log.info('[memory-exchange] 准备保存对话', { user: userContentForSave.substring(0, 50), assistant: assistant?.substring(0, 50) });
                fileLog('准备保存对话');

                // 保存到数据库（使用清理后的用户消息）
                const convId = saveConversation(cfg, sessionKey, userContentForSave, assistant);
                fileLog('对话已保存，sessionKey=' + sessionKey + ', convId=' + convId);

                // 生成记忆（使用缓存的用户原始消息或 assistant 回复）
                if (convId && userContentForMemory && userContentForMemory.length >= 5) {
                    fileLog('准备生成记忆，内容长度=' + userContentForMemory.length);
                    generateMemory(cfg, userContentForMemory, assistant, convId);
                } else {
                    fileLog('消息过短，跳过记忆生成');
                }

                // 清理缓存
                userPromptCache.delete(sessionKey);

            } catch (err) {
                fileLog('agent_end 失败：' + err.message);
                log.warn('[memory-exchange] agent_end 失败:', err.message);
            }
        });
    }
};
