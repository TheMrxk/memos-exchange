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

// 默认配置
const DEFAULT_CONFIG = {
    enabled: true,
    memoryLimitNumber: 6,
    preferenceLimitNumber: 6,
    minScore: 0.3,
    includeAssistant: true,
    maxMessageChars: 5000,
    searchEngine: join(homedir(), '.openclaw', 'workspace', 'memory-exchange', 'src', 'memory-exchange-plugin', 'search_engine.py'),
    databasePath: join(homedir(), '.openclaw', 'workspace', 'memory-exchange.db'),
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
    try {
        const cmd = `${cfg.pythonPath} "${cfg.searchEngine}" add --type preference "${userContent}"`;
        execSync(cmd, {
            encoding: 'utf8',
            timeout: 5000,
            stdio: ['pipe', 'pipe', 'pipe']
        });
    } catch (err) {
        console.warn('[memory-exchange] 保存对话失败:', err.message);
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

    return { user: userContent, assistant: assistantContent };
}

module.exports = {
    id: 'memory-exchange-plugin',
    name: 'Memory Exchange 本地记忆',
    description: '本地记忆存储和检索插件',
    kind: 'lifecycle',

    register(api) {
        const cfg = buildConfig(api.pluginConfig);
        const log = api.logger ?? console;

        if (!cfg.enabled) {
            log.info('[memory-exchange] 插件已禁用');
            return;
        }

        log.info('[memory-exchange] 插件已注册');

        // 对话前钩子 - 检索记忆并注入
        api.on('before_agent_start', async (event, ctx) => {
            try {
                const userPrompt = event?.prompt || '';
                if (!userPrompt || userPrompt.length < 3) {
                    return;
                }

                // 检索记忆
                const memories = searchMemories(cfg, userPrompt, cfg.memoryLimitNumber);

                if (!memories || memories.length === 0) {
                    return;
                }

                // 格式化为注入文本
                const injectionText = formatMemoriesForInjection(memories);

                if (injectionText) {
                    // 注入到系统上下文
                    return {
                        appendSystemContext: injectionText
                    };
                }
            } catch (err) {
                log.warn('[memory-exchange] before_agent_start 失败:', err.message);
            }
        });

        // 对话后钩子 - 保存对话
        api.on('agent_end', async (event, ctx) => {
            try {
                if (!event?.success || !event?.messages?.length) {
                    return;
                }

                // 提取最后一轮对话
                const { user, assistant } = pickLastTurn(event.messages, cfg);

                if (!user) {
                    return;
                }

                // 保存到数据库
                const sessionKey = ctx?.sessionKey || ctx?.sessionId || 'default-session';
                saveConversation(cfg, sessionKey, user, assistant);

            } catch (err) {
                log.warn('[memory-exchange] agent_end 失败:', err.message);
            }
        });
    }
};
