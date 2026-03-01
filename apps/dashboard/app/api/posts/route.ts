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
        cursorClause = "AND es.processed_at < $2";
        params.push(cursor);
    }

    const sql = `
    SELECT
      es.id,
      es.headline,
      es.summary,
      es.tags,
      es.processed_at,
      er.from_addr,
      er.subject,
      er.date_sent
    FROM email_stories es
    JOIN emails_raw er ON er.id = es.email_id
    WHERE es.status = 'ok'
    ${cursorClause}
    ORDER BY es.processed_at DESC
    LIMIT $1
  `;

    try {
        const rows = await query(sql, params);

        const nextCursor =
            rows.length === limit
                ? rows[rows.length - 1].processed_at?.toISOString() ?? null
                : null;

        return NextResponse.json({ posts: rows, nextCursor });
    } catch (err) {
        console.error("Failed to fetch posts:", err);
        return NextResponse.json(
            { error: "Failed to fetch posts" },
            { status: 500 },
        );
    }
}
