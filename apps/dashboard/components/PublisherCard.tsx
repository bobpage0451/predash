"use client";

export interface Publisher {
    email: string;      // raw from_addr, e.g. "Name <addr@host.com>"
    total_emails: number;
    skipped_emails: number;
    top_tags: string[];
    first_seen_at: string;
    last_seen_at: string;
}

/** Parse "Display Name <addr@host.com>" → { displayName, address } */
function parseFromAddr(fromAddr: string): { displayName: string; address: string } {
    const match = fromAddr.match(/^(.*?)\s*<([^>]+)>$/);
    if (match) {
        return {
            displayName: match[1].trim().replace(/^"|"$/g, "") || match[2],
            address: match[2].trim(),
        };
    }
    return { displayName: fromAddr, address: fromAddr };
}

function getAvatarColor(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue}, 65%, 55%)`;
}

function timeAgo(dateStr: string): string {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "today";
    if (diffDays === 1) return "yesterday";
    if (diffDays < 30) return `${diffDays}d ago`;
    const diffMonths = Math.floor(diffDays / 30);
    return `${diffMonths}mo ago`;
}

export default function PublisherCard({ publisher }: { publisher: Publisher }) {
    const { displayName, address } = parseFromAddr(publisher.email);
    const initials = displayName.slice(0, 2).toUpperCase();
    const avatarColor = getAvatarColor(publisher.email);
    const passedEmails = publisher.total_emails - publisher.skipped_emails;
    const passRate =
        publisher.total_emails > 0
            ? Math.round((passedEmails / publisher.total_emails) * 100)
            : 0;

    return (
        <article className="publisher-card">
            <div className="publisher-card-header">
                <div
                    className="publisher-avatar"
                    style={{ background: avatarColor }}
                >
                    {initials}
                </div>
                <div className="publisher-identity">
                    <h3 className="publisher-name">{displayName}</h3>
                    <p className="publisher-email">{address}</p>
                </div>
            </div>

            <div className="publisher-stats">
                <div className="publisher-stat">
                    <span className="stat-value">{publisher.total_emails}</span>
                    <span className="stat-label">Total</span>
                </div>
                <div className="publisher-stat-divider" />
                <div className="publisher-stat">
                    <span className="stat-value skipped">
                        {publisher.skipped_emails}
                    </span>
                    <span className="stat-label">Skipped</span>
                </div>
                <div className="publisher-stat-divider" />
                <div className="publisher-stat">
                    <span
                        className={`stat-value ${passRate >= 70 ? "good" : passRate >= 40 ? "mid" : "poor"}`}
                    >
                        {passRate}%
                    </span>
                    <span className="stat-label">Pass rate</span>
                </div>
            </div>

            {publisher.top_tags.length > 0 && (
                <div className="publisher-tags">
                    {publisher.top_tags.map((tag, i) => (
                        <span key={i} className="tag">
                            {tag}
                        </span>
                    ))}
                </div>
            )}

            <div className="publisher-footer">
                <span className="publisher-last-seen">
                    Last seen {timeAgo(publisher.last_seen_at)}
                </span>
            </div>
        </article>
    );
}
