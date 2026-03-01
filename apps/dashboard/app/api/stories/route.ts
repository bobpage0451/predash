import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

const DEFAULT_LIMIT = 20;

export async function GET(request: NextRequest) {
    const { searchParams } = request.nextUrl;
    const cursor = searchParams.get("cursor"); // ISO timestamp
    const limit = Math.min(
        Number(searchParams.get("limit")) || DEFAULT_LIMIT,
        100,
    );

    const params: unknown[] = [limit];
    let cursorClause = "";

    if (cursor) {
        cursorClause = "AND t.last_story_at < $2";
        params.push(cursor);
    }

    const sql = `
    SELECT
      t.id as topic_id,
      t.label as topic_label,
      t.story_count as topic_story_count,
      t.last_story_at as topic_updated_at,
      json_agg(
        json_build_object(
          'id', es.id,
          'headline', es.headline,
          'summary', es.summary,
          'tags', es.tags,
          'processed_at', es.processed_at,
          'from_addr', er.from_addr,
          'subject', er.subject,
          'date_sent', er.date_sent
        ) ORDER BY es.processed_at DESC
      ) as stories
    FROM topics t
    JOIN email_stories es ON es.topic_id = t.id
    JOIN emails_raw er ON er.id = es.email_id
    WHERE es.status = 'ok'
    ${cursorClause}
    GROUP BY t.id, t.label, t.story_count, t.last_story_at
    ORDER BY t.last_story_at DESC
    LIMIT $1
  `;

    try {
        const rows = await query(sql, params);

        const nextCursor =
            rows.length === limit
                ? rows[rows.length - 1].topic_updated_at?.toISOString() ?? null
                : null;

        return NextResponse.json({ feed: rows, nextCursor });
    } catch (err) {
        console.error("Failed to fetch stories:", err);
        return NextResponse.json(
            { error: "Failed to fetch stories" },
            { status: 500 },
        );
    }
}
