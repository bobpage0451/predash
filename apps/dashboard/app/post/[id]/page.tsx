import Link from "next/link";
import { query } from "@/lib/db";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

interface PostRow {
    id: string;
    headline: string;
    summary: string;
    tags: string[] | null;
    processed_at: string;
    processor: string;
    model: string;
    from_addr: string | null;
    subject: string | null;
    date_sent: string | null;
}

function formatDate(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

export async function generateMetadata({
    params,
}: {
    params: Promise<{ id: string }>;
}): Promise<Metadata> {
    const { id } = await params;
    const sql = `
    SELECT es.headline, es.summary, er.subject
    FROM email_stories es
    JOIN emails_raw er ON er.id = es.email_id
    WHERE es.id = $1 LIMIT 1
  `;
    const rows = await query(sql, [id]);
    if (rows.length === 0) return { title: "Post Not Found" };
    return {
        title: (rows[0].headline as string) || (rows[0].subject as string) || "Story",
        description: (rows[0].summary as string)?.slice(0, 160),
    };
}

export default async function PostPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;

    const sql = `
    SELECT
      es.id,
      es.headline,
      es.summary,
      es.tags,
      es.processed_at,
      es.processor,
      es.model,
      er.from_addr,
      er.subject,
      er.date_sent
    FROM email_stories es
    JOIN emails_raw er ON er.id = es.email_id
    WHERE es.id = $1
    LIMIT 1
  `;

    const rows = await query<PostRow>(sql, [id]);
    if (rows.length === 0) notFound();
    const post = rows[0];

    const displayDate = post.processed_at || post.date_sent;

    return (
        <div className="post-detail-container">
            <header className="post-detail-header">
                <Link href="/" className="back-link">
                    ← Back to Feed
                </Link>
            </header>

            <article className="post-detail-card">
                {/* Author row */}
                <div className="card-header">
                    <div className="avatar large">
                        {(post.from_addr?.[0] || "?").toUpperCase()}
                    </div>
                    <div className="header-text">
                        <span className="sender">{post.from_addr || "Unknown sender"}</span>
                        {post.subject && (
                            <span className="subject">{post.subject}</span>
                        )}
                    </div>
                </div>

                {/* Headline */}
                <div className="detail-headline">
                    <h1>{post.headline}</h1>
                </div>

                {/* Summary */}
                <div className="detail-body">
                    <p className="summary">{post.summary}</p>
                </div>

                {/* Tags */}
                {post.tags && post.tags.length > 0 && (
                    <div className="card-tags">
                        {post.tags.map((tag: string, i: number) => (
                            <span key={i} className="tag">
                                {tag}
                            </span>
                        ))}
                    </div>
                )}

                {/* Meta info */}
                <div className="detail-meta">
                    {displayDate && (
                        <div className="meta-row">
                            <span className="meta-label">Date</span>
                            <span className="meta-value">{formatDate(displayDate)}</span>
                        </div>
                    )}
                    <div className="meta-row">
                        <span className="meta-label">Processor</span>
                        <span className="meta-value">{post.processor}</span>
                    </div>
                    <div className="meta-row">
                        <span className="meta-label">Model</span>
                        <span className="meta-value">{post.model}</span>
                    </div>
                </div>
            </article>
        </div>
    );
}
