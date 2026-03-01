import { Pool, QueryResultRow } from "pg";

const pool = new Pool({
    connectionString:
        process.env.DATABASE_URL ||
        "postgresql://presence:presence@postgres:5432/presence",
});

export async function query<T extends QueryResultRow = QueryResultRow>(
    text: string,
    params?: unknown[],
) {
    const result = await pool.query<T>(text, params);
    return result.rows;
}

export default pool;
