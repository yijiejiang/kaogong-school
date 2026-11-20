# Tailscale 私有远程访问

目标：让 iPad / iPhone 在外网也能连回家里的 Mac，但不把服务直接暴露到公网。
Tailscale 会在 Mac 和 iPad 之间建立私有网络（tailnet），只有登录同一账号的设备能访问。

> 适合个人使用。Mac 必须保持开机；如果 Mac 睡眠，服务会不可达。

## 1. 安装并登录 Tailscale

Mac：

```bash
brew install --cask tailscale
open -a Tailscale
```

也可以从 [tailscale.com/download](https://tailscale.com/download) 安装。登录你的账号。

iPad：

- App Store 安装 **Tailscale**；
- 用**同一个账号**登录；
- 确认 iPad 和 Mac 在同一个 tailnet。

如果 Mac 上 `tailscale` 命令不在 PATH（App Store 版本常见），可以这样调用：

```bash
/Applications/Tailscale.app/Contents/MacOS/Tailscale status
```

下文用 `tailscale` 表示这个命令，可替换成上面的完整路径。

## 2. 启动后端

Tailscale Serve 会从 tailnet 代理到本机 `127.0.0.1:8000`，所以后端不需要暴露到局域网：

```bash
make backend        # 监听 127.0.0.1:8000
# 或
make install-service
```

确认本机可访问：

```bash
curl http://127.0.0.1:8000/api/health
```

## 3. 开启 Tailscale Serve

在 Tailscale 管理后台确认已启用 **MagicDNS** 和 **HTTPS Certificates**。

```bash
make tailscale-serve
```

等价于：

```bash
tailscale serve --bg 8000
tailscale serve status
```

`serve status` 会显示类似地址：

```
https://mac-mini.tailxxxx.ts.net
```

先在本机验证：

```bash
curl https://mac-mini.tailxxxx.ts.net/api/health
```

如果提示证书未启用，到 Tailscale 管理后台打开 HTTPS，或执行：

```bash
tailscale cert mac-mini.tailxxxx.ts.net
```

## 4. 配置 PUBLIC_BASE_URL

编辑 `backend/.env`：

```bash
PUBLIC_BASE_URL=https://mac-mini.tailxxxx.ts.net
```

重启后端。然后确认：

```bash
curl http://127.0.0.1:8000/api/connect/info
```

应返回：

```json
{
  "api_base": "https://mac-mini.tailxxxx.ts.net",
  "source": "public"
}
```

打开网页端「设置 → 用 iPad / iPhone 扫码连接」，二维码现在会编码这个 HTTPS 地址。

## 5. iPad 扫码连接

1. iPad 确认 Tailscale 已连接；
2. 打开考公私塾 App → 设置 → **扫码连接后端**；
3. 扫描网页上的二维码；
4. App 会自动写入 `https://mac-mini.tailxxxx.ts.net`，并重新加载设置。

也可以直接用 iPad 系统相机扫码，系统确认「在考公私塾中打开」后同样生效。

## 6. 保持 Mac 可访问

Tailscale 只能解决网络可达性，不能阻止 Mac 睡眠。个人长期使用建议：

```bash
caffeinate -dimsu
```

或者使用 Amphetamine、把 Mac 的睡眠设为永不。台式 Mac / Mac mini 更适合常驻。

## 7. 安全建议

- 不要开启 Tailscale Funnel（那是公网暴露），个人使用保持 tailnet 私有即可。
- 用 Tailscale ACL 限制只有自己的设备能访问这台 Mac。
- 不需要在 App 里再加登录；tailnet 本身就是访问边界。
- 如果以后开放给其他人使用，再考虑加应用层登录和每个用户独立的 `user_id`。

## 8. 常见问题

**iPad 打不开地址**

- iPad 的 Tailscale 是否已连接；
- `tailscale serve status` 是否显示 HTTPS 地址；
- Mac 是否睡眠；
- 用 iPad Safari 先访问 `https://mac-mini.tailxxxx.ts.net/api/health`。

**二维码仍然是局域网 IP**

- `PUBLIC_BASE_URL` 没有设置，或后端没有重启；
- 检查 `curl http://127.0.0.1:8000/api/connect/info` 的 `source` 是否为 `public`。

**证书错误**

- Tailscale 管理后台未启用 HTTPS Certificates；
- 域名必须是完整的 `*.ts.net` 地址，不要用 `http://`。

**重启后 Serve 失效**

- `tailscale serve` 配置通常会保留；失效时重新执行 `make tailscale-serve`。
- 停止代理：`make tailscale-stop`（等价于 `tailscale serve reset`）。
