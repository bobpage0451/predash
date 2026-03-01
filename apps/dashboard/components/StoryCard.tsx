"use client";

import Link from "next/link";

export interface StoryPost {
    id: string;
    headline: string;
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

export default function StoryCard({ story, onStoryClick }: { story: StoryPost; onStoryClick?: (storyId: string) => void }) {
    const displayDate = story.processed_at || story.date_sent;

    return (
        <article className="email-card story-card">
            {/* Header: sender info */}
            <div className="card-header">
                <div className="avatar">
                    {(story.from_addr?.[0] || "?").toUpperCase()}
                </div>
                <div className="header-text">
                    <span className="sender">{story.from_addr || "Unknown sender"}</span>
                    {story.subject && (
                        <span className="subject">{story.subject}</span>
                    )}
                </div>
            </div>

            {/* Headline */}
            <h3 className="story-headline">{story.headline}</h3>

            {/* Body: summary */}
            <div className="card-body">
                <p className="summary">{story.summary}</p>
            </div>

            {/* Tags */}
            {story.tags && story.tags.length > 0 && (
                <div className="card-tags">
                    {story.tags.map((tag, i) => (
                        <span key={i} className="tag">
                            {tag}
                        </span>
                    ))}
                </div>
            )}

            {/* Footer: date */}
            <div className="card-footer">
                <button
                    className="date-link modal-trigger"
                    onClick={() => onStoryClick?.(story.id)}
                >
                    {displayDate ? formatDate(displayDate) : "No date"}
                </button>
            </div>
        </article>
    );
}
