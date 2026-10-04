package bench.items.interfaces.http;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

import bench.items.application.CreateItem;
import bench.items.application.DeleteItem;
import bench.items.application.GetItem;
import bench.items.application.ReplaceItem;
import bench.items.domain.Item;
import bench.items.domain.ItemInput;
import bench.items.domain.ItemRepository;
import bench.items.domain.NotFoundException;
import java.time.Instant;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class ItemControllerTest {

  private static final String VALID = "{\"name\":\"Widget\",\"description\":\"Blue\",\"price_cents\":1999,\"quantity\":5}";
  private static final Instant TS = Instant.parse("2026-10-03T10:00:00Z");

  /** In-memory repository: every call can be made to fail with the supplied exception. */
  private static class FakeRepository implements ItemRepository {
    private final Supplier<RuntimeException> failure;

    FakeRepository(Supplier<RuntimeException> failure) {
      this.failure = failure;
    }

    private void maybeFail() {
      if (failure != null) {
        throw failure.get();
      }
    }

    private static Item item(long id, String description) {
      return new Item(id, "Widget", description, 1999, 5, TS, TS);
    }

    @Override
    public Item get(long id) {
      maybeFail();
      return item(id, null);
    }

    @Override
    public Item create(ItemInput input) {
      maybeFail();
      return item(100_001, "Blue");
    }

    @Override
    public Item replace(long id, ItemInput input) {
      maybeFail();
      return item(id, "Red");
    }

    @Override
    public void delete(long id) {
      maybeFail();
    }
  }

  private static MockMvc mvc(Supplier<RuntimeException> failure) {
    ItemRepository repo = new FakeRepository(failure);
    ItemController controller =
        new ItemController(new GetItem(repo), new CreateItem(repo), new ReplaceItem(repo), new DeleteItem(repo));
    return MockMvcBuilders.standaloneSetup(controller).setControllerAdvice(new ApiExceptionHandler()).build();
  }

  private static MockHttpServletResponse send(MockMvc mvc, MockHttpServletRequestBuilder request, String body)
      throws Exception {
    if (body != null) {
      request = request.contentType(MediaType.APPLICATION_JSON).content(body);
    }
    return mvc.perform(request).andReturn().getResponse();
  }

  private static String errorCode(MockHttpServletResponse response) throws Exception {
    String json = response.getContentAsString();
    assertThat(json).matches("\\{\"error\":\\{\"code\":\"[A-Z_]+\",\"message\":\"[^\"]+\"\\}\\}");
    return json.replaceAll(".*\"code\":\"([A-Z_]+)\".*", "$1");
  }

  @Test
  void getReturnsTheItemWithAnExplicitNullDescription() throws Exception {
    MockHttpServletResponse r = send(mvc(null), get("/items/7"), null);
    assertThat(r.getStatus()).isEqualTo(200);
    assertThat(r.getContentType()).startsWith("application/json");
    assertThat(r.getContentAsString())
        .isEqualTo("{\"id\":7,\"name\":\"Widget\",\"description\":null,\"price_cents\":1999,\"quantity\":5,"
            + "\"created_at\":\"2026-10-03T10:00:00Z\",\"updated_at\":\"2026-10-03T10:00:00Z\"}");
    for (String header : new String[] {"ETag", "Cache-Control", "Last-Modified", "Content-Encoding"}) {
      assertThat(r.containsHeader(header)).as(header).isFalse();
    }
  }

  @ParameterizedTest
  @ValueSource(strings = {"abc", "0", "-1", "1.5", "1e3", "+5", "9007199254740992", "99999999999999999999"})
  void invalidIdsAre400(String id) throws Exception {
    for (MockHttpServletRequestBuilder request :
        new MockHttpServletRequestBuilder[] {get("/items/" + id), delete("/items/" + id), put("/items/" + id)}) {
      MockHttpServletResponse r = send(mvc(null), request, VALID);
      assertThat(r.getStatus()).as(id).isEqualTo(400);
      assertThat(errorCode(r)).isEqualTo("VALIDATION_ERROR");
    }
  }

  @Test
  void createReturns201WithLocation() throws Exception {
    MockHttpServletResponse r = send(mvc(null), post("/items"), VALID);
    assertThat(r.getStatus()).isEqualTo(201);
    assertThat(r.getHeader("Location")).isEqualTo("/items/100001");
    assertThat(r.getContentAsString()).contains("\"id\":100001").contains("\"description\":\"Blue\"");
  }

  @Test
  void invalidBodiesAre400OnPostAndPut() throws Exception {
    for (String body : new String[] {"{\"name\":", "[]", "{\"price_cents\":1,\"quantity\":1}",
        "{\"name\":\"\",\"price_cents\":1,\"quantity\":1}", "{\"name\":\"n\",\"price_cents\":-1,\"quantity\":1}",
        "{\"name\":\"n\",\"price_cents\":1,\"quantity\":2147483648}"}) {
      for (MockHttpServletRequestBuilder request : new MockHttpServletRequestBuilder[] {post("/items"), put("/items/5")}) {
        MockHttpServletResponse r = send(mvc(null), request, body);
        assertThat(r.getStatus()).as(body).isEqualTo(400);
        assertThat(errorCode(r)).isEqualTo("VALIDATION_ERROR");
      }
    }
    // no body at all
    assertThat(send(mvc(null), post("/items"), null).getStatus()).isEqualTo(400);
    assertThat(send(mvc(null), put("/items/5"), null).getStatus()).isEqualTo(400);
  }

  @Test
  void replaceAndDelete() throws Exception {
    MockHttpServletResponse put = send(mvc(null), put("/items/5"), VALID);
    assertThat(put.getStatus()).isEqualTo(200);
    assertThat(put.getContentAsString()).contains("\"id\":5").contains("\"description\":\"Red\"");
    MockHttpServletResponse del = send(mvc(null), delete("/items/5"), null);
    assertThat(del.getStatus()).isEqualTo(204);
    assertThat(del.getContentAsString()).isEmpty();
  }

  @Test
  void errorMappingAndNoLeaks() throws Exception {
    Object[][] cases = {
        {(Supplier<RuntimeException>) NotFoundException::new, 404, "NOT_FOUND"},
        {(Supplier<RuntimeException>) () -> new IllegalStateException("secret connection string"), 500, "INTERNAL_ERROR"},
    };
    for (Object[] c : cases) {
      @SuppressWarnings("unchecked")
      MockMvc mvc = mvc((Supplier<RuntimeException>) c[0]);
      for (MockHttpServletRequestBuilder request : new MockHttpServletRequestBuilder[] {
          get("/items/1"), post("/items"), put("/items/1"), delete("/items/1")}) {
        MockHttpServletResponse r = send(mvc, request, VALID);
        assertThat(r.getStatus()).isEqualTo(c[1]);
        assertThat(errorCode(r)).isEqualTo(c[2]);
        assertThat(r.getContentAsString()).doesNotContain("secret");
      }
    }
  }

  @Test
  void onlyTheContractRoutesExist() throws Exception {
    MockMvc mvc = mvc(null);
    assertThat(send(mvc, get("/items"), null).getStatus()).isEqualTo(405);
    assertThat(send(mvc, patch("/items/1"), null).getStatus()).isEqualTo(405);
    assertThat(send(mvc, get("/health"), null).getStatus()).isEqualTo(404);
  }
}
