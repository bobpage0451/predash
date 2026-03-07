import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET() {
    const sql = `
    SELECT
      s.email,
      s.total_emails,
      s.skipped_emails,
      s.tag_counts,
      s.first_seen_at,
      s.last_seen_at
    FROM senders s
    ORDER BY s.last_seen_at DESC
  `;

    try {
        const rows = await query(sql);

        // Derive top 3 tags from tag_counts JSONB
        const publishers = rows.map((row) => {
            const tagCounts: Record<string, number> = row.tag_counts || {};
            const topTags = Object.entries(tagCounts)
                .sort((a, b) => (b[1] as number) - (a[1] as number))
                .slice(0, 3)
                .map(([tag]) => tag);

            return {
                email: row.email as string,
                total_emails: row.total_emails as number,
                skipped_emails: row.skipped_emails as number,
                top_tags: topTags,
                first_seen_at: row.first_seen_at,
                last_seen_at: row.last_seen_at,
            };
        });

        return NextResponse.json({ publishers });
    } catch (err) {
        console.error("Failed to fetch publishers:", err);
        return NextResponse.json(
            { error: "Failed to fetch publishers" },
            { status: 500 },
        );
    }
}
