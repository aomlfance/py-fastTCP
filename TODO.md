# fastTCP 待办

- [ ] **优化协议**
  - [ ] 使用MessagePack作为体
  - [ ] 重新定义协议
  - [ ] 同步项目的方法
- [ ] **对应客户端SDK开发**
  - [x] 同样拥有路由功能`@app.route()`
  - [x] 请求的实现(基于队列`deque`)
- [x] **超时支持**
- [ ] **支持软编码**
  - [x] 删除了[socket_.py](./fastTCP/socket_.py)中的`1024 bytes`硬编码, 现在默认`1MB`
  - [x] 将`max_size`实例化, 不用调用`get_bytes_msg`在重复填参数
- [ ] **TLS支持**
- [ ] **read()串行处理(server也搞个队列)**
- [ ] **socket储存状态支持**

