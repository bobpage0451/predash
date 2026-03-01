"use client";

import Link from "next/link";

export interface EmailPost {
    id: string;
    summary: string;
    tags: string[] | null;
    processed_at: string;
    from_addr: string | null;
    subject: string | null;
    date_sent: string | null;
}

function formatDate(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

export default function EmailCard({ post }: { post: EmailPost }) {
    const displayDate = post.processed_at || post.date_sent;

    return (
        <article className="email-card">
            {/* Header: sender info */}
            <div className="card-header">
                <div className="avatar">
                    {(post.from_addr?.[0] || "?").toUpperCase()}
                </div>
                <div className="header-text">
                    <span className="sender">{post.from_addr || "Unknown sender"}</span>
                    {post.subject && (
                        <span className="subject">{post.subject}</span>
                    )}
                </div>
            </div>

            {/* Body: summary */}
            <div className="card-body">
                <p className="summary">{post.summary}</p>
            </div>

            {/* Tags */}
            {post.tags && post.tags.length > 0 && (
                <div className="card-tags">
                    {post.tags.map((tag, i) => (
                        <span key={i} className="tag">
                            {tag}
                        </span>
                    ))}
                </div>
            )}

            {/* Footer: clickable date */}
            <div className="card-footer">
                <Link href={`/post/${post.id}`} className="date-link">
                    {displayDate ? formatDate(displayDate) : "No date"}
                </Link>
            </div>
        </article>
    );
}
