import { drizzle, type PostgresJsDatabase } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

type DB = PostgresJsDatabase<typeof schema>;

function createDb(): DB {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      "DATABASE_URL is not set. Provision a Postgres database (Railway, Neon, etc.) " +
        "and add DATABASE_URL to .env.local"
    );
  }
  const client = postgres(url);
  return drizzle(client, { schema });
}

let _db: DB | null = null;

export function getDb(): DB {
  if (!_db) _db = createDb();
  return _db;
}

// Lazy proxy so imports don't crash at build time when DATABASE_URL is unset.
export const db: DB = new Proxy({} as DB, {
  get(_, prop: string | symbol) {
    return (getDb() as unknown as Record<string | symbol, unknown>)[prop];
  },
});
