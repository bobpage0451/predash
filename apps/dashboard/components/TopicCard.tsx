"use client";

import { useState } from "react";
import { StoryPost } from "./StoryCard";

export interface FeedItem {
    topic_id: string;
    topic_label: string | null;
    topic_story_count: number;
    topic_updated_at: string;
    stories: StoryPost[];
}

function timeAgo(dateStr: string): string {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    if (diffHours < 24) {
        if (diffHours === 0) return "Just now";
        return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
    }
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

// Generate a deterministic color based on the topic string
function getTopicColor(topicStr: string) {
    let hash = 0;
    for (let i = 0; i < topicStr.length; i++) {
        hash = topicStr.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue}, 70%, 65%)`;
}

export default function TopicCard({ item, onStoryClick }: { item: FeedItem; onStoryClick?: (storyId: string) => void }) {
    const [expanded, setExpanded] = useState(true);

    // Derive top tags from stories (top 3 tags max)
    const tagCounts = new Map<string, number>();
    item.stories.forEach(s => {
        (s.tags || []).forEach(t => {
            tagCounts.set(t, (tagCounts.get(t) || 0) + 1);
        });
    });
    const topTags = Array.from(tagCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(e => e[0]);

    const labelStr = item.topic_label || `Topic ${item.topic_id.slice(0, 6)}`;
    const accentColor = getTopicColor(labelStr);

    return (
        <article className="topic-card" style={{ "--topic-accent": accentColor } as any}>
            <div className="topic-accent-border" style={{ backgroundColor: "var(--topic-accent)" }}></div>

            <div className="topic-header" onClick={() => setExpanded(!expanded)}>
                <div className="topic-header-left">
                    <span className={`topic-toggle-icon ${expanded ? "expanded" : ""}`}>▶</span>
                    <h2 className="topic-title">
                        Topic: {labelStr}
                    </h2>
                </div>
                <div className="topic-header-right">
                    <span className="topic-story-count">{item.topic_story_count} stories</span>
                    <span className="separator"></span>
                    <span className="topic-updated">Updated {timeAgo(item.topic_updated_at)}</span>
                </div>
            </div>

            {expanded && (
                <div className="topic-body">
                    {topTags.length > 0 && (
                        <div className="topic-tags-row">
                            {topTags.map((tag, i) => (
                                <span key={i} className="tag" style={{ backgroundColor: "var(--topic-accent)", color: "#fff", border: "none" }}>{tag}</span>
                            ))}
                        </div>
                    )}

                    <div className="topic-stories-list">
                        {item.stories.map((story) => (
                            <div key={story.id} className="topic-story-item">
                                <div className="topic-story-header">
                                    <h3 className="topic-story-headline">{story.headline}</h3>
                                    <div className="topic-story-meta">
                                        <button
                                            className="topic-story-time modal-trigger"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onStoryClick?.(story.id);
                                            }}
                                        >
                                            {timeAgo(story.processed_at)}
                                        </button>
                                        <span className="topic-story-sender" title={story.from_addr || ""}>
                                            {story.from_addr ? story.from_addr.split('<')[0].trim() : "Unknown"}
                                        </span>
                                    </div>
                                </div>
                                <p className="topic-story-summary">{story.summary}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </article>
    );
}
