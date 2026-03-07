"""SQLAlchemy 2.x declarative models for the Presence schema."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    """Shared declarative base for all models."""


# ---------------------------------------------------------------------------
# emails_raw
# ---------------------------------------------------------------------------


class EmailRaw(Base):
    __tablename__ = "emails_raw"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    mailbox: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    imap_uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    from_addr: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_sent: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    date_received: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    stories: Mapped[list["EmailStory"]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )
    filter_metrics: Mapped["EmailFilterMetrics | None"] = relationship(
        back_populates="email", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        # Partial unique: message_id unique per source (when present)
        Index(
            "uq_emails_raw_source_message_id",
            "source",
            "message_id",
            unique=True,
            postgresql_where=text("message_id IS NOT NULL"),
        ),
        # Partial unique: imap_uid unique per (source, mailbox) (when present)
        Index(
            "uq_emails_raw_source_mailbox_imap_uid",
            "source",
            "mailbox",
            "imap_uid",
            unique=True,
            postgresql_where=text("imap_uid IS NOT NULL"),
        ),
        # Partial unique: sha256 dedupe fallback
        Index(
            "uq_emails_raw_source_sha256",
            "source",
            "sha256",
            unique=True,
            postgresql_where=text("sha256 IS NOT NULL"),
        ),
        # Standard indexes
        Index("ix_emails_raw_date_received", "date_received"),
        Index("ix_emails_raw_ingested_at", "ingested_at"),
    )


# ---------------------------------------------------------------------------
# email_stories
# ---------------------------------------------------------------------------


class EmailStory(Base):
    __tablename__ = "email_stories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("emails_raw.id", ondelete="CASCADE"),
        nullable=False,
    )
    story_index: Mapped[int] = mapped_column(Integer, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)  # "bullish" / "bearish" / "neutral"
    named_entities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # list of entity strings
    emojis: Mapped[str | None] = mapped_column(Text, nullable=True)  # 1-2 contextual emojis
    processor: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ok'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding = mapped_column(Vector(768), nullable=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id"),
        nullable=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    email: Mapped["EmailRaw"] = relationship(back_populates="stories")
    topic: Mapped["Topic | None"] = relationship(back_populates="stories")

    __table_args__ = (
        # Unique constraint: prevent duplicate stories per run
        Index(
            "uq_email_stories_run",
            "email_id",
            "processor",
            "model",
            "prompt_version",
            "story_index",
            unique=True,
        ),
        # Standard indexes
        Index("ix_email_stories_processed_at", "processed_at"),
        Index("ix_email_stories_email_id", "email_id"),
        Index("ix_email_stories_topic_id", "topic_id"),
        Index("ix_email_stories_topic_processed", "topic_id", "processed_at"),
    )


# ---------------------------------------------------------------------------
# email_filter_metrics
# ---------------------------------------------------------------------------


class EmailFilterMetrics(Base):
    """Heuristic pre-filter signals and outcomes for a single email."""

    __tablename__ = "email_filter_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("emails_raw.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Final scores
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    quality: Mapped[str | None] = mapped_column(Text, nullable=True)  # "good" / "poor" / "skip" / None
    filter_outcome: Mapped[str] = mapped_column(Text, nullable=False)  # "pass" / "low_confidence" / "poor_quality"

    # Raw signals — stored individually for threshold tuning and debugging
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    link_density: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_html_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_sentence_len: Mapped[float | None] = mapped_column(Float, nullable=True)
    cta_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_list_unsubscribe: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_bulk_precedence: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    esp_detected: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. "mailchimp", "substack"

    # Relationship
    email: Mapped["EmailRaw"] = relationship(back_populates="filter_metrics")

    __table_args__ = (
        # One evaluation per email
        Index("uq_email_filter_metrics_email_id", "email_id", unique=True),
        Index("ix_email_filter_metrics_filter_outcome", "filter_outcome"),
        Index("ix_email_filter_metrics_evaluated_at", "evaluated_at"),
    )


# ---------------------------------------------------------------------------
# topics
# ---------------------------------------------------------------------------


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    centroid_embedding = mapped_column(Vector(768), nullable=False)
    story_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    last_story_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    stories: Mapped[list["EmailStory"]] = relationship(back_populates="topic")

    __table_args__ = (
        Index("ix_topics_last_story_at", "last_story_at"),
        Index("ix_topics_story_count", "story_count"),
    )


# ---------------------------------------------------------------------------
# senders
# ---------------------------------------------------------------------------


class Sender(Base):
    """Aggregated stats per unique sender/publisher email address."""

    __tablename__ = "senders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)  # raw from_addr value
    total_emails: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    skipped_emails: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    tag_counts: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # {tag: count} accumulated across all emails
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        Index("uq_senders_email", "email", unique=True),
        Index("ix_senders_last_seen_at", "last_seen_at"),
    )

