import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

const DEFAULT_LIMIT = 20;

export async function GET(request: NextRequest) {
    const { searchParams } = request.nextUrl;
    const limit = Math.min(
        Number(searchParams.get("limit")) || DEFAULT_LIMIT,
        100,
    );

    const sql = `
    SELECT
      da.id,
      da.description,
      da.action_types,
      da.active,
      da.created_at,
      da.updated_at,
      COALESCE(mc.match_count, 0) AS match_count
    FROM desired_actions da
    LEFT JOIN (
      SELECT desired_action_id, COUNT(*) AS match_count
      FROM action_matches
      GROUP BY desired_action_id
    ) mc ON mc.desired_action_id = da.id
    ORDER BY da.created_at DESC
    LIMIT $1
  `;

    try {
        const rows = await query(sql, [limit]);
        return NextResponse.json({ actions: rows });
    } catch (err) {
        console.error("Failed to fetch desired actions:", err);
        return NextResponse.json(
            { error: "Failed to fetch desired actions" },
            { status: 500 },
        );
    }
}

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { description, action_types } = body;

        if (!description || typeof description !== "string" || description.trim().length === 0) {
            return NextResponse.json(
                { error: "description is required" },
                { status: 400 },
            );
        }

        const sql = `
      INSERT INTO desired_actions (description, action_types)
      VALUES ($1, $2)
      RETURNING id, description, action_types, active, created_at, updated_at
    `;

        const rows = await query(sql, [
            description.trim(),
            action_types ? JSON.stringify(action_types) : null,
        ]);

        const action = rows[0];

        // Embed the description inline via Ollama (non-blocking failure)
        try {
            const ollamaUrl = process.env.OLLAMA_BASE_URL || "http://ollama:11434";
            const embeddingModel = process.env.EMBEDDING_MODEL || "nomic-embed-text";

            const embedRes = await fetch(`${ollamaUrl}/api/embed`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    model: embeddingModel,
                    input: description.trim(),
                }),
            });

            if (embedRes.ok) {
                const embedData = await embedRes.json();
                const embeddings = embedData.embeddings;
                if (embeddings && embeddings.length > 0) {
                    const vector = `[${embeddings[0].join(",")}]`;
                    await query(
                        `UPDATE desired_actions SET embedding = $1 WHERE id = $2`,
                        [vector, action.id],
                    );
                }
            }
        } catch (embedErr) {
            // Embedding failure is non-fatal; pipeline will backfill
            console.warn("Inline embedding failed (will backfill):", embedErr);
        }

        return NextResponse.json({ action }, { status: 201 });
    } catch (err) {
        console.error("Failed to create desired action:", err);
        return NextResponse.json(
            { error: "Failed to create desired action" },
            { status: 500 },
        );
    }
}

