import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

const DEFAULT_LIMIT = 50;

export async function GET(request: NextRequest) {
    const { searchParams } = request.nextUrl;
    const limit = Math.min(
        Number(searchParams.get("limit")) || DEFAULT_LIMIT,
        200,
    );
    const actionId = searchParams.get("action_id");

    const params: unknown[] = [limit];
    let actionFilter = "";

    if (actionId) {
        actionFilter = "AND am.desired_action_id = $2";
        params.push(actionId);
    }

    const sql = `
    SELECT
      am.id,
      am.desired_action_id,
      am.story_id,
      am.similarity_score,
      am.action_type_matched,
      am.matched_at,
      da.description AS action_description,
      es.headline    AS story_headline,
      es.summary     AS story_summary,
      es.action_type AS story_action_type,
      es.tags        AS story_tags,
      er.from_addr,
      er.subject
    FROM action_matches am
    JOIN desired_actions da ON da.id = am.desired_action_id
    JOIN email_stories es  ON es.id = am.story_id
    JOIN emails_raw er     ON er.id = es.email_id
    WHERE 1=1
    ${actionFilter}
    ORDER BY am.similarity_score DESC, am.matched_at DESC
    LIMIT $1
  `;

    try {
        const rows = await query(sql, params);
        return NextResponse.json({ matches: rows });
    } catch (err) {
        console.error("Failed to fetch action matches:", err);
        return NextResponse.json(
            { error: "Failed to fetch action matches" },
            { status: 500 },
        );
    }
}
