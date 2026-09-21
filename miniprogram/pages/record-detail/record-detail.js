// 记录详情页：完整分析 + 对话历史 + 继续对话（反思对话的主场）
// 回看负面记录时开头温柔承接（决策 38）
const { request } = require("../../utils/api");

Page({
  data: {
    record: null,
    chatInput: "",
    sending: false,
  },

  onLoad(options) {
    this.recordId = Number(options.record_id);
    // 从结果页点引导提问跳过来时，问题自动带入输入框（决策 65）
    if (options.ask) {
      this.setData({ chatInput: decodeURIComponent(options.ask) });
    }
    this.loadRecord();
  },

  async loadRecord() {
    try {
      const record = await request(`/api/records/${this.recordId}`, "GET");
      this.setData({ record });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    }
  },

  onChatInput(e) {
    this.setData({ chatInput: e.detail.value });
  },

  // 发送对话（反思对话：AI 记得分析，引用原话解释）
  async onSend() {
    const message = this.data.chatInput.trim();
    if (!message || this.data.sending) return;
    this.setData({ sending: true });
    try {
      const res = await request("/api/chat", "POST", {
        record_id: this.recordId,
        message,
      });
      if (res.crisis) {
        wx.showModal({ title: "我在", content: res.crisis_response, showCancel: false });
      }
      if (res.score_revision) {
        // 改分留痕提示（决策 36：原分数保留，轨迹可见）
        const s = res.score_revision;
        wx.showToast({ title: `我把${s.dimension}从 ${s.old} 调整为 ${s.new}`, icon: "none", duration: 3000 });
      }
      this.setData({ chatInput: "" });
      await this.loadRecord();  // 刷新对话历史
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none", duration: 3000 });
    } finally {
      this.setData({ sending: false });
    }
  },
});
