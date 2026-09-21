// 设置页：称呼设置 + 反馈入口（决策 14、44）
const { request } = require("../../utils/api");

Page({
  data: {
    nickname: "",
    feedback: "",
    saving: false,
  },

  onShow() {
    this.loadSettings();
  },

  async loadSettings() {
    try {
      const data = await request("/api/settings", "GET");
      this.setData({ nickname: data.user_nickname || "" });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    }
  },

  onNicknameInput(e) {
    this.setData({ nickname: e.detail.value });
  },

  async onSaveNickname() {
    this.setData({ saving: true });
    try {
      await request("/api/settings", "PUT", { user_nickname: this.data.nickname });
      wx.showToast({ title: "记住了", icon: "none" });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    } finally {
      this.setData({ saving: false });
    }
  },

  onFeedbackInput(e) {
    this.setData({ feedback: e.detail.value });
  },

  async onSendFeedback() {
    if (!this.data.feedback.trim()) {
      wx.showToast({ title: "先写点反馈吧", icon: "none" });
      return;
    }
    try {
      const res = await request("/api/feedback", "POST", { content: this.data.feedback });
      this.setData({ feedback: "" });
      wx.showToast({ title: res.thanks || "谢谢你的反馈", icon: "none", duration: 2500 });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    }
  },
});
