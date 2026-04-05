// Bank AI Marketing Frontend - Vue 3 Application (带认证)
const { createApp, ref, reactive, onMounted } = Vue;

const app = createApp({
    setup() {
        // API 基础 URL
        const API_BASE = '/api';

        // 用户信息
        const user = reactive({
            logged_in: false,
            id: null,
            username: '',
            display_name: '',
            role: ''
        });

        // 当前激活的菜单
        const activeMenu = ref('dashboard');

        // 检查登录状态
        const checkAuth = () => {
            const token = localStorage.getItem('auth_token');
            const userInfo = localStorage.getItem('user_info');

            if (!token || !userInfo) {
                window.location.href = 'login.html';
                return false;
            }

            try {
                const info = JSON.parse(userInfo);
                user.logged_in = true;
                user.id = info.id;
                user.username = info.username;
                user.display_name = info.display_name;
                user.role = info.role;
                return true;
            } catch (e) {
                window.location.href = 'login.html';
                return false;
            }
        };

        // 退出登录
        const handleLogout = () => {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('user_info');
            ElementPlus.ElMessage.success('已退出登录');
            window.location.href = 'login.html';
        };

        // 统计数据
        const stats = reactive({
            total_customers: 0,
            total_calls: 0,
            total_campaigns: 0,
            pending_followups: 0
        });

        // 最近通话
        const recentCalls = ref([]);

        // 通话记录
        const calls = ref([]);
        const callsLoading = ref(false);
        const callsPage = ref(1);
        const callsPageSize = ref(20);
        const callsTotal = ref(0);
        const callFilters = reactive({
            status: '',
            result: ''
        });

        // 客户列表
        const customers = ref([]);
        const customersLoading = ref(false);
        const customersPage = ref(1);
        const customersPageSize = ref(20);
        const customersTotal = ref(0);
        const customerFilters = reactive({
            intent_level: '',
            search: ''
        });

        // 活动列表
        const campaigns = ref([]);

        // 脚本模板
        const scripts = ref([]);

        // 跟进计划
        const followups = ref([]);

        // 对话框
        const showAddCustomerDialog = ref(false);
        const showAddCampaignDialog = ref(false);
        const showAddScriptDialog = ref(false);

        // 编辑/查看对话框
        const showEditCustomerDialog = ref(false);
        const showEditCampaignDialog = ref(false);
        const showViewScriptDialog = ref(false);
        const showEditScriptDialog = ref(false);
        const showViewCallDialog = ref(false);
        const showViewCustomerDialog = ref(false);

        // 分析状态
        const analyzing = ref(false);

        // 当前编辑/查看的对象
        const currentCustomer = reactive({});
        const currentCampaign = reactive({});
        const currentScript = reactive({});
        const currentCall = reactive({});

        // 新增客户表单
        const newCustomer = reactive({
            phone_number: '',
            name: '',
            gender: 'unknown',
            age_range: 'unknown',
            city: ''
        });

        // 新增活动表单
        const newCampaign = reactive({
            name: '',
            service_type: '',
            target_count: 100,
            start_date: '',
            end_date: ''
        });

        // 新增脚本表单
        const newScript = reactive({
            name: '',
            service_type: '',
            max_turns: 10,
            tone: 'friendly'
        });

        // 获取认证头
        const getAuthHeaders = () => {
            const token = localStorage.getItem('auth_token');
            return {
                'Content-Type': 'application/json',
                'Authorization': token ? `Bearer ${token}` : ''
            };
        };

        // 菜单选择处理
        const handleMenuSelect = (index) => {
            activeMenu.value = index;
            loadData(index);
        };

        // 加载数据
        const loadData = (menu) => {
            switch(menu) {
                case 'dashboard':
                    loadStats();
                    break;
                case 'calls':
                    loadCalls();
                    break;
                case 'customers':
                    loadCustomers();
                    break;
                case 'campaigns':
                    loadCampaigns();
                    break;
                case 'scripts':
                    loadScripts();
                    break;
                case 'followups':
                    loadFollowups();
                    break;
            }
        };

        // 加载统计数据
        const loadStats = async () => {
            try {
                const res = await fetch(`${API_BASE}/stats`, { headers: getAuthHeaders() });
                const data = await res.json();
                Object.assign(stats, data);
            } catch (e) {
                console.error('加载统计数据失败:', e);
            }
        };

        // 加载通话记录
        const loadCalls = async () => {
            callsLoading.value = true;
            try {
                const params = new URLSearchParams({
                    page: callsPage.value,
                    per_page: callsPageSize.value
                });
                if (callFilters.status) params.append('status', callFilters.status);
                if (callFilters.result) params.append('result', callFilters.result);

                const res = await fetch(`${API_BASE}/calls?${params}`, { headers: getAuthHeaders() });
                const data = await res.json();
                calls.value = data.items;
                callsTotal.value = data.total;
            } catch (e) {
                console.error('加载通话记录失败:', e);
            } finally {
                callsLoading.value = false;
            }
        };

        // 加载客户列表
        const loadCustomers = async () => {
            customersLoading.value = true;
            try {
                const params = new URLSearchParams({
                    page: customersPage.value,
                    per_page: customersPageSize.value
                });
                if (customerFilters.intent_level) params.append('intent_level', customerFilters.intent_level);
                if (customerFilters.search) params.append('search', customerFilters.search);

                const res = await fetch(`${API_BASE}/customers?${params}`, { headers: getAuthHeaders() });
                const data = await res.json();
                customers.value = data.items;
                customersTotal.value = data.total;
            } catch (e) {
                console.error('加载客户列表失败:', e);
            } finally {
                customersLoading.value = false;
            }
        };

        // 加载活动列表
        const loadCampaigns = async () => {
            try {
                const res = await fetch(`${API_BASE}/campaigns`, { headers: getAuthHeaders() });
                campaigns.value = await res.json();
            } catch (e) {
                console.error('加载活动列表失败:', e);
            }
        };

        // 加载脚本模板
        const loadScripts = async () => {
            try {
                const res = await fetch(`${API_BASE}/scripts`, { headers: getAuthHeaders() });
                scripts.value = await res.json();
            } catch (e) {
                console.error('加载脚本模板失败:', e);
            }
        };

        // 加载跟进计划
        const loadFollowups = async () => {
            try {
                const res = await fetch(`${API_BASE}/followups?status=pending`, { headers: getAuthHeaders() });
                followups.value = await res.json();
            } catch (e) {
                console.error('加载跟进计划失败:', e);
            }
        };

        // 添加客户
        const addCustomer = async () => {
            try {
                const res = await fetch(`${API_BASE}/customers`, {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(newCustomer)
                });
                if (res.ok) {
                    ElementPlus.ElMessage.success('客户添加成功');
                    showAddCustomerDialog.value = false;
                    loadCustomers();
                } else {
                    const err = await res.json();
                    ElementPlus.ElMessage.error(err.error || '添加失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('添加失败：' + e.message);
            }
        };

        // 添加活动
        const addCampaign = async () => {
            try {
                const res = await fetch(`${API_BASE}/campaigns`, {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(newCampaign)
                });
                if (res.ok) {
                    ElementPlus.ElMessage.success('活动添加成功');
                    showAddCampaignDialog.value = false;
                    loadCampaigns();
                } else {
                    const err = await res.json();
                    ElementPlus.ElMessage.error(err.error || '添加失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('添加失败：' + e.message);
            }
        };

        // 添加脚本
        const addScript = async () => {
            try {
                const res = await fetch(`${API_BASE}/scripts`, {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(newScript)
                });
                if (res.ok) {
                    ElementPlus.ElMessage.success('脚本添加成功');
                    showAddScriptDialog.value = false;
                    loadScripts();
                } else {
                    const err = await res.json();
                    ElementPlus.ElMessage.error(err.error || '添加失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('添加失败：' + e.message);
            }
        };

        // 查看通话详情
        const viewCallDetail = async (callId) => {
            try {
                const res = await fetch(`${API_BASE}/calls/${callId}`, { headers: getAuthHeaders() });
                if (res.ok) {
                    const data = await res.json();
                    Object.assign(currentCall, data);
                    showViewCallDialog.value = true;
                } else {
                    ElementPlus.ElMessage.error('获取通话详情失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('获取失败：' + e.message);
            }
        };

        // 导出通话记录 Markdown
        const exportCallMarkdown = (callId) => {
            window.open(`${API_BASE}/export/call/${callId}/markdown`, '_blank');
            ElementPlus.ElMessage.success('开始导出 Markdown 文件');
        };

        // 使用 AI 分析通话记录
        const analyzeCallWithLLM = async (callId) => {
            analyzing.value = true;
            try {
                const res = await fetch(`${API_BASE}/export/call/${callId}/analyze`, {
                    method: 'POST',
                    headers: getAuthHeaders()
                });
                if (res.ok) {
                    const result = await res.json();
                    if (result.success) {
                        ElementPlus.ElMessage.success('AI 分析完成');
                        // 刷新通话详情
                        await viewCallDetail(callId);
                    } else {
                        ElementPlus.ElMessage.error('分析失败：' + (result.error || '未知错误'));
                    }
                } else {
                    ElementPlus.ElMessage.error('分析失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('分析错误：' + e.message);
            } finally {
                analyzing.value = false;
            }
        };

        // 查看客户详情
        const viewCustomer = async (customerId) => {
            try {
                const res = await fetch(`${API_BASE}/customers/${customerId}`, { headers: getAuthHeaders() });
                if (res.ok) {
                    const data = await res.json();
                    Object.assign(currentCustomer, data);
                    showViewCustomerDialog.value = true;
                } else {
                    ElementPlus.ElMessage.error('获取客户详情失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('获取失败：' + e.message);
            }
        };

        // 编辑客户
        const editCustomer = async (customerId) => {
            try {
                const res = await fetch(`${API_BASE}/customers/${customerId}`, { headers: getAuthHeaders() });
                if (res.ok) {
                    const data = await res.json();
                    Object.assign(currentCustomer, data);
                    showEditCustomerDialog.value = true;
                } else {
                    ElementPlus.ElMessage.error('获取客户信息失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('获取失败：' + e.message);
            }
        };

        // 更新客户
        const updateCustomer = async () => {
            try {
                const res = await fetch(`${API_BASE}/customers/${currentCustomer.id}`, {
                    method: 'PUT',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(currentCustomer)
                });
                if (res.ok) {
                    ElementPlus.ElMessage.success('客户更新成功');
                    showEditCustomerDialog.value = false;
                    loadCustomers();
                } else {
                    const err = await res.json();
                    ElementPlus.ElMessage.error(err.error || '更新失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('更新失败：' + e.message);
            }
        };

        // 编辑活动
        const editCampaign = async (campaignId) => {
            try {
                const res = await fetch(`${API_BASE}/campaigns/${campaignId}`, { headers: getAuthHeaders() });
                if (res.ok) {
                    const data = await res.json();
                    Object.assign(currentCampaign, data);
                    showEditCampaignDialog.value = true;
                } else {
                    ElementPlus.ElMessage.error('获取活动信息失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('获取失败：' + e.message);
            }
        };

        // 更新活动
        const updateCampaign = async () => {
            try {
                const res = await fetch(`${API_BASE}/campaigns/${currentCampaign.id}`, {
                    method: 'PUT',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(currentCampaign)
                });
                if (res.ok) {
                    ElementPlus.ElMessage.success('活动更新成功');
                    showEditCampaignDialog.value = false;
                    loadCampaigns();
                } else {
                    const err = await res.json();
                    ElementPlus.ElMessage.error(err.error || '更新失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('更新失败：' + e.message);
            }
        };

        // 查看脚本
        const viewScript = async (scriptId) => {
            try {
                const res = await fetch(`${API_BASE}/scripts/${scriptId}`, { headers: getAuthHeaders() });
                if (res.ok) {
                    const data = await res.json();
                    Object.assign(currentScript, data);
                    showViewScriptDialog.value = true;
                } else {
                    ElementPlus.ElMessage.error('获取脚本失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('获取失败：' + e.message);
            }
        };

        // 编辑脚本
        const editScript = async (scriptId) => {
            try {
                const res = await fetch(`${API_BASE}/scripts/${scriptId}`, { headers: getAuthHeaders() });
                if (res.ok) {
                    const data = await res.json();
                    Object.assign(currentScript, data);
                    showEditScriptDialog.value = true;
                } else {
                    ElementPlus.ElMessage.error('获取脚本失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('获取失败：' + e.message);
            }
        };

        // 更新脚本
        const updateScript = async () => {
            try {
                const res = await fetch(`${API_BASE}/scripts/${currentScript.id}`, {
                    method: 'PUT',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(currentScript)
                });
                if (res.ok) {
                    ElementPlus.ElMessage.success('脚本更新成功');
                    showEditScriptDialog.value = false;
                    loadScripts();
                } else {
                    const err = await res.json();
                    ElementPlus.ElMessage.error(err.error || '更新失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('更新失败：' + e.message);
            }
        };

        // 完成跟进
        const completeFollowup = async (followupId) => {
            try {
                const res = await fetch(`${API_BASE}/followups/${followupId}`, {
                    method: 'PUT',
                    headers: getAuthHeaders(),
                    body: JSON.stringify({ status: 'completed' })
                });
                if (res.ok) {
                    ElementPlus.ElMessage.success('跟进已完成');
                    loadFollowups();
                } else {
                    const err = await res.json();
                    ElementPlus.ElMessage.error(err.error || '完成失败');
                }
            } catch (e) {
                ElementPlus.ElMessage.error('完成失败：' + e.message);
            }
        };

        // 获取状态标签类型
        const getStatusType = (status) => {
            const types = {
                'answered': 'success',
                'completed': 'success',
                'no_answer': 'warning',
                'busy': 'danger',
                'failed': 'danger'
            };
            return types[status] || 'info';
        };

        // 获取意向等级标签类型
        const getIntentType = (level) => {
            const types = {
                'hot': 'danger',
                'warm': 'warning',
                'cold': 'info',
                'converted': 'success'
            };
            return types[level] || 'info';
        };

        // 获取角色类型
        const getRoleType = (role) => {
            const types = {
                'admin': 'danger',
                'supervisor': 'warning',
                'operator': 'success'
            };
            return types[role] || 'info';
        };

        // 获取角色名称
        const getRoleName = (role) => {
            const names = {
                'admin': '管理员',
                'supervisor': '主管',
                'operator': '坐席员'
            };
            return names[role] || role;
        };

        // 初始化
        onMounted(() => {
            if (checkAuth()) {
                loadStats();
            }
        });

        return {
            user,
            activeMenu,
            stats,
            recentCalls,
            calls,
            callsLoading,
            callsPage,
            callsPageSize,
            callsTotal,
            callFilters,
            customers,
            customersLoading,
            customersPage,
            customersPageSize,
            customersTotal,
            customerFilters,
            campaigns,
            scripts,
            followups,
            showAddCustomerDialog,
            showAddCampaignDialog,
            showAddScriptDialog,
            showEditCustomerDialog,
            showEditCampaignDialog,
            showViewScriptDialog,
            showEditScriptDialog,
            showViewCallDialog,
            showViewCustomerDialog,
            analyzing,
            currentCustomer,
            currentCampaign,
            currentScript,
            currentCall,
            newCustomer,
            newCampaign,
            newScript,
            handleMenuSelect,
            handleLogout,
            loadCalls,
            loadCustomers,
            loadCampaigns,
            loadScripts,
            loadFollowups,
            addCustomer,
            addCampaign,
            addScript,
            updateCustomer,
            updateCampaign,
            updateScript,
            viewCallDetail,
            exportCallMarkdown,
            analyzeCallWithLLM,
            getStatusType,
            getIntentType,
            getRoleType,
            getRoleName,
            viewCustomer,
            editCustomer,
            editCampaign,
            viewScript,
            editScript,
            completeFollowup
        };
    }
});

app.use(ElementPlus);
app.mount('#app');
