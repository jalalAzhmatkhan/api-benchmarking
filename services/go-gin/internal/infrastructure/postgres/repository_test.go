package postgres

import (
	"context"
	"errors"
	"regexp"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/pashagolub/pgxmock/v5"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/domain"
)

var cols = []string{"id", "name", "description", "price_cents", "quantity", "created_at", "updated_at"}

func newRepo(t *testing.T) (*ItemRepository, pgxmock.PgxPoolIface) {
	t.Helper()
	mock, err := pgxmock.NewPool()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("unmet expectations: %v", err)
		}
	})
	return NewItemRepository(mock), mock
}

func q(sql string) string { return regexp.QuoteMeta(sql) }

func TestGet(t *testing.T) {
	ts := time.Date(2026, 10, 3, 10, 0, 0, 0, time.FixedZone("X", 7*3600))
	desc := "Blue"

	repo, mock := newRepo(t)
	mock.ExpectQuery(q(selectSQL)).WithArgs(int64(7)).
		WillReturnRows(pgxmock.NewRows(cols).AddRow(int64(7), "Widget", &desc, int64(1999), int32(5), ts, ts))
	it, err := repo.Get(context.Background(), 7)
	if err != nil {
		t.Fatal(err)
	}
	if it.ID != 7 || it.Name != "Widget" || it.Description == nil || *it.Description != "Blue" ||
		it.PriceCents != 1999 || it.Quantity != 5 || !it.CreatedAt.Equal(ts) || it.CreatedAt.Location() != time.UTC {
		t.Fatalf("unexpected item: %+v", it)
	}

	repo, mock = newRepo(t)
	mock.ExpectQuery(q(selectSQL)).WithArgs(int64(8)).
		WillReturnRows(pgxmock.NewRows(cols).AddRow(int64(8), "n", (*string)(nil), int64(0), int32(0), ts, ts))
	it, err = repo.Get(context.Background(), 8)
	if err != nil || it.Description != nil {
		t.Fatalf("null description must scan to nil: %+v, %v", it, err)
	}
}

func TestGetErrors(t *testing.T) {
	repo, mock := newRepo(t)
	mock.ExpectQuery(q(selectSQL)).WithArgs(int64(1)).WillReturnError(pgx.ErrNoRows)
	if _, err := repo.Get(context.Background(), 1); !errors.Is(err, domain.ErrNotFound) {
		t.Fatalf("no rows must map to ErrNotFound: %v", err)
	}

	repo, mock = newRepo(t)
	boom := errors.New("db down")
	mock.ExpectQuery(q(selectSQL)).WithArgs(int64(1)).WillReturnError(boom)
	if _, err := repo.Get(context.Background(), 1); !errors.Is(err, boom) || errors.Is(err, domain.ErrNotFound) {
		t.Fatalf("other errors must propagate unchanged in kind: %v", err)
	}
}

func TestCreate(t *testing.T) {
	ts := time.Now()
	desc := "d"
	in := domain.ItemInput{Name: "n", Description: &desc, PriceCents: 5, Quantity: 2}
	repo, mock := newRepo(t)
	mock.ExpectQuery(q(insertSQL)).WithArgs("n", &desc, int64(5), int64(2)).
		WillReturnRows(pgxmock.NewRows(cols).AddRow(int64(100001), "n", &desc, int64(5), int32(2), ts, ts))
	it, err := repo.Create(context.Background(), in)
	if err != nil || it.ID != 100001 {
		t.Fatalf("got %+v, %v", it, err)
	}
}

func TestReplace(t *testing.T) {
	ts := time.Now()
	in := domain.ItemInput{Name: "n", PriceCents: 5, Quantity: 2}
	repo, mock := newRepo(t)
	mock.ExpectQuery(q(updateSQL)).WithArgs(int64(9), "n", (*string)(nil), int64(5), int64(2)).
		WillReturnRows(pgxmock.NewRows(cols).AddRow(int64(9), "n", (*string)(nil), int64(5), int32(2), ts, ts))
	if it, err := repo.Replace(context.Background(), 9, in); err != nil || it.ID != 9 {
		t.Fatalf("got %+v, %v", it, err)
	}

	repo, mock = newRepo(t)
	mock.ExpectQuery(q(updateSQL)).WithArgs(int64(10), "n", (*string)(nil), int64(5), int64(2)).WillReturnError(pgx.ErrNoRows)
	if _, err := repo.Replace(context.Background(), 10, in); !errors.Is(err, domain.ErrNotFound) {
		t.Fatalf("missing row must map to ErrNotFound: %v", err)
	}
}

func TestDelete(t *testing.T) {
	repo, mock := newRepo(t)
	mock.ExpectExec(q(deleteSQL)).WithArgs(int64(1)).WillReturnResult(pgxmock.NewResult("DELETE", 1))
	if err := repo.Delete(context.Background(), 1); err != nil {
		t.Fatal(err)
	}

	repo, mock = newRepo(t)
	mock.ExpectExec(q(deleteSQL)).WithArgs(int64(2)).WillReturnResult(pgxmock.NewResult("DELETE", 0))
	if err := repo.Delete(context.Background(), 2); !errors.Is(err, domain.ErrNotFound) {
		t.Fatalf("zero rows must map to ErrNotFound: %v", err)
	}

	repo, mock = newRepo(t)
	boom := errors.New("db down")
	mock.ExpectExec(q(deleteSQL)).WithArgs(int64(3)).WillReturnError(boom)
	if err := repo.Delete(context.Background(), 3); !errors.Is(err, boom) {
		t.Fatalf("exec error must propagate: %v", err)
	}
}
