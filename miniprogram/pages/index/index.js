// 首页：粘贴内容 -> 分析 / 直接润色 / 试试示例
// 首次打开显示免责声明弹窗（决策：格式条款显著提示，同意留痕）
const { request } = require("../../utils/api");

// 开场白模板（决策 70：帮表达困难的用户开口）
const TEMPLATES = [
  "我和 ta 吵架了……",
  "我也不知道我为什么难过……",
  "今天有件事让我很开心……",
];

// 等待时的渐进式温柔文案（决策 59）
const WAITING_COPY = ["我正在认真读你的话……", "正在体会这句话背后的情绪……", "快好了……"];

// 强度四级（决策 89：与结果页用词一致）
const INTENSITY_OPTIONS = ["轻微", "明显", "强烈", "非常强烈"];

Page({
  data: {
    text: "",
    background: "",
    showGuess: false,      // 猜想区默认收起，可跳过（决策 90）
    guessEmotion: "",
    guessIntensityIndex: 0,
    intensityOptions: INTENSITY_OPTIONS,
    templates: TEMPLATES,
    loading: false,
    waitingCopy: "",
    showDisclaimer: false,
    disclaimerText: "",
  },

  onShow() {
    // 首次打开：未同意过免责声明则弹窗（同意记录存在本地，留痕）
    const agreed = wx.getStorageSync("agreed");
    if (!agreed) {
      this.setData({
        showDisclaimer: true,
        disclaimerText:
          "欢迎使用 meimei。开始使用前，请知悉：\n" +
          "1. 本工具由 AI 提供情绪分析与文本润色，所有内容仅供参考，不构成心理、医疗或法律建议。\n" +
          "2. 本工具不做任何心理诊断；危机识别为关键词 + AI 双保险，但无法承诺零漏判。\n" +
          "3. 你的数据只存储在你的设备上，不上传、不联网统计，可随时删除。\n" +
          "4. 本工具代码全部开源，谁都可以查证。\n" +
          "5. 你基于分析结果做出的行为，责任由你自己承担。",
      });
    }
  },

  onAgree() {
    wx.setStorageSync("agreed", true);
    this.setData({ showDisclaimer: false });
  },

  onTextInput(e) { this.setData({ text: e.detail.value }); },
  onBackgroundInput(e) { this.setData({ background: e.detail.value }); },
  onGuessEmotionInput(e) { this.setData({ guessEmotion: e.detail.value }); },
  onGuessIntensityChange(e) { this.setData({ guessIntensityIndex: Number(e.detail.value) }); },
  toggleGuess() { this.setData({ showGuess: !this.data.showGuess }); },

  // 开场白模板：点一下填入输入框
  onTemplate(e) {
    this.setData({ text: e.currentTarget.dataset.text });
  },

  // 试试示例（决策 41：新用户 30 秒看到产品价值）
  onExample() {
    this.setData({
      text: "我：你到底还回不回家吃饭？\n对方：随便你。\n我：你每次都这样，我受够了。",
      background: "冷战第三天，之前他答应过早点回家",
    });
  },

  // 等待文案轮播
  _startWaiting() {
    let i = 0;
    this.setData({ loading: true, waitingCopy: WAITING_COPY[0] });
    this._timer = setInterval(() => {
      i = (i + 1) % WAITING_COPY.length;
      this.setData({ waitingCopy: WAITING_COPY[i] });
    }, 2500);
  },

  _stopWaiting() {
    clearInterval(this._timer);
    this.setData({ loading: false, waitingCopy: "" });
  },

  async onAnalyze() {
    if (!this.data.text.trim()) {
      wx.showToast({ title: "先写点内容吧", icon: "none" });
      return;
    }
    this._startWaiting();
    try {
      const payload = { text: this.data.text, background: this.data.background || null };
      // 猜想了才带上（决策：猜想可跳过）
      if (this.data.showGuess && this.data.guessEmotion.trim()) {
        payload.guess = {
          emotion: this.data.guessEmotion.trim(),
          intensity: INTENSITY_OPTIONS[this.data.guessIntensityIndex],
        };
      }
      const result = await request("/api/analyze", "POST", payload);
      if (result.crisis) {
        // 危机回应：直接展示，不跳结果页
        wx.showModal({ title: "我在", content: result.crisis_response, showCancel: false });
        return;
      }
      wx.navigateTo({ url: `/pages/result/result?record_id=${result.record_id}` });
    } catch (err) {
      wx.showToast({ title: err.message, icon: "none", duration: 3000 });
    } finally {
      this._stopWaiting();
    }
  },

  // 直接润色入口（次要入口，决策 42）
  toPolish() {
    wx.navigateTo({ url: "/pages/polish/polish" });
  },
});
