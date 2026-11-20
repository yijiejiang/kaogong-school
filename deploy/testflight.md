# TestFlight 上传清单

当前工程已经配置好：

- Bundle ID：`com.kaogong.school`
- 版本：`1.0.0`
- Build：`1`
- Team：`ND6298Q5HK`
- 签名：Automatic
- 最低系统：iOS 17
- 支持设备：iPhone + iPad
- App 图标：新的书本 + 对勾图标（含 1024 App Store 图标）
- 隐私清单：`ios/KaogongSchool/PrivacyInfo.xcprivacy`
- 出口合规：`ITSAppUsesNonExemptEncryption = false`
- 共享 Scheme：`KaogongSchool`

## 1. 在 App Store Connect 创建 App

需要 Apple Developer Program 账号。

1. 打开 [App Store Connect](https://appstoreconnect.apple.com/) → Apps → **+** → New App。
2. 平台选 iOS。
3. Bundle ID 选择 `com.kaogong.school`。  
   如果列表里没有，先到 [developer.apple.com](https://developer.apple.com/account/resources/identifiers) 注册这个 Bundle ID；也可以在 Xcode 里换成一个你自己的唯一 ID。
4. 填写 App 名称、Primary Language（简体中文）、SKU。
5. 创建后进入 App → TestFlight，准备接收构建。

## 2. 在 Xcode 检查签名

1. 打开 `ios/KaogongSchool.xcodeproj`。
2. 选择 Target `KaogongSchool` → Signing & Capabilities。
3. 确认：
   - Team 是你的开发者团队；
   - Automatically manage signing 已勾选；
   - Bundle Identifier 与 App Store Connect 一致。
4. 如果提示需要注册设备或创建证书，按 Xcode 提示操作。

## 3. Archive

1. Xcode 顶部设备选择 **Any iOS Device (arm64)**。
2. 菜单 Product → **Archive**。
3. 等待 Archive 完成，Organizer 会自动打开。

如果 Archive 报签名错误，先在 Signing & Capabilities 里重新选择 Team，或到 Xcode Settings → Accounts 重新登录 Apple ID。

## 4. 上传到 App Store Connect

1. Organizer 里选中刚生成的 Archive。
2. 点击 **Distribute App**。
3. 选择 **App Store Connect** → **Upload**。
4. 保持默认选项，确认签名和 API 配置。
5. 上传完成后，到 App Store Connect → TestFlight 等待构建处理完成。

也可以在 Organizer 里选择 **Validate App** 先做一次校验。

## 5. 添加测试人员

### 内部测试

1. App Store Connect → 用户和访问，邀请测试人员并分配 App 权限。
2. TestFlight → Internal Testing → 新建测试组 → 添加内部用户。
3. 选择构建版本，保存。

### 外部测试

1. TestFlight → External Testing → 新建测试组。
2. 添加测试人员邮箱。
3. 首次构建需要 **Beta App Review**，通过后测试人员会收到 TestFlight 邀请。

测试人员在 iPad/iPhone 上安装 TestFlight，接受邀请即可安装。

## 6. 每次发新构建

1. 修改 `CURRENT_PROJECT_VERSION`，例如从 `1` 改成 `2`。  
   `MARKETING_VERSION` 保持 `1.0.0` 不变，除非要发布新版本号。
2. 重新 Product → Archive → Upload。
3. TestFlight 里选择新构建。

## 7. 常见错误

### `IDEDistribution.DistributionAppRecordProviderError error 0`

这个错误表示 Xcode 找不到与当前 Archive 的 Bundle ID 匹配的 App Store Connect App 记录，常见原因：

1. App Store Connect 里还没有创建这个 App；
2. Bundle ID 还没有在开发者后台注册；
3. Xcode 登录的 Apple ID 没有这个 App/Team 的权限；
4. Archive 使用了开发签名，没有可用的 App Store 分发描述文件。

处理顺序：

1. 到 [developer.apple.com](https://developer.apple.com/account/resources/identifiers) 确认 `com.kaogong.school` 已在 Team `ND6298Q5HK` 下注册。
2. 到 App Store Connect → Apps → **+** → New App，Bundle ID 选择 `com.kaogong.school`。
3. Xcode → Settings → Accounts，确认登录的是同一个 Apple ID，并在 Team 列表里选择 `ND6298Q5HK`。
4. Xcode → Target → Signing & Capabilities，重新勾选 Automatically manage signing。
5. Product → Clean Build Folder，然后重新 Product → Archive。
6. Organizer → Distribute App → App Store Connect → Upload。

可以在终端检查是否已有该 Bundle ID 的分发描述文件：

```bash
DIR="$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles"
for f in "$DIR"/*.mobileprovision; do
  security cms -D -i "$f" 2>/dev/null | grep -q 'com.kaogong.school' \
    && echo "FOUND $f"
done
```

如果没有输出，说明还没有生成对应的描述文件，通常就是 App 记录/Bundle ID 未创建或 Team 不匹配。

## 8. 注意

- App 目前允许 HTTP（`NSAllowsArbitraryLoads`），方便局域网连接。TestFlight 内部测试没问题；正式上架审核前建议改成 HTTPS + Tailscale/Cloudflare Tunnel 地址，并移除该例外。
- 相机、本地网络权限说明已经写入 Info.plist。
- 如果后续接入账号体系、收集更多个人数据，需要在 App Store Connect 填写 App Privacy，并更新隐私清单。
- 构建号不能重复；每次上传都要递增 `CURRENT_PROJECT_VERSION`。
