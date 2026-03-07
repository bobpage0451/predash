"use client";

import { useState, useEffect, useMemo } from "react";
import PublisherCard, { Publisher } from "@/components/PublisherCard";

type SortKey = "emails" | "passrate";
type SortDir = "asc" | "desc";

function getPassRate(p: Publisher): number {
    if (p.total_emails === 0) return 0;
    return (p.total_emails - p.skipped_emails) / p.total_emails;
}

function getValue(p: Publisher, key: SortKey): number {
    return key === "emails" ? p.total_emails : getPassRate(p);
}

export default function PublishersPage() {
    const [publishers, setPublishers] = useState<Publisher[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Each sort key is independently toggled on/off + has its own direction
    const [activeKeys, setActiveKeys] = useState<Set<SortKey>>(new Set());
    const [sortDirs, setSortDirs] = useState<Record<SortKey, SortDir>>({
        emails: "desc",
        passrate: "desc",
    });

    useEffect(() => {
        async function fetchPublishers() {
            try {
                const res = await fetch("/api/publishers");
                if (!res.ok) throw new Error("Failed to load publishers");
                const data = await res.json();
                setPublishers(data.publishers);
            } catch (err) {
                setError(
                    err instanceof Error ? err.message : "Something went wrong",
                );
            } finally {
                setLoading(false);
            }
        }
        fetchPublishers();
    }, []);

    function handleSort(key: SortKey) {
        if (activeKeys.has(key)) {
            // Already active → toggle direction
            setSortDirs((prev) => ({
                ...prev,
                [key]: prev[key] === "desc" ? "asc" : "desc",
            }));
        } else {
            // Activate this key (reset direction to desc)
            setSortDirs((prev) => ({ ...prev, [key]: "desc" }));
            setActiveKeys((prev) => new Set(prev).add(key));
        }
    }

    // Sort order: passrate is primary, emails is secondary
    const SORT_ORDER: SortKey[] = ["passrate", "emails"];

    const sorted = useMemo(() => {
        const keys = SORT_ORDER.filter((k) => activeKeys.has(k));
        if (keys.length === 0) return publishers;
        return [...publishers].sort((a, b) => {
            for (const key of keys) {
                const va = getValue(a, key);
                const vb = getValue(b, key);
                if (va !== vb) {
                    return sortDirs[key] === "desc" ? vb - va : va - vb;
                }
            }
            return 0;
        });
    }, [publishers, activeKeys, sortDirs]);

    const dirArrow = (key: SortKey) =>
        sortDirs[key] === "desc" ? " ↓" : " ↑";

    return (
        <div className="feed-container">
            <header className="feed-header">
                <div className="header-inner">
                    <div className="header-top-row">
                        <a href="/" className="logo">
                            <span className="logo-icon">◆</span> Presence
                        </a>
                        <a href="/" className="nav-secondary-link">← Feed</a>
                    </div>
                    <p className="tagline">Monitor your email publishers</p>
                </div>
            </header>

            <div className="page-layout">
                <main className="feed-main">
                    {error && (
                        <div className="feed-error">
                            <p>⚠ {error}</p>
                        </div>
                    )}

                    {loading && (
                        <div className="feed-loading">
                            <span className="spinner large" />
                            <p>Loading publishers…</p>
                        </div>
                    )}

                    {!loading && publishers.length === 0 && (
                        <div className="feed-empty">
                            <div className="empty-icon">📬</div>
                            <h2>No publishers yet</h2>
                            <p>
                                Run the pipeline to start tracking sender stats.
                            </p>
                        </div>
                    )}

                    {publishers.length > 0 && (
                        <>
                            <div className="publishers-summary">
                                <span className="publishers-count">
                                    {publishers.length} publisher
                                    {publishers.length !== 1 ? "s" : ""}{" "}
                                    tracked
                                </span>
                                <div className="publishers-sort-tags">
                                    <button
                                        className={`sort-tag${activeKeys.has("emails") ? " active" : ""}`}
                                        onClick={() => handleSort("emails")}
                                    >
                                        # emails{activeKeys.has("emails") ? dirArrow("emails") : ""}
                                    </button>
                                    <button
                                        className={`sort-tag${activeKeys.has("passrate") ? " active" : ""}`}
                                        onClick={() => handleSort("passrate")}
                                    >
                                        pass rate{activeKeys.has("passrate") ? dirArrow("passrate") : ""}
                                    </button>
                                </div>
                            </div>
                            <div className="publishers-grid">
                                {sorted.map((p) => (
                                    <PublisherCard
                                        key={p.email}
                                        publisher={p}
                                    />
                                ))}
                            </div>
                        </>
                    )}
                </main>
            </div>
        </div>
    );
}

