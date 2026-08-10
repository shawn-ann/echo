# 百炼多模型探测报告（Model Probe Report）

| 模型 | 可用 | 思考支持 | 默认耗时(s) | 备注 |
|------|------|---------|-----------|------|
| `qwen3.7-flash` | ✅ | both | 33.3 | — |
| `qwen3.7-plus` | ✅ | both | 50.4 | — |
| `qwen3.8-max` | ✅ | both | 68.8 | — |
| `deepseek-v4-flash-0731` | ✅ | both | 5.0 | — |
| `deepseek-v4-pro` | ✅ | both | 23.8 | — |
| `glm-5.2` | ✅ | both | 13.0 | — |
| `kimi/kimi-k3` | ❌ | unknown | 0.2 | {"code":"InvalidParameter","message":"Th |
| `MiniMax/MiniMax-M3` | ❌ | unknown | 0.4 | {"error":{"message":"The product is not  |

## 探测详情

### `qwen3.7-flash`（Qwen3.7 Flash）

- `default`：✅ status=200 耗时33.3s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `thinking_disabled`：✅ status=200 耗时3.5s `{   "intent": "correction",   "correction": {     "has_error`
- `thinking_enabled`：✅ status=200 耗时28.0s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `enable_thinking_False`：✅ status=200 耗时3.4s `{   "intent": "correction",   "correction": {     "has_error`
- `enable_thinking_True`：✅ status=200 耗时23.9s `{"intent":"correction","correction":{"has_errors":true,"erro`

### `qwen3.7-plus`（Qwen3.7 Plus）

- `default`：✅ status=200 耗时50.4s `{   "intent": "correction",   "correction": {     "has_error`
- `thinking_disabled`：✅ status=200 耗时13.1s `{  "intent": "correction",  "correction": {   "has_errors": `
- `thinking_enabled`：✅ status=200 耗时59.9s `{   "intent": "correction",   "correction": {     "has_error`
- `enable_thinking_False`：✅ status=200 耗时12.4s `{  "intent": "correction",  "correction": {   "has_errors": `
- `enable_thinking_True`：✅ status=200 耗时52.6s `{   "intent": "correction",   "correction": {     "has_error`

### `qwen3.8-max`（Qwen3.8 Max）

- `default`：✅ status=200 耗时68.8s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `thinking_disabled`：✅ status=200 耗时6.7s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `thinking_enabled`：✅ status=200 耗时59.7s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `enable_thinking_False`：✅ status=200 耗时6.2s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `enable_thinking_True`：✅ status=200 耗时63.2s `{   "intent": "correction",   "correction": {     "has_error`

### `deepseek-v4-flash-0731`（DeepSeek V4 Flash）

- `default`：✅ status=200 耗时5.0s `{"intent": "correction", "correction": {"has_errors": true, `
- `thinking_disabled`：✅ status=200 耗时3.7s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `thinking_enabled`：✅ status=200 耗时18.7s `{"intent": "correction", "correction": {"has_errors": true, `

### `deepseek-v4-pro`（DeepSeek V4 Pro）

- `default`：✅ status=200 耗时23.8s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `thinking_disabled`：✅ status=200 耗时10.3s `{"intent": "correction", "correction": {"has_errors": true, `
- `thinking_enabled`：✅ status=200 耗时14.8s `{"intent":"correction","correction":{"has_errors":true,"erro`

### `glm-5.2`（GLM 5.2）

- `default`：✅ status=200 耗时13.0s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `thinking_disabled`：✅ status=200 耗时5.4s `{"intent":"correction","correction":{"has_errors":true,"erro`
- `thinking_enabled`：✅ status=200 耗时21.2s `{"intent":"correction","correction":{"has_errors":true,"erro`

### `kimi/kimi-k3`（Kimi K3）

- `default`：❌ status=400 耗时0.2s `{"code":"InvalidParameter","message":"The product is not act`
- `default_error`：{"code":"InvalidParameter","message":"The product is not activated, please confi

### `MiniMax/MiniMax-M3`（MiniMax M3）

- `default`：❌ status=400 耗时0.4s `{"error":{"message":"The product is not activated, please co`
- `default_error`：{"error":{"message":"The product is not activated, please confirm that you have 
