import { validateId, validateInput } from '../domain/item.ts';
import type { Item, ItemInput, ItemRepository } from '../domain/item.ts';

/** The four use cases over one repository port. They depend only on the domain. */
export interface UseCases {
  getItem(id: number): Promise<Item>;
  createItem(input: ItemInput): Promise<Item>;
  replaceItem(id: number, input: ItemInput): Promise<Item>;
  deleteItem(id: number): Promise<void>;
}

export function createUseCases(repository: ItemRepository): UseCases {
  return {
    async getItem(id) {
      validateId(id);
      return repository.get(id);
    },
    async createItem(input) {
      validateInput(input);
      return repository.create(input);
    },
    async replaceItem(id, input) {
      validateId(id);
      validateInput(input);
      return repository.replace(id, input);
    },
    async deleteItem(id) {
      validateId(id);
      return repository.delete(id);
    },
  };
}
