// 记录列表页：情绪筛选 + 删除 + 陪伴文案 + 空状态引导
const { request } = require("../../utils/api");

Page({
  data: {
    records: [],
    companion: "",
    emotion: "",  // 筛选条件（空为全部）
  },

  onShow() {
    this.loadRecords();
  },

  async loadRecords() {
    try {
      const path = this.data.emotion
        ? `/api/records?emotion=${encodeURIComponent(this.data.emotion)}`
        : "/api/records";
      const data = await request(path, "GET");
      this.setData({ records: data.records, companion: data.companion });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    }
  },

  onEmotionInput(e) {
    this.setData({ emotion: e.detail.value });
  },

  onSearch() {
    this.loadRecords();
  },

  // 清空筛选
  onClearFilter() {
    this.setData({ emotion: "" }, () => this.loadRecords());
  },

  toDetail(e) {
    wx.navigateTo({ url: `/pages/record-detail/record-detail?record_id=${e.currentTarget.dataset.id}` });
  },

  // 删除（私密工具：想删就删得掉）
  async onDelete(e) {
    const id = e.currentTarget.dataset.id;
    const res = await wx.showModal({ title: "删除这条记录？", content: "删了就找不回来了", confirmText: "删除" });
    if (!res.confirm) return;
    try {
      await request(`/api/records/${id}`, "DELETE");
      this.loadRecords();
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none" });
    }
  },
});
