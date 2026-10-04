import Fastify from 'fastify';
import type { FastifyError, FastifyInstance } from 'fastify';

import type { UseCases } from '../application/use-cases.ts';
import { NotFoundError, ValidationError } from '../domain/errors.ts';
import { parseId, parseInput, toResponse } from './parse.ts';

function errorBody(code: string, message: string) {
  return { error: { code, message } };
}

/**
 * The four endpoints of the contract. No logger and no plugins (benchmark-rules.md). Every
 * content type is delivered as a raw Buffer so malformed input is always a contract 400
 * (Fastify's own parser would answer 415/400 with a different body).
 */
export function buildServer(useCases: UseCases): FastifyInstance {
  const app = Fastify({ logger: false });
  app.removeAllContentTypeParsers();
  app.addContentTypeParser('*', { parseAs: 'buffer' }, (_request, body, done) => done(null, body));

  app.setErrorHandler((error: FastifyError, _request, reply) => {
    if (error instanceof ValidationError) {
      return reply.code(400).send(errorBody('VALIDATION_ERROR', error.message));
    }
    if (error instanceof NotFoundError) {
      return reply.code(404).send(errorBody('NOT_FOUND', error.message));
    }
    // Framework-level client errors (e.g. 413 body too large) keep their status; nothing else leaks.
    if (error.statusCode !== undefined && error.statusCode >= 400 && error.statusCode < 500) {
      return reply.code(error.statusCode).send(errorBody('VALIDATION_ERROR', 'invalid request'));
    }
    return reply.code(500).send(errorBody('INTERNAL_ERROR', 'internal error'));
  });

  app.post('/items', async (request, reply) => {
    const item = await useCases.createItem(parseInput(request.body));
    return reply.code(201).header('location', `/items/${item.id}`).send(toResponse(item));
  });

  app.get<{ Params: { id: string } }>('/items/:id', async (request) =>
    toResponse(await useCases.getItem(parseId(request.params.id))),
  );

  app.put<{ Params: { id: string } }>('/items/:id', async (request) => {
    const id = parseId(request.params.id);
    return toResponse(await useCases.replaceItem(id, parseInput(request.body)));
  });

  app.delete<{ Params: { id: string } }>('/items/:id', async (request, reply) => {
    await useCases.deleteItem(parseId(request.params.id));
    return reply.code(204).send();
  });

  return app;
}
