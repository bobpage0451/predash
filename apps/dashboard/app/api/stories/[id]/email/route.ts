import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET(
    _request: NextRequest,
    { params }: { params: Promise<{ id: string }> },
) {
    const { id } = await params;

    const sql = `
    SELECT
      er.subject,
      er.from_addr,
      er.date_sent,
      er.body_html,
      er.body_text
    FROM email_stories es
    JOIN emails_raw er ON er.id = es.email_id
    WHERE es.id = $1
    LIMIT 1
  `;

    try {
        const rows = await query(sql, [id]);
        if (rows.length === 0) {
            return NextResponse.json({ error: "Email not found" }, { status: 404 });
        }
        return NextResponse.json(rows[0]);
    } catch (err) {
        console.error("Failed to fetch email:", err);
        return NextResponse.json(
            { error: "Failed to fetch email" },
            { status: 500 },
        );
    }
}
