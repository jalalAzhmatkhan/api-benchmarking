// PostgreSQL access: raw SQL through node-postgres, no ORM and no query builder.
// The pool follows Documentation/specs/connection-pooling.md: fixed size, pre-warmed, 5 s acquire
// timeout, no idle/lifetime eviction. Driver defaults (unnamed extended-protocol statements) are
// kept (decision D-06).
import pg from 'pg';

import { NotFoundError } from '../domain/errors.ts';
import type { Item, ItemInput, ItemRepository } from '../domain/item.ts';

// Canonical statements (Documentation/specs/database-schema.md §2), shared verbatim by all stacks.
export const SELECT_SQL = 'SELECT id, name, description, price_cents, quantity, created_at, updated_at FROM items WHERE id = $1';
export const INSERT_SQL =
  'INSERT INTO items (name, description, price_cents, quantity) VALUES ($1, $2, $3, $4) ' +
  'RETURNING id, name, description, price_cents, quantity, created_at, updated_at';
export const UPDATE_SQL =
  'UPDATE items SET name = $2, description = $3, price_cents = $4, quantity = $5, updated_at = now() ' +
  'WHERE id = $1 RETURNING id, name, description, price_cents, quantity, created_at, updated_at';
export const DELETE_SQL = 'DELETE FROM items WHERE id = $1';

/** The part of a pool the repository needs. */
export interface Queryable {
  query(config: { text: string; values: unknown[] }): Promise<{ rows: Record<string, unknown>[]; rowCount: number | null }>;
}

export interface ManagedPool extends Queryable {
  end(): Promise<void>;
}

/** BIGINT columns (id, price_cents) arrive as strings by default; values stay below 2^53 by contract. */
pg.types.setTypeParser(pg.types.builtins.INT8, Number);

/** A fixed-size pool: min = max = size, 5 s acquire timeout, no idle or lifetime eviction. */
export function createPool(databaseUrl: string, size: number): ManagedPool {
  const pool = new pg.Pool({
    connectionString: databaseUrl,
    max: size,
    min: size,
    connectionTimeoutMillis: 5000,
    idleTimeoutMillis: 0,
    maxLifetimeSeconds: 0,
  });
  return {
    query: (config) => pool.query(config),
    end: () => pool.end(),
  };
}

/** Opens `size` connections by running `size` overlapping queries (forces `size` distinct clients). */
export async function warmPool(db: Queryable, size: number): Promise<void> {
  await Promise.all(Array.from({ length: size }, () => db.query({ text: 'SELECT pg_sleep(0.05)', values: [] })));
}

function toItem(row: Record<string, unknown>): Item {
  return {
    id: row['id'] as number,
    name: row['name'] as string,
    description: row['description'] as string | null,
    priceCents: row['price_cents'] as number,
    quantity: row['quantity'] as number,
    createdAt: row['created_at'] as Date,
    updatedAt: row['updated_at'] as Date,
  };
}

export function createItemRepository(db: Queryable): ItemRepository {
  async function one(text: string, values: unknown[]): Promise<Item> {
    const row = (await db.query({ text, values })).rows[0];
    if (!row) {
      throw new NotFoundError();
    }
    return toItem(row);
  }

  return {
    get: (id) => one(SELECT_SQL, [id]),
    create: (input: ItemInput) => one(INSERT_SQL, [input.name, input.description, input.priceCents, input.quantity]),
    replace: (id, input) => one(UPDATE_SQL, [id, input.name, input.description, input.priceCents, input.quantity]),
    async delete(id) {
      if (!(await db.query({ text: DELETE_SQL, values: [id] })).rowCount) {
        throw new NotFoundError();
      }
    },
  };
}
