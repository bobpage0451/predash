"use client";

import Link from "next/link";

export interface StoryPost {
    id: string;
    headline: string;
    summary: string;
    tags: string[] | null;
    sentiment: "bullish" | "bearish" | "neutral" | null;
    named_entities: string[] | null;
    emojis: string | null;
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

const SENTIMENT_ICON: Record<string, string> = {
    bullish: "🟢",
    bearish: "🔴",
    neutral: "➖",
};

const SENTIMENT_CLASS: Record<string, string> = {
    bullish: "sentiment-bullish",
    bearish: "sentiment-bearish",
    neutral: "sentiment-neutral",
};

export default function StoryCard({ story, onStoryClick }: { story: StoryPost; onStoryClick?: (storyId: string) => void }) {
    const displayDate = story.processed_at || story.date_sent;
    const sentimentKey = story.sentiment ?? "neutral";
    const sentimentIcon = SENTIMENT_ICON[sentimentKey] ?? "➖";
    const sentimentClass = SENTIMENT_CLASS[sentimentKey] ?? "sentiment-neutral";

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
                {/* Sentiment badge */}
                <span className={`sentiment-badge ${sentimentClass}`} title={sentimentKey}>
                    {sentimentIcon}
                </span>
            </div>

            {/* Headline + emojis */}
            <h3 className="story-headline">
                {story.emojis && <span className="story-emojis">{story.emojis} </span>}
                {story.headline}
            </h3>

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

            {/* Named entities */}
            {story.named_entities && story.named_entities.length > 0 && (
                <div className="card-entities">
                    {story.named_entities.map((entity, i) => (
                        <span key={i} className="entity-tag">
                            {entity}
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
