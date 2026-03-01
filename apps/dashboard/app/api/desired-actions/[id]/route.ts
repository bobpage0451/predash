import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function DELETE(
    _request: NextRequest,
    { params }: { params: Promise<{ id: string }> },
) {
    const { id } = await params;

    try {
        const sql = `DELETE FROM desired_actions WHERE id = $1 RETURNING id`;
        const rows = await query(sql, [id]);

        if (rows.length === 0) {
            return NextResponse.json(
                { error: "Desired action not found" },
                { status: 404 },
            );
        }

        return NextResponse.json({ deleted: rows[0].id });
    } catch (err) {
        console.error("Failed to delete desired action:", err);
        return NextResponse.json(
            { error: "Failed to delete desired action" },
            { status: 500 },
        );
    }
}

export async function PATCH(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> },
) {
    const { id } = await params;

    try {
        const body = await request.json();
        const { active } = body;

        if (typeof active !== "boolean") {
            return NextResponse.json(
                { error: "active (boolean) is required" },
                { status: 400 },
            );
        }

        const sql = `
      UPDATE desired_actions
      SET active = $1, updated_at = now()
      WHERE id = $2
      RETURNING id, description, action_types, active, created_at, updated_at
    `;
        const rows = await query(sql, [active, id]);

        if (rows.length === 0) {
            return NextResponse.json(
                { error: "Desired action not found" },
                { status: 404 },
            );
        }

        return NextResponse.json({ action: rows[0] });
    } catch (err) {
        console.error("Failed to update desired action:", err);
        return NextResponse.json(
            { error: "Failed to update desired action" },
            { status: 500 },
        );
    }
}
