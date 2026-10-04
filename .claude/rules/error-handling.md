---
name: 错误处理规范
description: 适用于所有代码路径
---

## 异常捕获

```python
# ✅ 指定具体异常类型
try:
    file = open(path)
except FileNotFoundError:
    logger.warning("文件不存在: {}", path)
    return None

# ❌ 禁止裸捕获
try:
    do_something()
except:  # 吞掉 SystemExit / KeyboardInterrupt
    pass
```



## 保留异常链

```
# ✅ 保留原始错误
try:
    data = parse(raw)
except ValueError as e:
    raise MyAppError("解析失败") from e

# ❌ 丢失异常链（调试地狱）
try:
    data = parse(raw)
except ValueError as e:
    raise MyAppError("解析失败")
```



## 日志规范

```
# ✅ 结构化参数
logger.info("用户登录成功 user_id={} ip={}", user_id, ip)

# ✅ 异常日志记录堆栈
try:
    await risky_operation()
except DatabaseError:
    logger.exception("数据库操作失败")

# ❌ 泄露敏感信息
logger.info("token={}", jwt_token)  # 禁止
```