package bench.items.infrastructure;

import bench.items.domain.Item;
import bench.items.domain.ItemInput;
import bench.items.domain.ItemRepository;
import bench.items.domain.NotFoundException;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;

/** PostgreSQL repository: raw SQL through {@link JdbcClient}, no ORM. */
public class JdbcItemRepository implements ItemRepository {

  // Canonical statements (Documentation/specs/database-schema.md §2), shared verbatim by all stacks.
  static final String SELECT =
      "SELECT id, name, description, price_cents, quantity, created_at, updated_at FROM items WHERE id = ?";
  static final String INSERT =
      "INSERT INTO items (name, description, price_cents, quantity) VALUES (?, ?, ?, ?) "
          + "RETURNING id, name, description, price_cents, quantity, created_at, updated_at";
  static final String UPDATE =
      "UPDATE items SET name = ?, description = ?, price_cents = ?, quantity = ?, updated_at = now() "
          + "WHERE id = ? RETURNING id, name, description, price_cents, quantity, created_at, updated_at";
  static final String DELETE = "DELETE FROM items WHERE id = ?";

  private static final RowMapper<Item> ROW_MAPPER = JdbcItemRepository::mapRow;

  private final JdbcClient jdbc;

  public JdbcItemRepository(JdbcClient jdbc) {
    this.jdbc = jdbc;
  }

  private static Item mapRow(ResultSet rs, int rowNum) throws SQLException {
    return new Item(
        rs.getLong("id"),
        rs.getString("name"),
        rs.getString("description"),
        rs.getLong("price_cents"),
        rs.getInt("quantity"),
        rs.getObject("created_at", OffsetDateTime.class).toInstant(),
        rs.getObject("updated_at", OffsetDateTime.class).toInstant());
  }

  @Override
  public Item get(long id) {
    return jdbc.sql(SELECT).param(id).query(ROW_MAPPER).optional().orElseThrow(NotFoundException::new);
  }

  @Override
  public Item create(ItemInput input) {
    return jdbc.sql(INSERT)
        .param(input.name())
        .param(input.description())
        .param(input.priceCents())
        .param((int) input.quantity()) // range validated by the domain (0..Integer.MAX_VALUE)
        .query(ROW_MAPPER)
        .single();
  }

  @Override
  public Item replace(long id, ItemInput input) {
    return jdbc.sql(UPDATE)
        .param(input.name())
        .param(input.description())
        .param(input.priceCents())
        .param((int) input.quantity())
        .param(id)
        .query(ROW_MAPPER)
        .optional()
        .orElseThrow(NotFoundException::new);
  }

  @Override
  public void delete(long id) {
    if (jdbc.sql(DELETE).param(id).update() == 0) {
      throw new NotFoundException();
    }
  }
}
