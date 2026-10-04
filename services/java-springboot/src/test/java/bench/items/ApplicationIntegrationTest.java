package bench.items;

import static org.assertj.core.api.Assertions.assertThat;

import com.zaxxer.hikari.HikariDataSource;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;

/** The whole service wired by Spring against the real database (CI provides DATABASE_URL). */
@EnabledIfEnvironmentVariable(named = "DATABASE_URL", matches = ".+")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = "DB_POOL_SIZE=3")
class ApplicationIntegrationTest {

  @Value("${local.server.port}")
  int port;

  @Autowired DataSource dataSource;

  private HttpResponse<String> call(String method, String path, String body) throws Exception {
    HttpRequest.Builder request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path));
    request.method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(body));
    return HttpClient.newHttpClient().send(request.build(), HttpResponse.BodyHandlers.ofString());
  }

  @Test
  void poolIsFixedAndPreWarmed() {
    HikariDataSource hikari = (HikariDataSource) dataSource;
    assertThat(hikari.getMaximumPoolSize()).isEqualTo(3);
    assertThat(hikari.getMinimumIdle()).isEqualTo(3);
    assertThat(hikari.getConnectionTimeout()).isEqualTo(5_000);
    assertThat(hikari.getHikariPoolMXBean().getTotalConnections()).isEqualTo(3);
  }

  @Test
  void servesTheContractEndToEnd() throws Exception {
    HttpResponse<String> seeded = call("GET", "/items/1", null);
    assertThat(seeded.statusCode()).isEqualTo(200);
    assertThat(seeded.body()).contains("\"id\":1").contains("\"name\":\"item-1\"");

    HttpResponse<String> created = call("POST", "/items", "{\"name\":\"spring\",\"price_cents\":1,\"quantity\":1}");
    assertThat(created.statusCode()).isEqualTo(201);
    String location = created.headers().firstValue("Location").orElseThrow();

    assertThat(call("PUT", location, "{\"name\":\"spring2\",\"description\":\"d\",\"price_cents\":2,\"quantity\":2}").statusCode())
        .isEqualTo(200);
    assertThat(call("DELETE", location, null).statusCode()).isEqualTo(204);
    assertThat(call("GET", location, null).statusCode()).isEqualTo(404);
    assertThat(call("GET", "/items/abc", null).statusCode()).isEqualTo(400);
  }
}
