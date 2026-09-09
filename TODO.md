# fastTCP 待办

- [ ] **优化协议**
  - [ ] 使用MessagePack作为体
  - [ ] 重新定义协议
  - [ ] 同步项目的方法
- [ ] **对应客户端SDK开发**
  - [ ] 同样拥有路由功能`@app.route()`
  - [ ] 异步, 同步支持(实际基于异步)
- [ ] **支持软编码**
  - [x] 删除了[socket_.py](./fastTCP/socket_.py)中的`1024 bytes`硬编码, 现在默认`1MB`
  - [ ] 将`max_size`实例化, 不用调用`get_bytes_msg`在重复填参数