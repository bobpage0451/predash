"use client";

import { useState, useEffect } from "react";

interface EmailData {
    subject: string | null;
    from_addr: string | null;
    date_sent: string | null;
    body_html: string | null;
    body_text: string | null;
}

interface Props {
    storyId: string;
    onClose: () => void;
}

export default function EmailModal({ storyId, onClose }: Props) {
    const [emailData, setEmailData] = useState<EmailData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchEmail() {
            try {
                const res = await fetch(`/api/stories/${storyId}/email`);
                if (!res.ok) {
                    throw new Error("Failed to load email");
                }
                const data = await res.json();
                setEmailData(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Something went wrong");
            } finally {
                setLoading(false);
            }
        }
        fetchEmail();
    }, [storyId]);

    const displayDate = emailData?.date_sent ? new Date(emailData.date_sent).toLocaleString() : "";

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content email-modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <div className="email-modal-header-info">
                        <h3>{emailData?.subject || "No Subject"}</h3>
                        <div className="email-modal-meta">
                            <span className="sender">{emailData?.from_addr || "Unknown Sender"}</span>
                            {displayDate && <span className="date">{displayDate}</span>}
                        </div>
                    </div>
                    <button className="modal-close" onClick={onClose}>
                        ✕
                    </button>
                </div>

                <div className="modal-body email-modal-body">
                    {loading ? (
                        <div className="email-loading">
                            <span className="spinner"></span>
                            <p>Loading email...</p>
                        </div>
                    ) : error ? (
                        <p className="modal-error">{error}</p>
                    ) : emailData?.body_html ? (
                        <iframe
                            className="email-iframe"
                            srcDoc={emailData.body_html}
                            title="Email contents"
                            sandbox=""
                        />
                    ) : emailData?.body_text ? (
                        <pre className="email-text">
                            {emailData.body_text}
                        </pre>
                    ) : (
                        <p className="email-empty">No email content available.</p>
                    )}
                </div>
            </div>
        </div>
    );
}
