"use client";

import { useState } from "react";

const SUGGESTED_TYPES = [
    "discount_offer",
    "coupon",
    "job_posting",
    "event",
    "deadline",
    "subscription_offer",
    "informational",
];

interface Props {
    onClose: () => void;
    onCreated: () => void;
}

export default function AddActionModal({ onClose, onCreated }: Props) {
    const [description, setDescription] = useState("");
    const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const toggleType = (t: string) => {
        setSelectedTypes((prev) =>
            prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t],
        );
    };

    const handleSubmit = async () => {
        if (!description.trim()) {
            setError("Please enter a description");
            return;
        }

        setSaving(true);
        setError(null);

        try {
            const res = await fetch("/api/desired-actions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    description: description.trim(),
                    action_types:
                        selectedTypes.length > 0 ? selectedTypes : null,
                }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || "Failed to create");
            }

            onCreated();
            onClose();
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Something went wrong",
            );
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h3>Add Desired Action</h3>
                    <button className="modal-close" onClick={onClose}>
                        ✕
                    </button>
                </div>

                <div className="modal-body">
                    <label className="modal-label">
                        What are you looking for?
                    </label>
                    <textarea
                        className="modal-input"
                        placeholder="e.g. Looking for Tommy Hilfiger jacket on discount..."
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        rows={3}
                        autoFocus
                    />

                    <label className="modal-label">
                        Filter by action type{" "}
                        <span className="optional">(optional)</span>
                    </label>
                    <div className="type-selector">
                        {SUGGESTED_TYPES.map((t) => (
                            <button
                                key={t}
                                className={`type-chip ${selectedTypes.includes(t) ? "selected" : ""}`}
                                onClick={() => toggleType(t)}
                                type="button"
                            >
                                {t.replace("_", " ")}
                            </button>
                        ))}
                    </div>

                    {error && <p className="modal-error">{error}</p>}
                </div>

                <div className="modal-footer">
                    <button
                        className="modal-btn cancel"
                        onClick={onClose}
                        disabled={saving}
                    >
                        Cancel
                    </button>
                    <button
                        className="modal-btn save"
                        onClick={handleSubmit}
                        disabled={saving}
                    >
                        {saving ? <span className="spinner" /> : "Save"}
                    </button>
                </div>
            </div>
        </div>
    );
}
