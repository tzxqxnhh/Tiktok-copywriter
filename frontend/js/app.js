/**
 * app.js -- Vue 3 应用主入口
 * 全局状态管理 + 所有业务逻辑
 */
(function () {
    var API = window.Api;

    var app = Vue.createApp({
        data: function () {
            return {
                // ===== Tab 状态 =====
                activeTab: 'generation',

                // ===== 会话状态 =====
                sessions: [],
                currentSessionId: null,

                // ===== 生成参数 =====
                productName: '',
                sellingPoints: '',
                mode: 'copywriting',
                selectedStyles: ['剧情', '痛点', '悬念'],
                copyCount: 3,
                userExpectation: '',
                directorStyle: '剧情',
                generationOutput: '*等待输入商品信息...*',
                generationError: '',
                isGenerating: false,
                styles: ['剧情', '痛点', '悬念', '干货', '对比'],

                // ===== 知识库状态 =====
                kbRows: [['-', '暂无数据', '-']],
                kbCheckboxChoices: [],
                kbDocuments: [],
                kbTotal: 0,
                kbOffset: 0,
                kbPageInfo: '第 1 页 / 共 1 页',
                kbStyleFilter: '全部',
                batchDeleteMode: false,
                showDeleteConfirm: false,
                batchSelectedIds: [],
                kbSelectedRowIdx: -1,
                kbDetailVisible: false,
                kbDetailContent: '',
                kbDetailMeta: '',
                kbFeedback: '',
                kbAddText: '',
                kbAddStyle: '剧情',
                kbAddFile: null,
                isAddingKB: false,
            };
        },

        computed: {
            /**
             * 每页条数
             */
            kbPageSize: function () {
                return 20;
            },

            /**
             * 是否最后一页
             */
            kbIsLastPage: function () {
                if (this.kbTotal === 0) return true;
                var totalPages = Math.ceil(this.kbTotal / this.kbPageSize);
                var currentPage = Math.floor(this.kbOffset / this.kbPageSize) + 1;
                return currentPage >= totalPages;
            },

            /**
             * 渲染后的 Markdown 输出
             */
            renderedOutput: function () {
                if (!this.generationOutput || this.generationOutput === '*等待输入商品信息...*') {
                    return '';
                }
                if (typeof marked !== 'undefined') {
                    return marked.parse(this.generationOutput);
                }
                // 后备：简单转义
                return '<pre>' + this._escapeHtml(this.generationOutput) + '</pre>';
            }
        },

        watch: {
            /**
             * 监听风格筛选变更（DL-1修复）
             * 使用 watcher 而非 @change 事件，
             * 确保 v-model 更新 kbStyleFilter 后再触发数据加载
             */
            kbStyleFilter: function () {
                if (this.activeTab === 'knowledge-base') {
                    this.onKbStyleChange();
                }
            }
        },

        methods: {
            // ================================================
            // Tab 切换
            // ================================================

            /**
             * 切换 Tab -- 核心修复点
             * 使用 Vue 条件渲染替代 Gradio 的 tabs.select()
             */
            switchTab: function (tab) {
                this.activeTab = tab;
                if (tab === 'knowledge-base') {
                    this.loadKbData();
                }
                // 切换到文案生成 Tab 时无需特殊处理，会话列表已在 mounted 时加载
            },

            // ================================================
            // 会话管理
            // ================================================

            /**
             * 刷新会话列表
             */
            refreshSessions: async function () {
                var result = await API.getSessions();
                if (result.error) {
                    console.error('获取会话列表失败:', result.error);
                    return;
                }
                this.sessions = result.sessions || [];
            },

            /**
             * 新建会话
             */
            onNewSession: async function () {
                var result = await API.createSession();
                if (result.error) {
                    console.error('创建会话失败:', result.error);
                    return;
                }
                this.currentSessionId = result.session_id;
                this.generationOutput = '*新会话已创建，请输入商品信息...*';
                this.generationError = '';
                await this.refreshSessions();
            },

            /**
             * 选择历史会话
             * @param {string} sessionId
             */
            onSelectSession: async function (sessionId) {
                if (!sessionId) return;
                this.currentSessionId = sessionId;

                var result = await API.getSessionMessages(sessionId);
                if (result.error) {
                    console.error('获取会话消息失败:', result.error);
                    return;
                }

                var messages = result.messages || [];
                var historyText = '';
                for (var i = 0; i < messages.length; i++) {
                    if (messages[i].msg_type === 'result') {
                        historyText = messages[i].content;
                    }
                }

                if (historyText) {
                    this.generationOutput = historyText;
                    this.generationError = '';
                } else {
                    this.generationOutput = '*暂无生成记录*';
                    this.generationError = '';
                }
            },

            /**
             * 删除会话
             * @param {string} sessionId
             */
            onDeleteSession: async function (sessionId) {
                if (!sessionId) return;

                if (!confirm('确定要删除选中的会话吗？')) return;

                var result = await API.deleteSession(sessionId);
                if (result.error) {
                    console.error('删除会话失败:', result.error);
                    return;
                }

                this.currentSessionId = null;
                this.generationOutput = '*会话已删除，请新建或选择其他会话*';
                this.generationError = '';
                this.productName = '';
                this.sellingPoints = '';
                await this.refreshSessions();
            },

            // ================================================
            // 文案生成
            // ================================================

            /**
             * 模式切换
             */
            onModeChange: function () {
                // 模式切换时重置输出
                this.generationError = '';
            },

            /**
             * 生成文案
             */
            onGenerate: async function () {
                // 前端验证
                if (!this.productName || !this.productName.trim()) {
                    this.generationError = '请输入商品名称和卖点';
                    return;
                }
                if (!this.sellingPoints || !this.sellingPoints.trim()) {
                    this.generationError = '请输入商品名称和卖点';
                    return;
                }

                if (this.mode === 'copywriting' && (!this.selectedStyles || this.selectedStyles.length === 0)) {
                    this.generationError = '请至少选择一种风格';
                    return;
                }

                this.isGenerating = true;
                this.generationError = '';
                this.generationOutput = '';

                var result = await API.generate({
                    product_name: this.productName.trim(),
                    selling_points: this.sellingPoints.trim(),
                    session_id: this.currentSessionId,
                    mode: this.mode,
                    styles: this.mode === 'copywriting' ? this.selectedStyles : null,
                    count: this.copyCount,
                    user_expectation: this.mode === 'director' ? (this.userExpectation || null) : null,
                    director_style: this.mode === 'director' ? this.directorStyle : '剧情',
                });

                this.isGenerating = false;

                if (result.error) {
                    this.generationError = result.error;
                    this.generationOutput = '';
                    return;
                }

                this.generationOutput = result.output || '';
                this.currentSessionId = result.session_id;
                await this.refreshSessions();
            },

            /**
             * 清空输入
             */
            onClear: function () {
                this.productName = '';
                this.sellingPoints = '';
                this.userExpectation = '';
                this.generationOutput = '*等待输入商品信息...*';
                this.generationError = '';
            },

            // ================================================
            // 知识库管理
            // ================================================

            /**
             * 加载知识库文档数据
             */
            loadKbData: async function () {
                var result = await API.listKB({
                    style: this.kbStyleFilter,
                    offset: this.kbOffset,
                    limit: this.kbPageSize,
                });

                if (result.error) {
                    console.error('加载知识库数据失败:', result.error);
                    this.kbFeedback = '*加载失败: ' + result.error + '*';
                    return;
                }

                this.kbRows = result.rows || [['-', '暂无数据', '-']];
                this.kbCheckboxChoices = result.checkbox_choices || [];
                this.kbDocuments = result.documents || [];
                this.kbTotal = result.total || 0;
                this.kbPageInfo = result.page_info || '第 1 页 / 共 1 页';
                this.kbSelectedRowIdx = -1;
            },

            /**
             * 风格筛选变更
             */
            onKbStyleChange: async function () {
                this.kbOffset = 0;
                this.batchDeleteMode = false;
                this.showDeleteConfirm = false;
                this.batchSelectedIds = [];
                await this.loadKbData();
            },

            /**
             * 上一页
             * 删除模式下翻页保持删除模式，仅清空当前页的勾选和确认行
             */
            onKbPrevPage: async function () {
                if (this.kbOffset <= 0) return;
                this.kbOffset = Math.max(0, this.kbOffset - this.kbPageSize);
                this.showDeleteConfirm = false;
                this.batchSelectedIds = [];
                await this.loadKbData();
            },

            /**
             * 下一页
             * 删除模式下翻页保持删除模式，仅清空当前页的勾选和确认行
             */
            onKbNextPage: async function () {
                if (this.kbIsLastPage) return;
                this.kbOffset = this.kbOffset + this.kbPageSize;
                this.showDeleteConfirm = false;
                this.batchSelectedIds = [];
                await this.loadKbData();
            },

            /**
             * 点击文档行查看详情
             * @param {number} rowIdx
             */
            onKbRowClick: function (rowIdx) {
                if (rowIdx < 0 || rowIdx >= this.kbDocuments.length) return;
                this.kbSelectedRowIdx = rowIdx;
                var doc = this.kbDocuments[rowIdx];

                this.kbDetailContent = doc.content || '';
                var meta = doc.metadata || {};
                this.kbDetailMeta =
                    '<strong>文档ID:</strong> ' + this._escapeHtml(doc.id) + '<br>' +
                    '<strong>风格:</strong> ' + this._escapeHtml(meta.style || '未分类') + '<br>' +
                    '<strong>来源:</strong> ' + this._escapeHtml(meta.source || '未知') + '<br>' +
                    '<strong>标题:</strong> ' + this._escapeHtml(meta.title || '无');
                this.kbDetailVisible = true;
            },

            // ================================================
            // 批量删除
            // ================================================

            /**
             * 进入批量删除模式（BD-1修复）
             * 重置 offset 并重新加载数据，确保固定每页20条
             */
            enterBatchDeleteMode: async function () {
                this.kbOffset = 0;
                await this.loadKbData();
                this.batchDeleteMode = true;
                this.showDeleteConfirm = false;
                this.batchSelectedIds = [];
                this.kbFeedback = '';
            },

            /**
             * 退出批量删除模式
             */
            exitBatchDeleteMode: function () {
                this.batchDeleteMode = false;
                this.showDeleteConfirm = false;
                this.batchSelectedIds = [];
                this.kbFeedback = '';
            },

            /**
             * 批量选择变更（DL-3修复）
             * 仅记录选中项，不自动弹出确认行
             * 用户需点击"删除"按钮来弹出确认行
             */
            onBatchSelectionChange: function () {
                // 当取消所有勾选时，隐藏确认行
                if (this.batchSelectedIds.length === 0) {
                    this.showDeleteConfirm = false;
                }
            },

            /**
             * 点击行切换勾选状态（BD-2新增）
             * 在删除模式下，点击整行即可勾选/取消勾选
             * 勾选框本身通过 @click.stop 阻止事件冒泡，避免重复切换
             * @param {number} rowIdx - 行索引
             */
            onToggleBatchRow: function (rowIdx) {
                var doc = this.kbDocuments[rowIdx];
                if (!doc) return;
                var docId = doc.id;
                var idx = this.batchSelectedIds.indexOf(docId);
                if (idx >= 0) {
                    this.batchSelectedIds.splice(idx, 1);
                } else {
                    this.batchSelectedIds.push(docId);
                }
                this.onBatchSelectionChange();
            },

            /**
             * 批量删除按钮点击（DL-4新增）
             * 弹出确认行，让用户二次确认
             */
            onBatchDeleteClick: function () {
                if (!this.batchSelectedIds || this.batchSelectedIds.length === 0) {
                    this.kbFeedback = '*请先选择要删除的文档*';
                    return;
                }
                this.showDeleteConfirm = true;
                this.kbFeedback = '';
            },

            /**
             * 确认批量删除
             */
            onConfirmDelete: async function () {
                if (!this.batchSelectedIds || this.batchSelectedIds.length === 0) {
                    this.kbFeedback = '*请先选择要删除的文档*';
                    return;
                }

                var result = await API.batchDeleteKB(this.batchSelectedIds);

                if (result.error) {
                    this.kbFeedback = '*删除失败: ' + result.error + '*';
                } else {
                    this.kbFeedback = '**成功删除 ' + result.deleted_count + ' 条文档**';
                }

                // 退出删除模式并刷新
                this.batchDeleteMode = false;
                this.showDeleteConfirm = false;
                this.batchSelectedIds = [];
                this.kbDetailVisible = false;
                await this.loadKbData();
            },

            /**
             * 取消删除确认（回到选择状态）
             */
            onCancelDelete: function () {
                this.showDeleteConfirm = false;
                this.batchSelectedIds = [];
            },

            // ================================================
            // 添加知识库内容
            // ================================================

            /**
             * 文件选择
             * @param {Event} event
             */
            onKbFileSelected: function (event) {
                var file = event.target.files[0];
                if (file && !file.name.endsWith('.txt')) {
                    this.kbFeedback = '*错误: 仅支持 .txt 文件*';
                    event.target.value = '';
                    this.kbAddFile = null;
                    return;
                }
                this.kbAddFile = file || null;
            },

            /**
             * 添加到知识库
             */
            onAddKnowledge: async function () {
                if (!this.kbAddText.trim() && !this.kbAddFile) {
                    this.kbFeedback = '*错误: 请提供文本内容或上传文件*';
                    return;
                }

                this.isAddingKB = true;
                this.kbFeedback = '';

                var formData = new FormData();
                formData.append('text', this.kbAddText.trim());
                formData.append('style', this.kbAddStyle);
                if (this.kbAddFile) {
                    formData.append('file', this.kbAddFile);
                }

                var result = await API.addToKB(formData);

                this.isAddingKB = false;

                if (result.error) {
                    this.kbFeedback = '*错误: ' + result.error + '*';
                } else {
                    this.kbFeedback = '**' + result.message + '**';
                    this.kbAddText = '';
                    this.kbAddFile = null;
                    // 清空文件输入
                    var fileInput = document.querySelector('input[type="file"]');
                    if (fileInput) fileInput.value = '';
                    // 刷新列表
                    await this.loadKbData();
                }
            },

            // ================================================
            // 辅助方法
            // ================================================

            /**
             * HTML 转义（防止 XSS）
             * @param {string} str
             * @returns {string}
             */
            _escapeHtml: function (str) {
                if (!str) return '';
                return String(str)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;');
            },
        },

        // ================================================
        // 生命周期
        // ================================================

        mounted: async function () {
            // 加载配置
            var config = await API.getConfig();
            if (!config.error && config.styles) {
                this.styles = config.styles;
            }

            // 加载会话列表
            await this.refreshSessions();

            // 预加载知识库数据
            await this.loadKbData();
        },
    });

    app.mount('#app');
})();
