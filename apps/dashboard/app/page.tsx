"use client";

import { useState, useEffect, useCallback } from "react";
import StoryCard from "@/components/StoryCard";
import TopicCard, { FeedItem } from "@/components/TopicCard";
import EmailModal from "@/components/EmailModal";

export default function FeedPage() {
  const [activeEmailModalStoryId, setActiveEmailModalStoryId] = useState<string | null>(null);

  // ── Feed state ──
  const [feedItems, setFeedItems] = useState<FeedItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Fetch feed ──
  const fetchFeed = useCallback(
    async (nextCursor?: string | null) => {
      setLoading(true);
      try {
        const url = nextCursor
          ? `/api/stories?cursor=${encodeURIComponent(nextCursor)}`
          : "/api/stories";

        const res = await fetch(url);
        if (!res.ok) throw new Error("Failed to load feed");

        const data = await res.json();
        setFeedItems((prev) =>
          nextCursor ? [...prev, ...data.feed] : data.feed,
        );
        setCursor(data.nextCursor);
        setHasMore(!!data.nextCursor);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // ── Load feed on mount ──
  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  return (
    <div className="feed-container">
      {/* Header */}
      <header className="feed-header">
        <div className="header-inner">
          <h1 className="logo">
            <span className="logo-icon">◆</span> Presence
          </h1>
          <p className="tagline">Your processed email intelligence feed</p>
        </div>
      </header>

      {/* Two-column layout: sidebar + feed */}
      <div className="page-layout">
        {/* Feed grid */}
        <main className="feed-main topic-feed">
          {error && (
            <div className="feed-error">
              <p>⚠ {error}</p>
            </div>
          )}

          {feedItems.length > 0 ? (
            <div className="topic-post-list">
              {feedItems.map((item) => {
                if (item.topic_story_count === 1 && item.stories.length > 0) {
                  return (
                    <StoryCard
                      key={item.topic_id}
                      story={item.stories[0]}
                      onStoryClick={setActiveEmailModalStoryId}
                    />
                  );
                }
                return (
                  <TopicCard
                    key={item.topic_id}
                    item={item}
                    onStoryClick={setActiveEmailModalStoryId}
                  />
                );
              })}
            </div>
          ) : !loading ? (
            <div className="feed-empty">
              <div className="empty-icon">📰</div>
              <h2>No stories yet</h2>
              <p>
                Once stories are extracted, they&apos;ll appear here as topics.
              </p>
            </div>
          ) : null}

          {/* Load more */}
          {hasMore && feedItems.length > 0 && (
            <div className="load-more-wrapper">
              <button
                className="load-more-btn"
                onClick={() => fetchFeed(cursor)}
                disabled={loading}
              >
                {loading ? (
                  <span className="spinner" />
                ) : (
                  "Load More"
                )}
              </button>
            </div>
          )}

          {loading && feedItems.length === 0 && (
            <div className="feed-loading">
              <span className="spinner large" />
              <p>Loading feed…</p>
            </div>
          )}
        </main>
      </div>

      {/* Shared Email Modal */}
      {activeEmailModalStoryId && (
        <EmailModal
          storyId={activeEmailModalStoryId}
          onClose={() => setActiveEmailModalStoryId(null)}
        />
      )}
    </div>
  );
}
