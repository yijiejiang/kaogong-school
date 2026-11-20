import SwiftUI

struct MarkdownText: View {
    let content: String

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            ForEach(Array(MarkdownBlock.parse(content).enumerated()), id: \.offset) { _, block in
                block.view
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private enum MarkdownBlock {
    case heading(level: Int, text: String)
    case paragraph(String)
    case bullet(marker: String, text: String)
    case quote(String)
    case code(String)
    case table([[String]])
    case divider

    @ViewBuilder
    var view: some View {
        switch self {
        case .heading(let level, let text):
            Text(MarkdownBlock.inline(text))
                .font(.system(size: headingSize(level), weight: .bold))
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)

        case .paragraph(let text):
            Text(MarkdownBlock.inline(text))
                .font(.subheadline)
                .foregroundStyle(Theme.ink)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)

        case .bullet(let marker, let text):
            HStack(alignment: .top, spacing: 7) {
                Text(marker)
                    .font(.subheadline)
                    .foregroundStyle(Theme.accent)
                    .frame(minWidth: 16, alignment: .trailing)
                Text(MarkdownBlock.inline(text))
                    .font(.subheadline)
                    .foregroundStyle(Theme.ink)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
            }

        case .quote(let text):
            HStack(alignment: .top, spacing: 9) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Theme.accent.opacity(0.45))
                    .frame(width: 3)
                Text(MarkdownBlock.inline(text))
                    .font(.subheadline)
                    .foregroundStyle(Theme.muted)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
            }

        case .code(let text):
            ScrollView(.horizontal, showsIndicators: false) {
                Text(text)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(Theme.ink)
                    .textSelection(.enabled)
                    .padding(10)
            }
            .background(Theme.codeBackground)
            .overlay(
                RoundedRectangle(cornerRadius: 9).stroke(Theme.line)
            )
            .clipShape(RoundedRectangle(cornerRadius: 9))

        case .table(let rows):
            ScrollView(.horizontal, showsIndicators: false) {
                Grid(alignment: .leading, horizontalSpacing: 14, verticalSpacing: 7) {
                    ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                        GridRow {
                            ForEach(Array(row.enumerated()), id: \.offset) { _, cell in
                                Text(MarkdownBlock.inline(cell))
                                    .font(.caption)
                                    .fontWeight(index == 0 ? .semibold : .regular)
                                    .foregroundStyle(Theme.ink)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .padding(.vertical, 3)
                            }
                        }
                        if index == 0 {
                            Divider()
                        }
                    }
                }
                .padding(10)
            }
            .background(Theme.paper)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line))
            .clipShape(RoundedRectangle(cornerRadius: 9))

        case .divider:
            Divider().background(Theme.line)
        }
    }

    private func headingSize(_ level: Int) -> CGFloat {
        switch level {
        case 1: return 21
        case 2: return 18
        case 3: return 16
        default: return 15
        }
    }

    static func inline(_ text: String) -> AttributedString {
        let options = AttributedString.MarkdownParsingOptions(
            interpretedSyntax: .inlineOnlyPreservingWhitespace,
            failurePolicy: .returnPartiallyParsedIfPossible
        )
        return (try? AttributedString(markdown: text, options: options))
            ?? AttributedString(text)
    }

    static func parse(_ content: String) -> [MarkdownBlock] {
        let normalized = content.replacingOccurrences(of: "\r\n", with: "\n")
        let lines = normalized.components(separatedBy: "\n")
        var blocks: [MarkdownBlock] = []
        var index = 0

        while index < lines.count {
            let line = lines[index]
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            if trimmed.isEmpty {
                index += 1
                continue
            }

            if trimmed.hasPrefix("```") {
                index += 1
                var code: [String] = []
                while index < lines.count,
                      !lines[index].trimmingCharacters(in: .whitespaces)
                        .hasPrefix("```") {
                    code.append(lines[index])
                    index += 1
                }
                if index < lines.count { index += 1 }
                blocks.append(.code(code.joined(separator: "\n")))
                continue
            }

            if let heading = heading(trimmed) {
                blocks.append(.heading(level: heading.level, text: heading.text))
                index += 1
                continue
            }

            if isTableStart(lines, at: index) {
                var rows: [[String]] = []
                while index < lines.count, lines[index].contains("|") {
                    let cells = tableCells(lines[index])
                    if !isTableSeparator(lines[index]) {
                        rows.append(cells)
                    }
                    index += 1
                }
                if !rows.isEmpty {
                    blocks.append(.table(rows))
                }
                continue
            }

            if trimmed.hasPrefix(">") {
                var quote: [String] = []
                while index < lines.count {
                    let current = lines[index].trimmingCharacters(in: .whitespaces)
                    guard current.hasPrefix(">") else { break }
                    quote.append(
                        String(current.dropFirst())
                            .trimmingCharacters(in: .whitespaces)
                    )
                    index += 1
                }
                blocks.append(.quote(quote.joined(separator: "\n")))
                continue
            }

            if let marker = listMarker(line) {
                blocks.append(.bullet(marker: marker.marker, text: marker.text))
                index += 1
                continue
            }

            if isDivider(trimmed) {
                blocks.append(.divider)
                index += 1
                continue
            }

            var paragraph: [String] = [line]
            index += 1
            while index < lines.count {
                let next = lines[index]
                let nextTrimmed = next.trimmingCharacters(in: .whitespaces)
                if nextTrimmed.isEmpty
                    || heading(nextTrimmed) != nil
                    || isTableStart(lines, at: index)
                    || nextTrimmed.hasPrefix(">")
                    || nextTrimmed.hasPrefix("```")
                    || listMarker(next) != nil
                    || isDivider(nextTrimmed) {
                    break
                }
                paragraph.append(next)
                index += 1
            }
            blocks.append(
                .paragraph(
                    paragraph.joined(separator: "\n")
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                )
            )
        }

        return blocks
    }

    private static func heading(
        _ line: String
    ) -> (level: Int, text: String)? {
        let hashes = line.prefix { $0 == "#" }
        guard !hashes.isEmpty, hashes.count <= 6 else { return nil }
        let rest = line.dropFirst(hashes.count)
        guard rest.hasPrefix(" ") else { return nil }
        let text = rest.trimmingCharacters(in: .whitespaces)
        return text.isEmpty ? nil : (hashes.count, text)
    }

    private static func listMarker(
        _ line: String
    ) -> (marker: String, text: String)? {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        guard let first = trimmed.first else { return nil }
        if ["-", "*", "+"].contains(first) {
            let rest = trimmed.dropFirst()
            guard rest.hasPrefix(" ") else { return nil }
            let text = rest.trimmingCharacters(in: .whitespaces)
            return text.isEmpty ? nil : ("•", text)
        }
        guard let dot = trimmed.firstIndex(of: "."),
              trimmed[..<dot].allSatisfy(\.isNumber),
              dot > trimmed.startIndex
        else {
            return nil
        }
        let after = trimmed.index(after: dot)
        guard after < trimmed.endIndex, trimmed[after] == " " else {
            return nil
        }
        let text = trimmed[after...].trimmingCharacters(in: .whitespaces)
        return text.isEmpty
            ? nil
            : ("\(trimmed[..<dot]).", text)
    }

    private static func isDivider(_ line: String) -> Bool {
        let compact = line.replacingOccurrences(of: " ", with: "")
        return compact.count >= 3
            && (compact.allSatisfy { $0 == "-" }
                || compact.allSatisfy { $0 == "*" }
                || compact.allSatisfy { $0 == "_" })
    }

    private static func isTableStart(_ lines: [String], at index: Int) -> Bool {
        guard index + 1 < lines.count,
              lines[index].contains("|"),
              lines[index + 1].contains("|")
        else {
            return false
        }
        let separator = lines[index + 1]
            .replacingOccurrences(of: "|", with: "")
            .replacingOccurrences(of: " ", with: "")
        return !separator.isEmpty
            && separator.allSatisfy { $0 == "-" || $0 == ":" }
    }

    private static func isTableSeparator(_ line: String) -> Bool {
        let cells = tableCells(line)
        return !cells.isEmpty
            && cells.allSatisfy { cell in
                let compact = cell.replacingOccurrences(of: " ", with: "")
                return !compact.isEmpty
                    && compact.allSatisfy { $0 == "-" || $0 == ":" }
            }
    }

    private static func tableCells(_ line: String) -> [String] {
        var value = line.trimmingCharacters(in: .whitespaces)
        if value.hasPrefix("|") { value.removeFirst() }
        if value.hasSuffix("|") { value.removeLast() }
        return value
            .split(separator: "|", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespaces) }
    }
}
