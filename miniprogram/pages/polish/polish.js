// 润色页：独立入口（不分析也能直接润色），支持语气指定和多轮微调
const { request } = require("../../utils/api");

Page({
  data: {
    text: "",
    background: "",
    tone: "",       // 可选：预设或自然语言描述
    feedback: "",   // 多轮微调意见
    versions: [],
    lastText: "",   // 上一版润色结果（微调时带上）
    recordId: null,
    loading: false,
  },

  onLoad(options) {
    // 从分析结果页跳过来时带上记录 id（润色结果会合并进那条记录）
    if (options.record_id) {
      this.recordId = Number(options.record_id);
      this.setData({ recordId: this.recordId });
    }
  },

  onTextInput(e) { this.setData({ text: e.detail.value }); },
  onBackgroundInput(e) { this.setData({ background: e.detail.value }); },
  onToneInput(e) { this.setData({ tone: e.detail.value }); },
  onFeedbackInput(e) { this.setData({ feedback: e.detail.value }); },

  async onPolish() {
    if (!this.data.text.trim()) {
      wx.showToast({ title: "先写点要润色的话吧", icon: "none" });
      return;
    }
    this.setData({ loading: true });
    try {
      const payload = {
        text: this.data.text,
        background: this.data.background || null,
        tone: this.data.tone.trim() || null,
        record_id: this.data.recordId,
      };
      // 多轮微调：有意见时带上上一版结果
      if (this.data.feedback.trim() && this.data.lastText) {
        payload.feedback = this.data.feedback.trim();
        payload.previous = this.data.lastText;
      }
      const res = await request("/api/polish", "POST", payload);
      this.setData({
        versions: res.versions,
        lastText: res.versions[0] ? res.versions[0].text : "",
        recordId: res.record_id,
      });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none", duration: 3000 });
    } finally {
      this.setData({ loading: false });
    }
  },
});
