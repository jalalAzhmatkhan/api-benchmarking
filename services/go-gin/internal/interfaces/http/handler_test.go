package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/domain"
)

type getFn func(context.Context, int64) (domain.Item, error)
type createFn func(context.Context, domain.ItemInput) (domain.Item, error)
type replaceFn func(context.Context, int64, domain.ItemInput) (domain.Item, error)
type deleteFn func(context.Context, int64) error

func (f getFn) Execute(ctx context.Context, id int64) (domain.Item, error) { return f(ctx, id) }
func (f createFn) Execute(ctx context.Context, in domain.ItemInput) (domain.Item, error) {
	return f(ctx, in)
}
func (f replaceFn) Execute(ctx context.Context, id int64, in domain.ItemInput) (domain.Item, error) {
	return f(ctx, id, in)
}
func (f deleteFn) Execute(ctx context.Context, id int64) error { return f(ctx, id) }

var ts = time.Date(2026, 10, 3, 10, 0, 0, 0, time.UTC)

func sample(id int64) domain.Item {
	d := "Blue"
	return domain.Item{ID: id, Name: "Widget", Description: &d, PriceCents: 1999, Quantity: 5, CreatedAt: ts, UpdatedAt: ts}
}

func handler(err error) Handler {
	return Handler{
		Get:     getFn(func(_ context.Context, id int64) (domain.Item, error) { return sample(id), err }),
		Create:  createFn(func(_ context.Context, _ domain.ItemInput) (domain.Item, error) { return sample(100001), err }),
		Replace: replaceFn(func(_ context.Context, id int64, _ domain.ItemInput) (domain.Item, error) { return sample(id), err }),
		Delete:  deleteFn(func(context.Context, int64) error { return err }),
	}
}

func do(h Handler, method, path, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	NewRouter(h).ServeHTTP(w, req)
	return w
}

func errCode(t *testing.T, w *httptest.ResponseRecorder) string {
	t.Helper()
	var b errorBody
	if err := json.Unmarshal(w.Body.Bytes(), &b); err != nil || b.Error.Message == "" {
		t.Fatalf("not a contract error body: %q (%v)", w.Body.String(), err)
	}
	return b.Error.Code
}

const validBody = `{"name":"Widget","description":"Blue","price_cents":1999,"quantity":5}`

func TestGetOK(t *testing.T) {
	w := do(handler(nil), http.MethodGet, "/items/7", "")
	if w.Code != 200 || !strings.HasPrefix(w.Header().Get("Content-Type"), "application/json") {
		t.Fatalf("status %d, content-type %q", w.Code, w.Header().Get("Content-Type"))
	}
	var got itemResponse
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got.ID != 7 || got.Name != "Widget" || got.Description == nil || *got.Description != "Blue" ||
		got.PriceCents != 1999 || got.Quantity != 5 || !got.CreatedAt.Equal(ts) {
		t.Fatalf("unexpected body: %s", w.Body.String())
	}
	for _, h := range []string{"Etag", "Cache-Control", "Last-Modified", "Content-Encoding"} {
		if w.Header().Get(h) != "" {
			t.Errorf("unexpected header %s", h)
		}
	}
}

func TestNullDescriptionIsSerialized(t *testing.T) {
	h := handler(nil)
	h.Get = getFn(func(context.Context, int64) (domain.Item, error) {
		it := sample(1)
		it.Description = nil
		return it, nil
	})
	w := do(h, http.MethodGet, "/items/1", "")
	if !strings.Contains(w.Body.String(), `"description":null`) {
		t.Fatalf("description must be an explicit null: %s", w.Body.String())
	}
}

func TestInvalidIDs(t *testing.T) {
	for _, id := range []string{"abc", "0", "-1", "1.5", "1e3", "+5", "9007199254740992", "99999999999999999999"} {
		for _, m := range []string{http.MethodGet, http.MethodDelete} {
			w := do(handler(nil), m, "/items/"+id, "")
			if w.Code != 400 || errCode(t, w) != "VALIDATION_ERROR" {
				t.Errorf("%s /items/%s: status %d, body %s", m, id, w.Code, w.Body.String())
			}
		}
		if w := do(handler(nil), http.MethodPut, "/items/"+id, validBody); w.Code != 400 {
			t.Errorf("PUT /items/%s: status %d", id, w.Code)
		}
	}
}

func TestCreate(t *testing.T) {
	w := do(handler(nil), http.MethodPost, "/items", validBody)
	if w.Code != 201 || w.Header().Get("Location") != "/items/100001" {
		t.Fatalf("status %d, Location %q", w.Code, w.Header().Get("Location"))
	}
	var got itemResponse
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil || got.ID != 100001 {
		t.Fatalf("unexpected body: %s", w.Body.String())
	}
}

func TestBodyValidation(t *testing.T) {
	bad := map[string]string{
		"empty body":          ``,
		"malformed":           `{"name":`,
		"array":               `[]`,
		"string":              `"x"`,
		"null":                `null`,
		"name missing":        `{"price_cents":1,"quantity":1}`,
		"name null":           `{"name":null,"price_cents":1,"quantity":1}`,
		"name number":         `{"name":5,"price_cents":1,"quantity":1}`,
		"price missing":       `{"name":"n","quantity":1}`,
		"price string":        `{"name":"n","price_cents":"10","quantity":1}`,
		"price fractional":    `{"name":"n","price_cents":1.5,"quantity":1}`,
		"price overflow":      `{"name":"n","price_cents":99999999999999999999,"quantity":1}`,
		"quantity missing":    `{"name":"n","price_cents":1}`,
		"quantity fractional": `{"name":"n","price_cents":1,"quantity":1.5}`,
		"quantity string":     `{"name":"n","price_cents":1,"quantity":"1"}`,
	}
	for name, body := range bad {
		for _, route := range [][2]string{{http.MethodPost, "/items"}, {http.MethodPut, "/items/5"}} {
			w := do(handler(nil), route[0], route[1], body)
			if w.Code != 400 || errCode(t, w) != "VALIDATION_ERROR" {
				t.Errorf("%s %s [%s]: status %d, body %s", route[0], route[1], name, w.Code, w.Body.String())
			}
		}
	}
	ok := `{"name":"n","price_cents":1,"quantity":1,"unknown":true,"id":1}`
	if w := do(handler(nil), http.MethodPost, "/items", ok); w.Code != 201 {
		t.Fatalf("unknown fields must be ignored, got %d", w.Code)
	}
}

func TestReplaceAndDelete(t *testing.T) {
	w := do(handler(nil), http.MethodPut, "/items/5", validBody)
	if w.Code != 200 {
		t.Fatalf("PUT status %d", w.Code)
	}
	w = do(handler(nil), http.MethodDelete, "/items/5", "")
	if w.Code != 204 || w.Body.Len() != 0 {
		t.Fatalf("DELETE status %d, body %q", w.Code, w.Body.String())
	}
}

func TestErrorMapping(t *testing.T) {
	cases := []struct {
		err    error
		status int
		code   string
	}{
		{domain.ErrNotFound, 404, "NOT_FOUND"},
		{&domain.ValidationError{Message: "bad"}, 400, "VALIDATION_ERROR"},
		{errors.New("db down"), 500, "INTERNAL_ERROR"},
	}
	for _, tc := range cases {
		h := handler(tc.err)
		for _, r := range [][3]string{
			{http.MethodGet, "/items/1", ""}, {http.MethodPost, "/items", validBody},
			{http.MethodPut, "/items/1", validBody}, {http.MethodDelete, "/items/1", ""},
		} {
			w := do(h, r[0], r[1], r[2])
			if w.Code != tc.status || errCode(t, w) != tc.code {
				t.Errorf("%s %s with %v: status %d, body %s", r[0], r[1], tc.err, w.Code, w.Body.String())
			}
		}
	}
	// internal errors never leak details
	w := do(handler(errors.New("secret connection string")), http.MethodGet, "/items/1", "")
	if strings.Contains(w.Body.String(), "secret") {
		t.Fatalf("internal error leaked: %s", w.Body.String())
	}
}

func TestPanicBecomesContract500(t *testing.T) {
	h := handler(nil)
	h.Get = getFn(func(context.Context, int64) (domain.Item, error) { panic("boom") })
	w := do(h, http.MethodGet, "/items/1", "")
	if w.Code != 500 || errCode(t, w) != "INTERNAL_ERROR" {
		t.Fatalf("status %d, body %s", w.Code, w.Body.String())
	}
}
