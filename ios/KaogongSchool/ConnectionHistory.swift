import Foundation

struct ConnectionRecord: Codable, Identifiable, Equatable {
    let url: String
    let userId: String
    var lastUsed: Date

    var id: String { "\(url)|\(userId)" }

    var host: String {
        URL(string: url)?.host ?? url
    }

    var displayName: String {
        if host.hasSuffix(".ts.net") {
            return "Tailscale · \(host)"
        }
        if host.hasPrefix("192.168.")
            || host.hasPrefix("10.")
            || host.hasPrefix("172.") {
            return "局域网 · \(host)"
        }
        if host == "127.0.0.1" || host == "localhost" {
            return "本机 · \(host)"
        }
        return host
    }

    var detail: String {
        var value = url
        if !userId.isEmpty {
            value += " · 学习者 \(userId)"
        }
        return value
    }
}

enum ConnectionHistory {
    private static let key = "connectionHistory"
    static let limit = 8

    static func load() -> [ConnectionRecord] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let records = try? JSONDecoder().decode(
                [ConnectionRecord].self,
                from: data
              )
        else {
            return []
        }
        return records.sorted { $0.lastUsed > $1.lastUsed }
    }

    @discardableResult
    static func record(url: String, userId: String) -> [ConnectionRecord] {
        let normalized = url.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return load() }
        var records = load()
        records.removeAll {
            $0.url == normalized && $0.userId == userId
        }
        records.insert(
            ConnectionRecord(
                url: normalized,
                userId: userId,
                lastUsed: Date()
            ),
            at: 0
        )
        if records.count > limit {
            records = Array(records.prefix(limit))
        }
        save(records)
        return records
    }

    @discardableResult
    static func remove(id: String) -> [ConnectionRecord] {
        var records = load()
        records.removeAll { $0.id == id }
        save(records)
        return records
    }

    private static func save(_ records: [ConnectionRecord]) {
        guard let data = try? JSONEncoder().encode(records) else { return }
        UserDefaults.standard.set(data, forKey: key)
    }
}
