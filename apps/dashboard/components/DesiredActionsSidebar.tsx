"use client";

import { useState, useEffect, useCallback } from "react";

export interface ActionMatch {
    id: string;
    desired_action_id: string;
    story_id: string;
    similarity_score: number;
    action_type_matched: boolean;
    matched_at: string;
    action_description: string;
    story_headline: string;
    story_summary: string;
    story_action_type: string | null;
    story_tags: string[] | null;
    from_addr: string | null;
    subject: string | null;
}

export interface DesiredAction {
    id: string;
    description: string;
    action_types: string[] | null;
    active: boolean;
    created_at: string;
    match_count: number;
}

interface Props {
    onOpenAdd: () => void;
}

export default function DesiredActionsSidebar({ onOpenAdd }: Props) {
    const [actions, setActions] = useState<DesiredAction[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [matches, setMatches] = useState<ActionMatch[]>([]);
    const [matchesLoading, setMatchesLoading] = useState(false);

    const fetchActions = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch("/api/desired-actions");
            if (!res.ok) throw new Error("Failed to load actions");
            const data = await res.json();
            setActions(data.actions);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchActions();
    }, [fetchActions]);

    const handleDelete = async (id: string) => {
        try {
            const res = await fetch(`/api/desired-actions/${id}`, {
                method: "DELETE",
            });
            if (res.ok) {
                setActions((prev) => prev.filter((a) => a.id !== id));
                if (expandedId === id) {
                    setExpandedId(null);
                    setMatches([]);
                }
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleToggle = async (id: string, currentActive: boolean) => {
        try {
            const res = await fetch(`/api/desired-actions/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ active: !currentActive }),
            });
            if (res.ok) {
                setActions((prev) =>
                    prev.map((a) =>
                        a.id === id ? { ...a, active: !currentActive } : a,
                    ),
                );
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleExpand = async (id: string) => {
        if (expandedId === id) {
            setExpandedId(null);
            setMatches([]);
            return;
        }
        setExpandedId(id);
        setMatchesLoading(true);
        try {
            const res = await fetch(`/api/action-matches?action_id=${id}&limit=10`);
            if (res.ok) {
                const data = await res.json();
                setMatches(data.matches);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setMatchesLoading(false);
        }
    };

    return (
        <aside className="actions-sidebar">
            <div className="sidebar-header">
                <h2 className="sidebar-title">
                    <span className="sidebar-icon">🎯</span> Desired Actions
                </h2>
                <button className="add-action-btn" onClick={onOpenAdd}>
                    <span>+</span> Add New
                </button>
            </div>

            <div className="actions-stack">
                {loading && actions.length === 0 && (
                    <div className="sidebar-loading">
                        <span className="spinner" />
                    </div>
                )}

                {!loading && actions.length === 0 && (
                    <div className="sidebar-empty">
                        <p>No desired actions yet.</p>
                        <p className="sidebar-empty-hint">
                            Add actions to match against your emails.
                        </p>
                    </div>
                )}

                {actions.map((action) => (
                    <div
                        key={action.id}
                        className={`action-card ${!action.active ? "inactive" : ""} ${expandedId === action.id ? "expanded" : ""}`}
                    >
                        <div
                            className="action-card-main"
                            onClick={() => handleExpand(action.id)}
                        >
                            <p className="action-description">
                                {action.description}
                            </p>

                            <div className="action-meta">
                                {action.action_types &&
                                    action.action_types.length > 0 && (
                                        <div className="action-types">
                                            {action.action_types.map(
                                                (t, i) => (
                                                    <span
                                                        key={i}
                                                        className="action-type-tag"
                                                    >
                                                        {t.replace("_", " ")}
                                                    </span>
                                                ),
                                            )}
                                        </div>
                                    )}

                                <div className="action-footer">
                                    {action.match_count > 0 && (
                                        <span className="match-badge">
                                            {action.match_count} match
                                            {action.match_count !== 1
                                                ? "es"
                                                : ""}
                                        </span>
                                    )}

                                    <div className="action-controls">
                                        <button
                                            className={`toggle-btn ${action.active ? "active" : ""}`}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleToggle(
                                                    action.id,
                                                    action.active,
                                                );
                                            }}
                                            title={
                                                action.active
                                                    ? "Pause"
                                                    : "Resume"
                                            }
                                        >
                                            {action.active ? "⏸" : "▶"}
                                        </button>
                                        <button
                                            className="delete-btn"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDelete(action.id);
                                            }}
                                            title="Delete"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Expanded matches */}
                        {expandedId === action.id && (
                            <div className="action-matches-panel">
                                {matchesLoading ? (
                                    <div className="matches-loading">
                                        <span className="spinner" />
                                    </div>
                                ) : matches.length === 0 ? (
                                    <p className="no-matches">
                                        No matches yet
                                    </p>
                                ) : (
                                    <div className="matches-list">
                                        {matches.map((m) => (
                                            <div
                                                key={m.id}
                                                className="match-item"
                                            >
                                                <div className="match-headline">
                                                    {m.story_headline}
                                                </div>
                                                <div className="match-detail">
                                                    <span className="match-score">
                                                        {(
                                                            m.similarity_score *
                                                            100
                                                        ).toFixed(0)}
                                                        % match
                                                    </span>
                                                    {m.action_type_matched && (
                                                        <span className="type-match-badge">
                                                            ✓ type
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </aside>
    );
}
