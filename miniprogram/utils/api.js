// 统一 API 请求封装：所有页面通过这里调后端，失败时给温柔提示
function request(path, method, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: getApp().globalData.apiBase + path,
      method,
      data,
      success: (res) => {
        if (res.statusCode === 200) {
          resolve(res.data);
        } else {
          // 后端的温柔提示文案（detail 字段）直接透传
          reject(new Error((res.data && res.data.detail) || "请求失败"));
        }
      },
      fail: () => reject(new Error("连不上后端啦，请确认服务已启动、地址正确")),
    });
  });
}

module.exports = { request };
