// 首页：粘贴内容 -> 分析情绪 -> 润色，打通后端 API 的最小实现
// 注意：这里只验证功能闭环，UI 设计留待二期讨论
const app = getApp();

Page({
  data: {
    text: "",        // 用户粘贴的聊天记录或气话
    scene: "",       // 场景（可选）：情侣/职场/家庭/朋友
    analysis: null,  // 分析结果
    polish: null,    // 润色结果
    recordId: null,  // 后端自动保存的记录 id（润色时带上，合并成一条反思记录）
    loading: false,
  },

  onTextInput(e) {
    this.setData({ text: e.detail.value });
  },

  onSceneInput(e) {
    this.setData({ scene: e.detail.value });
  },

  // 调用后端接口的通用方法
  request(path, data) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: app.globalData.apiBase + path,
        method: "POST",
        data,
        success: (res) => {
          if (res.statusCode === 200) {
            resolve(res.data);
          } else {
            reject(new Error((res.data && res.data.detail) || "请求失败"));
          }
        },
        fail: () => reject(new Error("连不上后端，请确认服务已启动、地址正确")),
      });
    });
  },

  async onAnalyze() {
    if (!this.data.text.trim()) {
      wx.showToast({ title: "先粘贴点内容吧", icon: "none" });
      return;
    }
    this.setData({ loading: true, analysis: null, polish: null });
    try {
      const analysis = await this.request("/api/analyze", {
        text: this.data.text,
        scene: this.data.scene || null,
      });
      this.setData({ analysis, recordId: analysis.record_id });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  async onPolish() {
    this.setData({ loading: true });
    try {
      const polish = await this.request("/api/polish", {
        text: this.data.text,
        record_id: this.data.recordId, // 合并到分析那条记录里
      });
      this.setData({ polish });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },
});
