/**
 * api.js -- API 请求封装层
 * 所有与 FastAPI 后端的通信集中在此文件
 */
const API_BASE = '/api';

/**
 * 统一请求方法
 * @param {string} method - HTTP 方法
 * @param {string} url - API 路径
 * @param {object|null} body - 请求体
 * @param {boolean} isFormData - 是否为 FormData
 * @returns {Promise<object>} 响应数据
 */
async function apiRequest(method, url, body = null, isFormData = false) {
    const options = { method };

    if (body && method !== 'GET') {
        if (isFormData) {
            options.body = body;  // FormData，不设置 Content-Type
        } else {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(body);
        }
    }

    try {
        const response = await fetch(API_BASE + url, options);
        const contentType = response.headers.get('content-type') || '';

        // 尝试解析 JSON 响应
        if (contentType.includes('application/json')) {
            const data = await response.json();
            if (!response.ok) {
                return { error: data.detail || '请求失败 (' + response.status + ')' };
            }
            return data;
        }

        // 非 JSON 响应
        if (!response.ok) {
            return { error: '请求失败 (' + response.status + ')' };
        }
        return { message: 'OK' };
    } catch (err) {
        return { error: '网络请求失败: ' + err.message };
    }
}

/**
 * API 方法集合
 */
window.Api = {
    // ===== 配置 =====
    getConfig: function () {
        return apiRequest('GET', '/config');
    },

    // ===== 会话 =====
    getSessions: function () {
        return apiRequest('GET', '/sessions');
    },

    createSession: function (title) {
        return apiRequest('POST', '/sessions', { title: title || null });
    },

    deleteSession: function (id) {
        return apiRequest('DELETE', '/sessions/' + encodeURIComponent(id));
    },

    getSessionMessages: function (id) {
        return apiRequest('GET', '/sessions/' + encodeURIComponent(id) + '/messages');
    },

    // ===== 生成 =====
    generate: function (data) {
        return apiRequest('POST', '/generate', data);
    },

    // ===== 知识库 =====
    listKB: function (params) {
        var query = '?style=' + encodeURIComponent(params.style || '全部') +
                    '&offset=' + (params.offset || 0) +
                    '&limit=' + (params.limit || 20);
        return apiRequest('GET', '/knowledge-base' + query);
    },

    addToKB: function (formData) {
        return apiRequest('POST', '/knowledge-base', formData, true);
    },

    getKBDoc: function (id) {
        return apiRequest('GET', '/knowledge-base/' + encodeURIComponent(id));
    },

    deleteKBDoc: function (id) {
        return apiRequest('DELETE', '/knowledge-base/' + encodeURIComponent(id));
    },

    batchDeleteKB: function (ids) {
        return apiRequest('POST', '/knowledge-base/batch-delete', { ids: ids });
    }
};
