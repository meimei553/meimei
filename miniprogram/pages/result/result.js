// 分析结果页：信息层级"先情后理"（决策 64）
// 第一眼安慰回应 → 雷达图（文字版过渡）→ 解读；引导提问可点击直接进对话（决策 65）
const { request } = require("../../utils/api");

Page({
  data: {
    record: null,
    analysis: null,
  },

  onLoad(options) {
    // 从首页带过来的记录 id，从后端取完整分析结果
    this.recordId = Number(options.record_id);
    this.loadRecord();
  },

  async loadRecord() {
    try {
      const record = await request(`/api/records/${this.recordId}`, "GET");
      this.setData({ record, analysis: record.analysis });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    }
  },

  // 点引导提问 -> 跳到记录详情页的对话区，问题自动带入（决策 65）
  onQuestion(e) {
    const question = e.currentTarget.dataset.question;
    wx.navigateTo({
      url: `/pages/record-detail/record-detail?record_id=${this.recordId}&ask=${encodeURIComponent(question)}`,
    });
  },

  // 去润色（带上原文）
  toPolish() {
    wx.navigateTo({ url: `/pages/polish/polish?record_id=${this.recordId}` });
  },
});
